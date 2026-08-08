"""FastAPI application: admin pages, JSON API, and the public form renderer."""

from __future__ import annotations

import json
import logging
import secrets
from typing import Any

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
)
from fastapi.responses import Response as RawResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from . import auth, db, export, media, repository, sheets
from .config import settings
from .models import QUESTION_TYPES, CatapultLeadIn, FormIn, validate_answer

log = logging.getLogger("formcraft")

templates = Jinja2Templates(directory=str(settings.web_dir / "templates"))

LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}


def create_app() -> FastAPI:
    db.init_db()
    # openapi_url=None matters as much as docs_url: the schema names the app and
    # enumerates every route, which is exactly what a visitor should not get.
    app = FastAPI(
        title="Formcraft", docs_url=None, redoc_url=None, openapi_url=None
    )
    app.mount(
        "/static",
        StaticFiles(directory=str(settings.web_dir / "static")),
        name="static",
    )
    _register_public(app)
    _register_catapult_integration(app)
    if settings.is_admin_role:
        _register_admin(app)
    return app


def _is_local(request: Request) -> bool:
    """True when the client is on this machine.

    Deliberately reads the socket peer, never X-Forwarded-For — a header a
    remote caller controls must not be able to unlock the admin surface.
    """
    if settings.admin_allow_remote:
        return True
    client = request.client
    return client is not None and client.host in LOOPBACK


def _require_local(request: Request) -> None:
    """Admin surface is invisible off-machine — 404, not 403, so it leaks nothing."""
    if not _is_local(request):
        raise HTTPException(status_code=404, detail="Not found")


def _render(request: Request, template: str, **context: Any) -> HTMLResponse:
    """Every template gets the brand and the image-slot registry for free."""
    return templates.TemplateResponse(
        request=request,
        name=template,
        context={
            "brand_name": settings.brand_name,
            "owner_name": settings.owner_name,
            "owner_role": settings.owner_role,
            **media.context(),
            **context,
        },
    )


