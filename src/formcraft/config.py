"""Runtime settings, loaded once from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _path(name: str, default: str) -> Path:
    raw = os.getenv(name, default)
    candidate = Path(raw)
    return candidate if candidate.is_absolute() else ROOT / candidate


@dataclass(frozen=True)
class Settings:
    root: Path
    database_url: str
    db_pool_size: int
    web_dir: Path
    role: str
    admin_allow_remote: bool
    brand_name: str
    owner_name: str
    owner_role: str
    serverless: bool
    admin_username: str
    admin_password_hash: str
    secret_key: str
    base_url: str
    secure_cookies: bool
    google_enabled: bool
    google_client_secret_file: Path
    google_token_file: Path
    google_token_json: str

    @property
    def is_admin_role(self) -> bool:
        return self.role == "admin"

    @property
    def is_configured(self) -> bool:
        """Public instances need no credentials — they only render forms."""
        if not self.database_url:
            return False
        if not self.is_admin_role:
            return True
        return bool(self.admin_password_hash and self.secret_key)


def load_settings() -> Settings:
    role = os.getenv("FORMCRAFT_ROLE", "admin").strip().lower()
    if role not in {"admin", "public"}:
        raise ValueError(f"FORMCRAFT_ROLE must be 'admin' or 'public', got {role!r}")

    return Settings(
        root=ROOT,
        database_url=os.getenv("FORMCRAFT_DATABASE_URL", "").strip(),
        db_pool_size=int(os.getenv("FORMCRAFT_DB_POOL_SIZE", "5")),
        web_dir=ROOT / "web",
        role=role,
        admin_allow_remote=_flag("FORMCRAFT_ADMIN_ALLOW_REMOTE"),
        brand_name=os.getenv("FORMCRAFT_BRAND_NAME", "Formcraft").strip(),
        owner_name=os.getenv("FORMCRAFT_OWNER_NAME", "").strip(),
        owner_role=os.getenv("FORMCRAFT_OWNER_ROLE", "").strip(),
        # Vercel and most FaaS hosts set VERCEL / AWS_LAMBDA_FUNCTION_NAME.
        serverless=_flag("FORMCRAFT_SERVERLESS")
        or bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME")),
        admin_username=os.getenv("FORMCRAFT_ADMIN_USERNAME", "admin").strip(),
        admin_password_hash=os.getenv("FORMCRAFT_ADMIN_PASSWORD_HASH", "").strip(),
        secret_key=os.getenv("FORMCRAFT_SECRET_KEY", "").strip(),
        base_url=os.getenv("FORMCRAFT_BASE_URL", "http://127.0.0.1:8480").rstrip("/"),
        secure_cookies=_flag("FORMCRAFT_SECURE_COOKIES"),
        google_enabled=_flag("FORMCRAFT_GOOGLE_ENABLED"),
        google_client_secret_file=_path(
            "FORMCRAFT_GOOGLE_CLIENT_SECRET_FILE", "data/google_client_secret.json"
        ),
        google_token_file=_path(
            "FORMCRAFT_GOOGLE_TOKEN_FILE", "data/google_token.json"
        ),
        google_token_json=os.getenv("FORMCRAFT_GOOGLE_TOKEN_JSON", "").strip(),
    )


settings = load_settings()
