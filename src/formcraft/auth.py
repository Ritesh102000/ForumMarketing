"""Single-admin authentication.

There is exactly one account. Credentials live in the environment, not the
database, so there is no signup path and no way to create a second admin.
"""

from __future__ import annotations

import hmac
import time

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import settings

SESSION_COOKIE = "formcraft_session"
SESSION_MAX_AGE = 60 * 60 * 12  # 12 hours

_hasher = PasswordHasher()

# Login throttle: per-process, which is all a single-admin app needs.
_attempts: list[float] = []
_MAX_ATTEMPTS = 8
_WINDOW_SECONDS = 300


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def _serializer() -> URLSafeTimedSerializer:
    if not settings.secret_key:
        raise RuntimeError(
            "FORMCRAFT_SECRET_KEY is not set. Copy .env.example to .env and fill it in."
        )
    return URLSafeTimedSerializer(settings.secret_key, salt="formcraft-session")


def throttled() -> bool:
    now = time.time()
    _attempts[:] = [t for t in _attempts if now - t < _WINDOW_SECONDS]
    return len(_attempts) >= _MAX_ATTEMPTS


def record_failure() -> None:
    _attempts.append(time.time())


def clear_failures() -> None:
    _attempts.clear()


def verify_credentials(username: str, password: str) -> bool:
    """Constant-time-ish check of the single admin credential pair."""
    if not settings.admin_password_hash:
        raise RuntimeError(
            "No admin password configured. Run: uv run python scripts/set_password.py"
        )
    username_ok = hmac.compare_digest(username.strip(), settings.admin_username)
    try:
        _hasher.verify(settings.admin_password_hash, password)
    except (VerifyMismatchError, Exception):  # noqa: B014 - argon2 raises several
        return False
    return username_ok


def issue_session() -> str:
    return _serializer().dumps({"sub": settings.admin_username})


def read_session(request: Request) -> bool:
    # A public-role instance has no signing key and therefore no sessions.
    if not settings.secret_key:
        return False
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return False
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return False
    return data.get("sub") == settings.admin_username


def require_admin(request: Request) -> None:
    """FastAPI dependency guarding every admin route."""
    if not read_session(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin login required"
        )