def _register_admin(app: FastAPI) -> None:  # noqa: C901 - route table, flat by nature
    admin = Depends(auth.require_admin)
    local = Depends(_require_local)

    # ---------------------------------------------------------------- auth

    @app.get("/login", response_class=HTMLResponse, dependencies=[local])
    def login_page(request: Request) -> Response:
        if auth.read_session(request):
            return RedirectResponse("/", status_code=302)
        return _render(request, "login.html", error=None)

    @app.post("/login", response_class=HTMLResponse, dependencies=[local])
    async def login_submit(request: Request) -> Response:
        form = await request.form()
        username = str(form.get("username", ""))
        password = str(form.get("password", ""))

        if auth.throttled():
            return _render(
                request,
                "login.html",
                error="Too many attempts. Wait a few minutes and try again.",
            )

        if not auth.verify_credentials(username, password):
            auth.record_failure()
            return _render(
                request, "login.html", error="Incorrect username or password."
            )

        auth.clear_failures()
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(
            auth.SESSION_COOKIE,
            auth.issue_session(),
            max_age=auth.SESSION_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=settings.secure_cookies,
        )
        return response

    @app.post("/logout", dependencies=[local])
    def logout() -> Response:
        response = RedirectResponse("/login", status_code=302)
        response.delete_cookie(auth.SESSION_COOKIE)
        return response

    # ------------------------------------------------------------- admin UI

    @app.get("/", response_class=HTMLResponse, dependencies=[local])
    def dashboard(request: Request) -> Response:
        if not auth.read_session(request):
            return RedirectResponse("/login", status_code=302)
        return _render(
            request,
            "dashboard.html",
            forms=repository.list_forms(),
            base_url=settings.base_url,
            google=sheets.status_summary(),
        )

    @app.get("/admin/new", response_class=HTMLResponse, dependencies=[local])
    def builder_new(request: Request) -> Response:
        if not auth.read_session(request):
            return RedirectResponse("/login", status_code=302)
        return _render(
            request,
            "builder.html",
            form=None,
            form_data=None,
            question_types=QUESTION_TYPES,
            base_url=settings.base_url,
        )

    @app.get("/admin/media", response_class=HTMLResponse, dependencies=[local])
    def media_gallery(request: Request) -> Response:
        if not auth.read_session(request):
            return RedirectResponse("/login", status_code=302)
        filled = sum(1 for name in media.SLOTS if media.resolve(name))
        return _render(request, "media.html", filled=filled)

    @app.get("/admin/media/briefs.txt", dependencies=[local, admin])
    def media_briefs() -> RawResponse:
        return _file_response(
            media.briefs().encode("utf-8"), "text/plain; charset=utf-8",
            "formcraft-image-briefs.txt",
        )

    @app.get("/admin/{form_id}", response_class=HTMLResponse, dependencies=[local])
    def builder_edit(request: Request, form_id: str) -> Response:
        if not auth.read_session(request):
            return RedirectResponse("/login", status_code=302)
        form = repository.get_form(form_id=form_id)
        if form is None:
            raise HTTPException(status_code=404, detail="Form not found")
        return _render(
            request,
            "builder.html",
            form=form,
            form_data=_editor_payload(form),
            question_types=QUESTION_TYPES,
            base_url=settings.base_url,
        )

    @app.get(
        "/admin/{form_id}/responses",
        response_class=HTMLResponse,
        dependencies=[local],
    )
    def responses_page(request: Request, form_id: str) -> Response:
        if not auth.read_session(request):
            return RedirectResponse("/login", status_code=302)
        form = repository.get_form(form_id=form_id)
        if form is None:
            raise HTTPException(status_code=404, detail="Form not found")
        return _render(
            request,
            "responses.html",
            form=form,
            responses=repository.list_responses(form_id),
            base_url=settings.base_url,
            google=sheets.status_summary(),
        )

    # --------------------------------------------------------------- export

    @app.get("/admin/{form_id}/export.csv", dependencies=[local, admin])
    def export_csv(form_id: str) -> RawResponse:
        form, questions, responses = _export_data(form_id)
        return _file_response(
            export.to_csv(questions, responses),
            "text/csv; charset=utf-8",
            export.filename(form["title"], "csv"),
        )

    @app.get("/admin/{form_id}/export.xlsx", dependencies=[local, admin])
    def export_xlsx(form_id: str) -> RawResponse:
        form, questions, responses = _export_data(form_id)
        return _file_response(
            export.to_xlsx(form["title"], questions, responses),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            export.filename(form["title"], "xlsx"),
        )

    @app.post("/api/forms/{form_id}/export-key", dependencies=[local, admin])
    def api_export_key(form_id: str, rotate: bool = True) -> JSONResponse:
        if not rotate:
            repository.clear_export_key(form_id)
            return JSONResponse({"key": None})
        key = repository.rotate_export_key(form_id)
        return JSONResponse(
            {"key": key, "url": f"{settings.base_url}/feed/{form_id}.csv?key={key}"}
        )

    @app.get("/feed/{form_id}.csv", dependencies=[local])
    def export_feed(form_id: str, key: str = "") -> RawResponse:
        """Refreshable CSV for Excel / Numbers / Sheets.

        Registered on the admin instance only, and gated on `local`, so the
        key never crosses the network — it is only ever fetched over loopback
        by a spreadsheet running on this same machine.
        """
        form = repository.form_by_export_key(form_id, key)
        if form is None:
            raise HTTPException(status_code=404, detail="Not found")
        questions = repository.all_questions(form_id)
        responses = repository.list_responses(form_id, limit=10000)
        return RawResponse(
            content=export.to_csv(questions, responses),
            media_type="text/csv; charset=utf-8",
            headers={"Cache-Control": "no-store"},
        )

    # ------------------------------------------------------------- JSON API

    @app.post("/api/forms", dependencies=[local, admin])
    async def api_create(request: Request) -> JSONResponse:
        payload = await _read_form(request)
        try:
            form_id = repository.create_form(payload)
        except Exception as exc:  # converted into a safe, useful API response
            _raise_form_write_error(exc, action="created")
        sheet = _sheet_after_save(form_id, create=True)
        return JSONResponse(
            {"id": form_id, "sheet": sheet}, status_code=status.HTTP_201_CREATED
        )

    @app.put("/api/forms/{form_id}", dependencies=[local, admin])
    async def api_update(form_id: str, request: Request) -> JSONResponse:
        payload = await _read_form(request)
        try:
            repository.update_form(form_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Form not found") from exc
        except Exception as exc:  # converted into a safe, useful API response
            _raise_form_write_error(exc, action="updated")
        return JSONResponse(
            {"id": form_id, "sheet": _sheet_after_save(form_id, create=False)}
        )

    @app.delete("/api/forms/{form_id}", dependencies=[local, admin])
    def api_delete(form_id: str) -> JSONResponse:
        repository.delete_form(form_id)
        return JSONResponse({"deleted": form_id})

    @app.post("/api/forms/{form_id}/sheet", dependencies=[local, admin])
    def api_create_sheet(form_id: str) -> JSONResponse:
        return JSONResponse(_attach_sheet(form_id, force=True))

    @app.post("/api/sync", dependencies=[local, admin])
    def api_sync() -> JSONResponse:
        return JSONResponse(retry_pending())


def _register_public(app: FastAPI) -> None:

    @app.get("/f/{public_ref}", response_class=HTMLResponse)
    def public_form(request: Request, public_ref: str) -> Response:
        form = repository.get_form(public_ref=public_ref)
        if form is None:
            raise HTTPException(status_code=404, detail="Form not found")
        # Drafts are visible only to a logged-in admin on the local instance.
        preview_ok = settings.is_admin_role and auth.read_session(request)
        if not form["is_published"] and not preview_ok:
            raise HTTPException(status_code=404, detail="Form not found")
        response = _render(
            request,
            "form.html",
            form=form,
            preview=not form["is_published"],
        )
        # An unguessable URL is not private if a crawler indexes it.
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response

    @app.post("/f/{public_ref}")
    async def submit(public_ref: str, request: Request) -> JSONResponse:
        form = repository.get_form(public_ref=public_ref)
        if form is None or not form["is_published"]:
            raise HTTPException(status_code=404, detail="Form not found")

        body = await request.json()
        answers: dict[str, Any] = {}
        errors: dict[str, str] = {}

        for question in form["questions"]:
            value, error = validate_answer(question, body.get(question["id"]))
            if error:
                errors[question["id"]] = error
            else:
                answers[question["id"]] = value

        if errors:
            return JSONResponse({"errors": errors}, status_code=422)

        response_id = _save_form_response(form, answers)

        return JSONResponse(
            {"ok": True, "id": response_id, "message": form["confirm_msg"]}
        )

    @app.post("/f/{public_ref}/responses/{response_id}/booking")
    async def save_booking(
        public_ref: str, response_id: str, request: Request
    ) -> JSONResponse:
        form = repository.get_form(public_ref=public_ref)
        if form is None or not form["is_published"] or not form["meeting_url"]:
            raise HTTPException(status_code=404, detail="Form not found")

        body = await request.json()
        booking_answers: dict[str, Any] = {}
        for question in form["questions"]:
            field = question["config"].get("calendly_field")
            if not field:
                continue
            value, error = validate_answer(question, body.get(field))
            if error:
                return JSONResponse({"detail": error}, status_code=422)
            booking_answers[question["id"]] = value

        if not booking_answers or body.get("status") != "Booked":
            return JSONResponse({"detail": "Invalid booking data."}, status_code=422)

        saved = repository.update_response(form["id"], response_id, booking_answers)
        if saved is None:
            raise HTTPException(status_code=404, detail="Response not found")

        sheet_synced = False
        if sheets.enabled() and form.get("sheet_id"):
            try:
                sheets.append_response(
                    form, response_id, saved["payload"], saved["submitted_at"]
                )
            except Exception as exc:  # noqa: BLE001 - booking remains durable
                sync_error = f"{type(exc).__name__}: {exc}"
                log.warning(
                    "booking sheet sync failed for %s: %s", response_id, sync_error
                )
                repository.mark_synced(response_id, sync_error)
            else:
                repository.mark_synced(response_id)
                sheet_synced = True

        return JSONResponse(
            {
                "ok": True,
                "sheet_connected": bool(form.get("sheet_id")),
                "sheet_synced": sheet_synced,
            }
        )

    @app.exception_handler(404)
    async def form_not_found(request: Request, exc: Exception) -> Response:
        """A branded page for mistyped form links.

        Scoped to /f/ deliberately: everywhere else a bare 404 is the point,
        since a styled page would confirm what is running at that address.
        """
        if not request.url.path.startswith("/f/"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        response = _render(request, "not_found.html")
        response.status_code = 404
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response

    @app.get("/healthz")
    def healthz() -> JSONResponse:
        # The public instance says only that it is up. Role, database state and
        # integration status are operator detail, not visitor-facing.
        if not settings.is_admin_role:
            return JSONResponse({"ok": True})
        return JSONResponse(
            {
                "ok": True,
                "role": settings.role,
                "database": db.ping(),
                "google": sheets.status_summary(),
            }
        )


CATAPULT_FIELD_LABELS = {
    "name": "Name",
    "email": "Email",
    "phone": "Phone",
    "company": "Business name",
    "website": "Website",
    "goal": "Main goal",
    "budgetBand": "Budget",
    "timeline": "Timeline",
    "message": "Additional context",
    "diagnostic": "Diagnostic answers",
    "utm": "Attribution",
    "consent": "Consent",
    "source": "Source",
}


def _register_catapult_integration(app: FastAPI) -> None:
    @app.post("/api/integrations/catapult/{kind}")
    async def catapult_lead(kind: str, request: Request) -> JSONResponse:
        secret = settings.catapult_ingest_secret
        authorization = request.headers.get("authorization", "")
        supplied = authorization.removeprefix("Bearer ").strip()
        if not secret or not supplied or not secrets.compare_digest(secret, supplied):
            raise HTTPException(status_code=404, detail="Not found")

        form_ids = {
            "contact": settings.catapult_contact_form_id,
            "diagnostic": settings.catapult_diagnostic_form_id,
        }
        form_id = form_ids.get(kind, "")
        if not form_id:
            raise HTTPException(status_code=404, detail="Not found")

        try:
            payload = CatapultLeadIn.model_validate(await request.json())
        except (ValidationError, ValueError) as exc:
            detail = _validation_detail(exc)
            return JSONResponse({"message": detail}, status_code=422)

        if payload.source != kind:
            return JSONResponse(
                {"message": "The form source does not match this submission."},
                status_code=422,
            )

        form = repository.get_form(form_id=form_id)
        if form is None or not form["is_published"]:
            raise HTTPException(status_code=503, detail="Form is unavailable")

        values = payload.model_dump(exclude={"websiteCheck"})
        values["diagnostic"] = json.dumps(payload.diagnostic, sort_keys=True)
        values["utm"] = json.dumps(payload.utm, sort_keys=True)
        values["consent"] = "Agreed"
        values["source"] = "Growth diagnostic" if kind == "diagnostic" else "Contact"
        questions = {question["label"]: question for question in form["questions"]}
        answers: dict[str, Any] = {}

        for key, label in CATAPULT_FIELD_LABELS.items():
            question = questions.get(label)
            if question is None:
                log.error("Catapult form %s is missing question %s", form_id, label)
                raise HTTPException(status_code=503, detail="Form is unavailable")
            value, error = validate_answer(question, values.get(key))
            if error:
                return JSONResponse({"message": error, "field": key}, status_code=422)
            answers[question["id"]] = value

        response_id = _save_form_response(form, answers)
        return JSONResponse(
            {"ok": True, "id": response_id, "message": form["confirm_msg"]},
            status_code=201,
        )


def _validation_detail(exc: Exception) -> str:
    if isinstance(exc, ValidationError) and exc.errors():
        return str(exc.errors()[0].get("msg", "Check the form and try again."))
    return "Check the form and try again."


def _save_form_response(form: dict[str, Any], answers: dict[str, Any]) -> str:
    """Persist first, then attempt Sheet delivery without risking the response."""
    response_id = repository.save_response(form["id"], answers)
    if sheets.enabled() and form.get("sheet_id"):
        try:
            sheets.append_response(form, response_id, answers)
        except Exception as exc:  # noqa: BLE001 - never lose a response
            sync_error = f"{type(exc).__name__}: {exc}"
            log.warning("sheet sync failed for %s: %s", response_id, sync_error)
            repository.mark_synced(response_id, sync_error)
        else:
            repository.mark_synced(response_id)
    return response_id


def _export_data(form_id: str) -> tuple[dict[str, Any], list, list]:
    form = repository.get_form(form_id=form_id)
    if form is None:
        raise HTTPException(status_code=404, detail="Form not found")
    return (
        form,
        repository.all_questions(form_id),
        repository.list_responses(form_id, limit=10000),
    )


def _file_response(body: bytes, media_type: str, name: str) -> RawResponse:
    return RawResponse(
        content=body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


async def _read_form(request: Request) -> FormIn:
    try:
        raw = await request.json()
    except Exception as exc:  # Starlette may surface several decoder exceptions
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_json",
                "message": "The form data could not be read. Refresh and try again.",
            },
        ) from exc
    return _parse_form(raw)


def _parse_form(raw: Any) -> FormIn:
    try:
        return FormIn.model_validate(raw)
    except ValidationError as exc:
        errors = []
        for item in exc.errors(include_url=False, include_context=False):
            message = item["msg"].removeprefix("Value error, ")
            errors.append(
                {
                    "field": ".".join(str(part) for part in item["loc"]) or "form",
                    "message": message,
                }
            )
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_error",
                "message": "Please fix the form before saving.",
                "errors": errors,
            },
        ) from exc


