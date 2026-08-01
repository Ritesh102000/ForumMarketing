"""FastAPI application: admin pages, JSON API, and the public form renderer."""

from __future__ import annotations

import logging
from typing import Any

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
from .models import QUESTION_TYPES, FormIn, validate_answer

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
        payload = _parse_form(await request.json())
        form_id = repository.create_form(payload)
        sheet = _attach_sheet(form_id)
        return JSONResponse(
            {"id": form_id, "sheet": sheet}, status_code=status.HTTP_201_CREATED
        )

    @app.put("/api/forms/{form_id}", dependencies=[local, admin])
    async def api_update(form_id: str, request: Request) -> JSONResponse:
        payload = _parse_form(await request.json())
        try:
            repository.update_form(form_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Form not found") from exc
        return JSONResponse({"id": form_id})

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

        response_id = repository.save_response(form["id"], answers)

        sync_error = ""
        if sheets.enabled() and form.get("sheet_id"):
            try:
                sheets.append_response(form, answers)
            except Exception as exc:  # noqa: BLE001 - never lose a response
                sync_error = f"{type(exc).__name__}: {exc}"
                log.warning("sheet sync failed for %s: %s", response_id, sync_error)
        repository.mark_synced(response_id, sync_error)

        return JSONResponse({"ok": True, "message": form["confirm_msg"]})

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


def _parse_form(raw: Any) -> FormIn:
    try:
        return FormIn.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


def _attach_sheet(form_id: str, force: bool = False) -> dict[str, Any]:
    """Create the spreadsheet for a form. Never fatal — the form still works."""
    if not sheets.enabled():
        return {"created": False, "detail": "Google sync is off."}

    form = repository.get_form(form_id=form_id)
    if form is None:
        raise HTTPException(status_code=404, detail="Form not found")
    if form.get("sheet_id") and not force:
        return {"created": False, "url": form["sheet_url"], "detail": "Already linked."}

    try:
        sheet_id, sheet_url = sheets.create_spreadsheet(form)
    except Exception as exc:  # noqa: BLE001
        detail = f"{type(exc).__name__}: {exc}"
        repository.set_sheet(form_id, "", "", error=detail)
        log.warning("sheet creation failed for %s: %s", form_id, detail)
        return {"created": False, "detail": detail}

    repository.set_sheet(form_id, sheet_id, sheet_url)
    return {"created": True, "url": sheet_url, "detail": "Spreadsheet created."}


def retry_pending() -> dict[str, Any]:
    """Push any responses that failed to reach their spreadsheet."""
    if not sheets.enabled():
        return {"attempted": 0, "synced": 0, "detail": "Google sync is off."}

    pending = repository.pending_sync()
    synced = 0
    last_error = ""
    for item in pending:
        form = repository.get_form(form_id=item["form_id"])
        if form is None:
            continue
        try:
            sheets.append_response(form, item["payload"], item["submitted_at"])
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
