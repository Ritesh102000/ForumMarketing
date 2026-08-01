"""Guided Google authorisation, with verification.

This does everything except the two things that need your Google password:
creating the OAuth client in the Cloud Console, and clicking Allow. It walks
you through those, runs the flow, then proves the result works by creating a
real spreadsheet and deleting it again.

Finally it prints the one-line token blob to paste into Vercel.

    uv run python scripts/google_setup.py
"""

from __future__ import annotations

import contextlib
import json
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from formcraft.config import settings  # noqa: E402
from formcraft.sheets import SCOPES  # noqa: E402

CONSOLE = "https://console.cloud.google.com"

CHECKLIST = f"""
Do these once in the Google Cloud Console. They need your Google password,
so they are yours to click — everything after is automatic.

  1. {CONSOLE}/projectcreate
     Create a project (any name).

  2. {CONSOLE}/apis/library/drive.googleapis.com
     Enable the Google Drive API.

  3. {CONSOLE}/apis/library/sheets.googleapis.com
     Enable the Google Sheets API.

  4. {CONSOLE}/auth/branding
     Fill in the app name and your email.

  5. {CONSOLE}/auth/audience
     Set publishing status to PRODUCTION, not Testing.

     This matters: in Testing, Google expires the refresh token after 7 days
     and your deployment silently stops syncing. We only request the
     non-sensitive drive.file scope, so Production needs no review — the
     "unverified app" notice on the consent screen is expected and fine for
     your own account.

  6. {CONSOLE}/auth/clients
     Create client → Desktop app → download the JSON.

  7. Save that file to:
     {settings.google_client_secret_file}
"""


def _fail(message: str) -> int:
    print(f"\n✗ {message}")
    return 1


def main() -> int:  # noqa: C901 - a linear setup script reads better flat
    secret_file = settings.google_client_secret_file

    if not secret_file.exists():
        print(CHECKLIST)
        answer = input("Open the console in your browser now? [Y/n] ").strip().lower()
        if answer in ("", "y", "yes"):
            webbrowser.open(f"{CONSOLE}/projectcreate")
        print(f"\nRe-run this script once {secret_file} exists.")
        return 1

    try:
        client = json.loads(secret_file.read_text())
    except json.JSONDecodeError as exc:
        return _fail(f"{secret_file} is not valid JSON: {exc}")

    if "installed" not in client and "web" not in client:
        return _fail(
            f"{secret_file} does not look like an OAuth client file. "
            "Create credentials of type 'Desktop app' and download that JSON."
        )
    if "web" in client:
        print(
            "! This is a Web application client. A Desktop app client is easier "
            "here — if the browser step fails, create one of those instead.\n"
        )

    print(f"Requesting scope: {', '.join(SCOPES)}")
    print("A browser window will open. Sign in and click Allow.\n")

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), SCOPES)
    try:
        creds = flow.run_local_server(port=0, prompt="consent", open_browser=True)
    except Exception as exc:  # noqa: BLE001
        return _fail(f"Authorisation failed: {exc}")

    if not creds.refresh_token:
        return _fail(
            "Google returned no refresh token. Revoke the app at "
            "https://myaccount.google.com/permissions and run this again."
        )

    settings.google_token_file.parent.mkdir(parents=True, exist_ok=True)
    settings.google_token_file.write_text(creds.to_json())
    settings.google_token_file.chmod(0o600)
    print(f"✓ Token saved to {settings.google_token_file}")

    # --- prove it actually works -------------------------------------------
    print("\nVerifying by creating a real spreadsheet…")
    from googleapiclient.discovery import build

    try:
        sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
        created = (
            sheets.spreadsheets()
            .create(
                body={"properties": {"title": "Formcraft — setup check"}},
                fields="spreadsheetId,spreadsheetUrl",
            )
            .execute()
        )
        sheet_id = created["spreadsheetId"]
        sheets.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="Sheet1!A1:B1",
            valueInputOption="RAW",
            body={"values": [["Formcraft", "works"]]},
        ).execute()
        print(f"✓ Created and wrote to {created['spreadsheetUrl']}")

        drive = build("drive", "v3", credentials=creds, cache_discovery=False)
        with contextlib.suppress(Exception):
            drive.files().delete(fileId=sheet_id).execute()
            print("✓ Test spreadsheet deleted")
    except Exception as exc:  # noqa: BLE001
        return _fail(
            f"Authorisation succeeded but the API call failed: {exc}\n"
            "  Most often this means the Sheets or Drive API is not enabled "
            "(steps 2 and 3 above)."
        )

    # --- deployment blob ----------------------------------------------------
    blob = json.dumps(json.loads(creds.to_json()), separators=(",", ":"))
    print("\n" + "─" * 72)
    print("Local setup is done. Set FORMCRAFT_GOOGLE_ENABLED=1 in .env.")
    print("\nFor Vercel, add this environment variable:\n")
    print("  FORMCRAFT_GOOGLE_TOKEN_JSON")
    print(f"  {blob}\n")
    print("Or from the CLI:")
    print("  vercel env add FORMCRAFT_GOOGLE_TOKEN_JSON production")
    print("─" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