def _raise_form_write_error(exc: Exception, action: str) -> None:
    if isinstance(exc, repository.DuplicateFormTitleError):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "duplicate_form_name",
                "message": (
                    "A form with this name already exists. Choose a different name."
                ),
                "field": "title",
            },
        ) from exc
    if isinstance(exc, repository.InvalidFormReferenceError):
        log.warning("rejected invalid form structure reference: %s", exc)
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_structure",
                "message": (
                    "This form changed unexpectedly. Refresh it before saving again."
                ),
            },
        ) from exc
    if isinstance(exc, (psycopg.OperationalError, db.DatabaseUnavailable)):
        log.exception("database unavailable while form was being %s", action)
        raise HTTPException(
            status_code=503,
            detail={
                "code": "database_unavailable",
                "message": (
                    "The database is temporarily unavailable, so the form was not "
                    f"{action}. "
                    "Wait a moment and try again."
                ),
            },
        ) from exc
    if isinstance(exc, psycopg.IntegrityError):
        log.exception("database rejected form while it was being %s", action)
        raise HTTPException(
            status_code=409,
            detail={
                "code": "save_conflict",
                "message": "The form conflicts with saved data. Refresh and try again.",
            },
        ) from exc
    log.exception("unexpected error while form was being %s", action)
    raise HTTPException(
        status_code=500,
        detail={
            "code": "save_failed",
            "message": (
                f"The form could not be {action}. "
                "Your changes are still on this page."
            ),
        },
    ) from exc


