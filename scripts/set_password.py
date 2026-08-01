"""Generate the admin password hash and secret key, and write them into .env."""

from __future__ import annotations

import getpass
import os
import re
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# When the checkout is linked to Vercel, its marketplace integrations are
# pulled here. Import only the standard DATABASE_URL into the local admin .env;
# the remaining Vercel variables belong to the deployed public service.
load_dotenv(ROOT / ".env.local", override=False)

from formcraft.auth import hash_password  # noqa: E402

ENV = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"


def upsert(text: str, key: str, value: str) -> str:
    line = f"{key}={value}"
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(line, text)
    return text.rstrip("\n") + f"\n{line}\n"


def main() -> int:
    if not ENV.exists():
        if not EXAMPLE.exists():
            print("No .env.example found.")
            return 1
        ENV.write_text(EXAMPLE.read_text())
        print("Created .env from .env.example")

    text = ENV.read_text()

    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        text = upsert(text, "FORMCRAFT_DATABASE_URL", database_url)
        print("Connected the local admin to the Vercel Postgres database.")

    username = input("Admin username [admin]: ").strip() or "admin"
    password = getpass.getpass("Admin password: ")
    if len(password) < 8:
        print("Password must be at least 8 characters.")
        return 1
    if password != getpass.getpass("Confirm password: "):
        print("Passwords do not match.")
        return 1

    text = upsert(text, "FORMCRAFT_ADMIN_USERNAME", username)
    text = upsert(text, "FORMCRAFT_ADMIN_PASSWORD_HASH", hash_password(password))

    if not re.search(r"^FORMCRAFT_SECRET_KEY=.+$", text, re.MULTILINE):
        text = upsert(text, "FORMCRAFT_SECRET_KEY", secrets.token_urlsafe(48))
        print("Generated a new FORMCRAFT_SECRET_KEY.")

    ENV.write_text(text)
    print(f"\nSaved. Admin user is '{username}'.")
    print("Start the server with: uv run python scripts/run.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
