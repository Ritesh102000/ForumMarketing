"""Form persistence: read, create, replace, delete."""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .db import readonly, transaction
from .models import FormIn


class DuplicateFormTitleError(ValueError):
    """A form already uses the same human-facing title."""


class InvalidFormReferenceError(ValueError):
    """An edit tried to reuse structure owned by a different form."""


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def slugify(title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return base or "form"


def unique_slug(conn: psycopg.Connection, title: str, exclude_id: str = "") -> str:
    base = slugify(title)
    candidate = base
    suffix = 2
    while True:
        row = conn.execute(
            "SELECT id FROM forms WHERE slug = %s AND id <> %s", (candidate, exclude_id)
        ).fetchone()
        if row is None:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def list_forms() -> list[dict[str, Any]]:
    with readonly() as conn:
        return conn.execute(
            """
            SELECT f.*,
                   (SELECT COUNT(*) FROM questions q
                     WHERE q.form_id = f.id AND NOT q.archived) AS question_count,
                   (SELECT COUNT(*) FROM responses r
                     WHERE r.form_id = f.id) AS response_count
              FROM forms f
             ORDER BY f.updated_at DESC
            """
        ).fetchall()


def get_form(
    form_id: str = "", public_ref: str = ""
) -> dict[str, Any] | None:
    """Look up by internal id (admin) or public reference (visitor link).

    There is deliberately no lookup by slug: slugs are readable and therefore
    guessable, and a visitor holding one form's link must not be able to
    discover any other form.
    """
    if not form_id and not public_ref:
        return None

    with readonly() as conn:
        if form_id:
            form = conn.execute(
                "SELECT * FROM forms WHERE id = %s", (form_id,)
            ).fetchone()
        else:
            form = conn.execute(
                "SELECT * FROM forms WHERE public_ref = %s", (public_ref,)
            ).fetchone()
        if form is None:
            return None

        sections = conn.execute(
            "SELECT * FROM sections WHERE form_id = %s ORDER BY position",
            (form["id"],),
        ).fetchall()
        questions = conn.execute(
            """SELECT * FROM questions
                WHERE form_id = %s AND NOT archived
                ORDER BY position""",
            (form["id"],),
        ).fetchall()

    by_section: dict[str | None, list[dict[str, Any]]] = {}
    for question in questions:
        by_section.setdefault(question["section_id"], []).append(question)

    for section in sections:
        section["questions"] = by_section.get(section["id"], [])

    form["sections"] = sections
    form["questions"] = questions
    return form


def all_questions(form_id: str) -> list[dict[str, Any]]:
    """Every question ever on this form, archived ones last.

    Exports use this rather than get_form(): a deleted question still has
    answers in past responses, and dropping those columns would lose data.
    """
    with readonly() as conn:
        return conn.execute(
            """SELECT * FROM questions WHERE form_id = %s
                ORDER BY archived, position""",
            (form_id,),
        ).fetchall()


def rotate_export_key(form_id: str) -> str:
    key = secrets.token_urlsafe(24)
    with transaction() as conn:
        conn.execute(
            "UPDATE forms SET export_key = %s WHERE id = %s", (key, form_id)
        )
    return key


def clear_export_key(form_id: str) -> None:
    with transaction() as conn:
        conn.execute("UPDATE forms SET export_key = NULL WHERE id = %s", (form_id,))


def form_by_export_key(form_id: str, key: str) -> dict[str, Any] | None:
    """Constant-time key check, so the feed URL cannot be probed by timing."""
    if not key:
        return None
    with readonly() as conn:
        row = conn.execute(
            "SELECT export_key FROM forms WHERE id = %s", (form_id,)
        ).fetchone()
    if row is None or not row["export_key"]:
        return None
    if not secrets.compare_digest(row["export_key"], key):
        return None
    return get_form(form_id=form_id)


def create_form(payload: FormIn) -> str:
    if any(section.id for section in payload.sections) or any(
        question.id for section in payload.sections for question in section.questions
    ):
        raise InvalidFormReferenceError("A new form cannot reuse saved structure.")
    form_id = _new_id()
    now = _now()
    try:
        with transaction() as conn:
            _ensure_unique_title(conn, payload.title)
            slug = unique_slug(conn, payload.title)
            # Readable prefix for humans, random suffix so it cannot be guessed.
            # Never regenerated — renaming a form must not break shared links.
            public_ref = f"{slug}-{secrets.token_urlsafe(9)}"
            conn.execute(
                """INSERT INTO forms
                   (id, slug, public_ref, title, description, display_mode, accent,
                    is_published, confirm_msg, meeting_url, meeting_label,
                    created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    form_id,
                    slug,
                    public_ref,
                    payload.title,
                    payload.description,
                    payload.display_mode,
                    payload.accent,
                    payload.is_published,
                    payload.confirm_msg,
                    payload.meeting_url,
                    payload.meeting_label,
                    now,
                    now,
                ),
            )
            _write_structure(conn, form_id, payload)
    except psycopg.errors.UniqueViolation as exc:
        if exc.diag.constraint_name == "idx_forms_title_normalized":
            raise DuplicateFormTitleError(payload.title) from exc
        raise InvalidFormReferenceError(
            "The form contains a conflicting reference."
        ) from exc
    return form_id


def update_form(form_id: str, payload: FormIn) -> None:
    """Replace the form's structure.

    Questions keep their IDs when the client sends them back, so existing
    responses and spreadsheet columns stay attached. Questions that disappear
    are archived rather than deleted.
    """
    try:
        with transaction() as conn:
            existing = conn.execute(
                "SELECT id FROM forms WHERE id = %s", (form_id,)
            ).fetchone()
            if existing is None:
                raise KeyError(form_id)

            _ensure_unique_title(conn, payload.title, exclude_id=form_id)
            kept = {
                q.id for section in payload.sections for q in section.questions if q.id
            }
            section_ids = {section.id for section in payload.sections if section.id}
            _ensure_owned_structure(conn, form_id, kept, section_ids)

            slug = unique_slug(conn, payload.title, exclude_id=form_id)
            conn.execute(
                """UPDATE forms
                      SET slug = %s, title = %s, description = %s,
                          display_mode = %s, accent = %s, is_published = %s,
                          confirm_msg = %s, meeting_url = %s,
                          meeting_label = %s, updated_at = %s
                    WHERE id = %s""",
                (
                    slug,
                    payload.title,
                    payload.description,
                    payload.display_mode,
                    payload.accent,
                    payload.is_published,
                    payload.confirm_msg,
                    payload.meeting_url,
                    payload.meeting_label,
                    _now(),
                    form_id,
                ),
            )

            conn.execute(
                "UPDATE questions SET archived = TRUE WHERE form_id = %s", (form_id,)
            )
            conn.execute("DELETE FROM sections WHERE form_id = %s", (form_id,))
            _write_structure(conn, form_id, payload, reuse_ids=kept)
    except psycopg.errors.UniqueViolation as exc:
        if exc.diag.constraint_name == "idx_forms_title_normalized":
            raise DuplicateFormTitleError(payload.title) from exc
        raise InvalidFormReferenceError(
            "The form contains a conflicting reference."
        ) from exc


def _ensure_unique_title(
    conn: psycopg.Connection, title: str, exclude_id: str = ""
) -> None:
    row = conn.execute(
        """SELECT id FROM forms
            WHERE lower(btrim(title)) = lower(btrim(%s)) AND id <> %s""",
        (title, exclude_id),
    ).fetchone()
    if row is not None:
        raise DuplicateFormTitleError(title)


def _ensure_owned_structure(
    conn: psycopg.Connection,
    form_id: str,
    question_ids: set[str],
    section_ids: set[str],
) -> None:
    if question_ids:
        owned = {
            row["id"]
            for row in conn.execute(
                "SELECT id FROM questions WHERE form_id = %s AND id = ANY(%s)",
                (form_id, list(question_ids)),
            ).fetchall()
        }
        if owned != question_ids:
            raise InvalidFormReferenceError("A question does not belong to this form.")
    if section_ids:
        owned = {
            row["id"]
            for row in conn.execute(
                "SELECT id FROM sections WHERE form_id = %s AND id = ANY(%s)",
                (form_id, list(section_ids)),
            ).fetchall()
        }
        if owned != section_ids:
            raise InvalidFormReferenceError("A section does not belong to this form.")


def _write_structure(
    conn: psycopg.Connection,
    form_id: str,
    payload: FormIn,
    reuse_ids: set[str] | None = None,
) -> None:
    reuse_ids = reuse_ids or set()
    position = 0

    for index, section in enumerate(payload.sections or []):
        section_id = section.id or _new_id()
        conn.execute(
            """INSERT INTO sections (id, form_id, title, description, position)
               VALUES (%s,%s,%s,%s,%s)""",
            (section_id, form_id, section.title, section.description, index),
        )
        for question in section.questions:
            values = (
                question.type,
                question.label,
                question.help_text,
                question.placeholder,
                question.required,
                Jsonb(question.options),
                Jsonb(question.config),
                position,
                section_id,
            )
            if question.id in reuse_ids:
                conn.execute(
                    """UPDATE questions
                          SET type = %s, label = %s, help_text = %s, placeholder = %s,
                              required = %s, options = %s, config = %s, position = %s,
                              section_id = %s, archived = FALSE
                        WHERE id = %s AND form_id = %s""",
                    (*values, question.id, form_id),
                )
            else:
                conn.execute(
                    """INSERT INTO questions
                       (id, form_id, type, label, help_text, placeholder,
                        required, options, config, position, section_id, archived)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,FALSE)""",
                    (_new_id(), form_id, *values),
                )
            position += 1


def delete_form(form_id: str) -> None:
    with transaction() as conn:
        conn.execute("DELETE FROM forms WHERE id = %s", (form_id,))


def set_sheet(form_id: str, sheet_id: str, sheet_url: str, error: str = "") -> None:
    with transaction() as conn:
        conn.execute(
            """UPDATE forms SET sheet_id = %s, sheet_url = %s, sheet_error = %s
                WHERE id = %s""",
            (sheet_id or None, sheet_url or None, error or None, form_id),
        )
        if sheet_id:
            # A newly linked (or deliberately replaced) spreadsheet needs a
            # complete backfill. Responses may have been collected while
            # Google was disconnected, so never trust their previous sync bit.
            conn.execute(
                """UPDATE responses SET synced = FALSE, sync_error = NULL
                    WHERE form_id = %s""",
                (form_id,),
            )


def set_sheet_error(form_id: str, error: str = "") -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE forms SET sheet_error = %s WHERE id = %s",
            (error or None, form_id),
        )


def save_response(form_id: str, answers: dict[str, Any]) -> str:
    response_id = _new_id()
    with transaction() as conn:
        conn.execute(
            """INSERT INTO responses (id, form_id, submitted_at, payload, synced)
               VALUES (%s,%s,%s,%s,FALSE)""",
            (response_id, form_id, _now(), Jsonb(answers)),
        )
    return response_id


def update_response(
    form_id: str, response_id: str, answers: dict[str, Any]
) -> dict[str, Any] | None:
    """Merge later metadata into one response and queue its Sheet row again."""
    with transaction() as conn:
        return conn.execute(
            """UPDATE responses
                  SET payload = payload || %s,
                      synced = FALSE,
                      sync_error = NULL
                WHERE id = %s AND form_id = %s
            RETURNING *""",
            (Jsonb(answers), response_id, form_id),
        ).fetchone()


def mark_synced(response_id: str, error: str = "") -> None:
    with transaction() as conn:
        conn.execute(
            "UPDATE responses SET synced = %s, sync_error = %s WHERE id = %s",
            (not error, error or None, response_id),
        )


def list_responses(form_id: str, limit: int = 500) -> list[dict[str, Any]]:
    with readonly() as conn:
        return conn.execute(
            """SELECT * FROM responses WHERE form_id = %s
                ORDER BY submitted_at DESC LIMIT %s""",
            (form_id, limit),
        ).fetchall()


def pending_sync(limit: int = 50, form_id: str = "") -> list[dict[str, Any]]:
    with readonly() as conn:
        return conn.execute(
            """SELECT r.* FROM responses r
                JOIN forms f ON f.id = r.form_id
               WHERE NOT r.synced AND f.sheet_id IS NOT NULL
                 AND (%s = '' OR r.form_id = %s)
               ORDER BY r.submitted_at LIMIT %s""",
            (form_id, form_id, limit),
        ).fetchall()