def _editor_payload(form: dict[str, Any]) -> dict[str, Any]:
    """Only JSON-safe fields needed by builder.js.

    Database rows also contain timezone-aware datetimes and Sheet metadata.
    Passing the whole row through Jinja's ``tojson`` makes an otherwise
    successful form creation crash on the redirect to its editor.
    """
    return {
        "title": form["title"],
        "description": form["description"],
        "display_mode": form["display_mode"],
        "accent": form["accent"],
        "is_published": form["is_published"],
        "confirm_msg": form["confirm_msg"],
        "meeting_url": form["meeting_url"],
        "meeting_label": form["meeting_label"],
        "sections": [
            {
                "id": section["id"],
                "title": section["title"],
                "description": section["description"],
                "questions": [
                    {
                        "id": question["id"],
                        "type": question["type"],
                        "label": question["label"],
                        "help_text": question["help_text"],
                        "placeholder": question["placeholder"],
                        "required": question["required"],
                        "options": question["options"],
                        "config": question["config"],
                    }
                    for question in section["questions"]
                ],
            }
            for section in form["sections"]
        ],
    }


def _sheet_after_save(form_id: str, create: bool) -> dict[str, Any]:
    """A Sheet outage must never turn a successful form save into a 500."""
    try:
        return _attach_sheet(form_id) if create else _sync_sheet(form_id)
    except Exception:  # noqa: BLE001 - form durability takes priority
        log.exception("sheet follow-up failed after form %s was saved", form_id)
        key = "created" if create else "updated"
        return {
            key: False,
            "status": "error",
            "detail": (
                "The form is saved. Google Sheets could not be reached; "
                "retry sync from Responses."
            ),
        }


