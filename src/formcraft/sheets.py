"""Google Sheets sync.

Every form gets its own spreadsheet, created when the form is created. Each
question owns a stable column index, so adding or removing questions later
never shifts existing data.

The whole module degrades to no-ops when FORMCRAFT_GOOGLE_ENABLED is off, so
the app is fully usable without any Google setup.
"""

from __future__ import annotations

import contextlib
import json
import threading
from datetime import UTC, datetime
from typing import Any

from .config import settings
from .db import readonly, transaction

# drive.file only. It is a NON-SENSITIVE scope, so the OAuth app can be
# published to Production without a Google verification review — which in turn
# means the refresh token does not expire after 7 days. The Sheets API accepts
# it for files the app itself created, which is all we ever touch.
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

TIMESTAMP_HEADER = "Submitted at"
RESPONSE_ID_HEADER = "Formcraft response ID"
RESPONSE_ID_KEY = "__formcraft_response_id__"

_lock = threading.Lock()
_service: Any = None


class SheetsUnavailable(RuntimeError):
    """Raised when Sheets is enabled but not usable."""


def enabled() -> bool:
    return settings.google_enabled


def _column_letter(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA."""
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _load_service() -> Any:
    global _service
    with _lock:
        if _service is not None:
            return _service

        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        payload = _token_source()
        if payload is None:
            raise SheetsUnavailable(
                "Google is enabled but no credentials were found. Run "
                "`uv run python scripts/google_setup.py` locally, or set "
                "FORMCRAFT_GOOGLE_TOKEN_JSON when deploying."
            )

        creds = Credentials.from_authorized_user_info(payload, SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Read-only filesystem on serverless hosts: refreshing in memory
                # is enough, the refresh token itself does not change.
                if not settings.serverless and settings.google_token_file.exists():
                    with contextlib.suppress(OSError):
                        settings.google_token_file.write_text(creds.to_json())
            else:
                raise SheetsUnavailable(
                    "Google credentials are invalid. Re-run scripts/google_setup.py"
                )

        _service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        return _service


def _read_columns(form_id: str) -> dict[str, int]:
    with readonly() as conn:
        rows = conn.execute(
            "SELECT question_id, col_index FROM sheet_columns WHERE form_id = %s",
            (form_id,),
        ).fetchall()
    return {row["question_id"]: row["col_index"] for row in rows}


def _submitted_label(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat(timespec="seconds")
    return str(value)


def _write_columns(form_id: str, mapping: dict[str, int]) -> None:
    with transaction() as conn:
        conn.cursor().executemany(
            """INSERT INTO sheet_columns (form_id, question_id, col_index)
               VALUES (%s,%s,%s)
               ON CONFLICT (form_id, question_id)
               DO UPDATE SET col_index = EXCLUDED.col_index""",
            [(form_id, qid, idx) for qid, idx in mapping.items()],
        )


def create_spreadsheet(form: dict[str, Any]) -> tuple[str, str]:
    """Create the spreadsheet for a form and write its header row."""
    if not enabled():
        return "", ""

    service = _load_service()
    questions = form.get("sheet_questions", form["questions"])

    created = (
        service.spreadsheets()
        .create(
            body={
                "properties": {"title": f"{form['title']} — responses"},
                "sheets": [{"properties": {"title": "Responses"}}],
            },
            fields="spreadsheetId,spreadsheetUrl",
        )
        .execute()
    )
    sheet_id = created["spreadsheetId"]
    sheet_url = created["spreadsheetUrl"]

    header = [TIMESTAMP_HEADER] + [_header_label(q) for q in questions]
    mapping = {q["id"]: index + 1 for index, q in enumerate(questions)}
    response_id_index = len(header)
    mapping[RESPONSE_ID_KEY] = response_id_index
    header.append(RESPONSE_ID_HEADER)

    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"Responses!A1:{_column_letter(len(header) - 1)}1",
        valueInputOption="RAW",
        body={"values": [header]},
    ).execute()

    _format_sheet(service, sheet_id, response_id_index)
    _write_columns(form["id"], mapping)
    return sheet_id, sheet_url


def _format_sheet(service: Any, sheet_id: str, response_id_index: int) -> None:
    # Cosmetic only — never let this block sheet creation.
    with contextlib.suppress(Exception):
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={
                "requests": [
                    {
                        "updateSheetProperties": {
                            "properties": {
                                "sheetId": 0,
                                "gridProperties": {"frozenRowCount": 1},
                            },
                            "fields": "gridProperties.frozenRowCount",
                        }
                    },
                    {
                        "repeatCell": {
                            "range": {"sheetId": 0, "endRowIndex": 1},
                            "cell": {
                                "userEnteredFormat": {
                                    "textFormat": {"bold": True},
                                }
                            },
                            "fields": "userEnteredFormat.textFormat.bold",
                        }
                    },
                    {
                        "updateDimensionProperties": {
                            "range": {
                                "sheetId": 0,
                                "dimension": "COLUMNS",
                                "startIndex": response_id_index,
                                "endIndex": response_id_index + 1,
                            },
                            "properties": {"hiddenByUser": True},
                            "fields": "hiddenByUser",
                        }
                    },
                ]
            },
        ).execute()


def _header_label(question: dict[str, Any]) -> str:
    suffix = " (removed)" if question.get("archived") else ""
    return f"{question['label']}{suffix}"


def _ensure_response_id_column(
    service: Any, form: dict[str, Any], mapping: dict[str, int]
) -> dict[str, int]:
    """Add the private idempotency column to spreadsheets from older releases."""
    if RESPONSE_ID_KEY in mapping:
        return mapping

    index = max(mapping.values(), default=0) + 1
    service.spreadsheets().values().update(
        spreadsheetId=form["sheet_id"],
        range=f"Responses!{_column_letter(index)}1",
        valueInputOption="RAW",
        body={"values": [[RESPONSE_ID_HEADER]]},
    ).execute()
    mapping[RESPONSE_ID_KEY] = index
    _write_columns(form["id"], {RESPONSE_ID_KEY: index})

    with contextlib.suppress(Exception):
        service.spreadsheets().batchUpdate(
            spreadsheetId=form["sheet_id"],
            body={
                "requests": [
                    {
                        "updateDimensionProperties": {
                            "range": {
                                "sheetId": 0,
                                "dimension": "COLUMNS",
                                "startIndex": index,
                                "endIndex": index + 1,
                            },
                            "properties": {"hiddenByUser": True},
                            "fields": "hiddenByUser",
                        }
                    }
                ]
            },
        ).execute()
    return mapping


def _ensure_columns(
    service: Any, form: dict[str, Any], questions: list[dict[str, Any]]
) -> dict[str, int]:
    """Assign columns to any question added after the sheet was created."""
    mapping = _read_columns(form["id"])
    mapping = _ensure_response_id_column(service, form, mapping)
    missing = [q for q in questions if q["id"] not in mapping]
    if not missing:
        return mapping

    next_index = max(mapping.values(), default=0) + 1
    additions: dict[str, int] = {}
    header_cells: list[str] = []
    for question in missing:
        additions[question["id"]] = next_index
        header_cells.append(_header_label(question))
        next_index += 1

    start = _column_letter(min(additions.values()))
    end = _column_letter(max(additions.values()))
    service.spreadsheets().values().update(
        spreadsheetId=form["sheet_id"],
        range=f"Responses!{start}1:{end}1",
        valueInputOption="RAW",
        body={"values": [header_cells]},
    ).execute()

    mapping.update(additions)
    _write_columns(form["id"], additions)
    return mapping


def sync_spreadsheet(form: dict[str, Any]) -> None:
    """Synchronize a form title and question headers after an admin edit."""
    if not enabled() or not form.get("sheet_id"):
        return

    service = _load_service()
    questions = form.get("sheet_questions", form["questions"])
    mapping = _ensure_columns(service, form, questions)

    data = [
        {
            "range": "Responses!A1",
            "values": [[TIMESTAMP_HEADER]],
        },
        {
            "range": f"Responses!{_column_letter(mapping[RESPONSE_ID_KEY])}1",
            "values": [[RESPONSE_ID_HEADER]],
        },
    ]
    data.extend(
        {
            "range": f"Responses!{_column_letter(mapping[q['id']])}1",
            "values": [[_header_label(q)]],
        }
        for q in questions
    )
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=form["sheet_id"],
        body={"valueInputOption": "RAW", "data": data},
    ).execute()
    service.spreadsheets().batchUpdate(
        spreadsheetId=form["sheet_id"],
        body={
            "requests": [
                {
                    "updateSpreadsheetProperties": {
                        "properties": {"title": f"{form['title']} — responses"},
                        "fields": "title",
                    }
                }
            ]
        },
    ).execute()


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def append_response(
    form: dict[str, Any],
    response_id: str,
    answers: dict[str, Any],
    submitted_at: Any = None,
) -> None:
    """Append one response row. Raises on failure so the caller can retry."""
    if not enabled() or not form.get("sheet_id"):
        return

    service = _load_service()
    questions = form.get("sheet_questions", form["questions"])
    mapping = _ensure_columns(service, form, questions)

    response_id_index = mapping[RESPONSE_ID_KEY]
    response_id_column = _column_letter(response_id_index)
    existing = (
        service.spreadsheets()
        .values()
        .get(
            spreadsheetId=form["sheet_id"],
            range=f"Responses!{response_id_column}2:{response_id_column}",
        )
        .execute()
        .get("values", [])
    )
    if any(row and row[0] == response_id for row in existing):
        return

    width = max(mapping.values(), default=0) + 1
    row: list[str] = [""] * width
    row[0] = _submitted_label(
        submitted_at or datetime.now(UTC).isoformat(timespec="seconds")
    )
    row[response_id_index] = response_id
    for question_id, value in answers.items():
        index = mapping.get(question_id)
        if index is not None and index < width:
            row[index] = _format_value(value)

    service.spreadsheets().values().append(
        spreadsheetId=form["sheet_id"],
        range="Responses!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()


def status_summary() -> dict[str, Any]:
    """Small health blob for the admin dashboard."""
    if not enabled():
        return {"enabled": False, "ready": False, "detail": "Google sync is off."}
    try:
        _load_service()
    except SheetsUnavailable as exc:
        return {"enabled": True, "ready": False, "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001
        detail = f"{type(exc).__name__}: {exc}"
        return {"enabled": True, "ready": False, "detail": detail}
    return {"enabled": True, "ready": True, "detail": "Connected."}


def _token_source() -> dict[str, Any] | None:
    """Env var first (Vercel), then the local file (your Mac)."""
    if settings.google_token_json:
        try:
            return json.loads(settings.google_token_json)
        except json.JSONDecodeError as exc:
            raise SheetsUnavailable(
                f"FORMCRAFT_GOOGLE_TOKEN_JSON is not valid JSON: {exc}"
            ) from exc
    if settings.google_token_file.exists():
        try:
            return json.loads(settings.google_token_file.read_text())
        except (OSError, json.JSONDecodeError):
            return None
    return None


token_payload = _token_source