def _attach_sheet(
    form_id: str, force: bool = False, include_archived: bool = True
) -> dict[str, Any]:
    """Create the spreadsheet for a form. Never fatal — the form still works."""
    if not sheets.enabled():
        return {"created": False, "detail": "Google sync is off."}

    form = repository.get_form(form_id=form_id)
    if form is None:
        raise HTTPException(status_code=404, detail="Form not found")
    if form.get("sheet_id") and not force:
        return {"created": False, "url": form["sheet_url"], "detail": "Already linked."}

    form["sheet_questions"] = (
        repository.all_questions(form_id) if include_archived else form["questions"]
    )

    try:
        sheet_id, sheet_url = sheets.create_spreadsheet(form)
    except Exception as exc:  # noqa: BLE001
        technical_detail = f"{type(exc).__name__}: {exc}"
        detail = _sheet_failure_message(exc, "created")
        repository.set_sheet(form_id, "", "", error=detail)
        log.warning("sheet creation failed for %s: %s", form_id, technical_detail)
        return {"created": False, "status": "error", "detail": detail}

    try:
        repository.set_sheet(form_id, sheet_id, sheet_url)
    except Exception:  # the Google file exists; never hide its URL
        log.exception("sheet %s was created but could not be linked", sheet_id)
        return {
            "created": True,
            "linked": False,
            "status": "error",
            "url": sheet_url,
            "detail": (
                "The Google Sheet was created, but the app could not save its link. "
                "Keep this Sheet URL and retry linking after the database recovers."
            ),
        }
    backfill = retry_pending(form_id=form_id)
    return {
        "created": True,
        "linked": True,
        "status": "ok",
        "url": sheet_url,
        "backfilled": backfill["synced"],
        "detail": "Spreadsheet created and existing responses synchronized.",
    }


def _sync_sheet(form_id: str) -> dict[str, Any]:
    """Keep a linked spreadsheet aligned with a saved form without blocking saves."""
    if not sheets.enabled():
        return {"updated": False, "detail": "Google sync is off."}

    form = repository.get_form(form_id=form_id)
    if form is None:
        raise HTTPException(status_code=404, detail="Form not found")
    if not form.get("sheet_id"):
        return {"updated": False, "detail": "No spreadsheet is linked."}

    form["sheet_questions"] = repository.all_questions(form_id)
    try:
        sheets.sync_spreadsheet(form)
    except Exception as exc:  # noqa: BLE001 - the form edit is already durable
        technical_detail = f"{type(exc).__name__}: {exc}"
        detail = _sheet_failure_message(exc, "updated")
        repository.set_sheet_error(form_id, detail)
        log.warning("sheet update failed for %s: %s", form_id, technical_detail)
        return {"updated": False, "status": "error", "detail": detail}

    repository.set_sheet_error(form_id)
    return {
        "updated": True,
        "status": "ok",
        "url": form["sheet_url"],
        "detail": "Sheet updated.",
    }


def _sheet_failure_message(exc: Exception, action: str) -> str:
    """Turn provider/network failures into safe, actionable admin copy."""
    detail = str(exc).casefold()
    saved = "The form is saved. "
    if "invalid_grant" in detail or "token has been expired" in detail:
        return saved + "Google authorization expired. Reconnect Google and retry sync."
    if "403" in detail or "permission" in detail or "forbidden" in detail:
        return saved + "Google denied access. Check the account permissions and retry."
    if "404" in detail or "not found" in detail:
        return (
            saved + "The linked Google Sheet was not found. It may have been deleted."
        )
    if "429" in detail or "quota" in detail or "rate limit" in detail:
        return (
            saved
            + "Google's request limit was reached. Wait briefly and retry sync."
        )
    if "timeout" in detail or "timed out" in detail or "connection" in detail:
        return (
            saved
            + "Google Sheets could not be reached. Check the connection and retry."
        )
    return saved + f"The Google Sheet could not be {action}. Retry sync from Responses."


def retry_pending(form_id: str = "") -> dict[str, Any]:
    """Push any responses that failed to reach their spreadsheet."""
    if not sheets.enabled():
        return {"attempted": 0, "synced": 0, "detail": "Google sync is off."}

    pending = repository.pending_sync(form_id=form_id)
    synced = 0
    last_error = ""
    for item in pending:
        form = repository.get_form(form_id=item["form_id"])
        if form is None:
            continue
        form["sheet_questions"] = repository.all_questions(item["form_id"])
        try:
            sheets.append_response(
                form, item["id"], item["payload"], item["submitted_at"]
            )
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            repository.mark_synced(item["id"], last_error)
            continue
        repository.mark_synced(item["id"])
        synced += 1

    return {
        "attempted": len(pending),
        "synced": synced,
        "detail": last_error or "Done.",
    }


app = create_app()
