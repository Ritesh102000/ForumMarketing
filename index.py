"""Vercel entrypoint for the public Formcraft service.

Vercel's current FastAPI runtime detects a root ``index.py`` and routes the
deployment domain directly to the exported ASGI application. The admin surface
is intentionally unavailable in this deployment.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

os.environ.setdefault("FORMCRAFT_ROLE", "public")
os.environ.setdefault("FORMCRAFT_SERVERLESS", "1")

from formcraft.config import settings  # noqa: E402

if settings.is_admin_role:
    raise RuntimeError(
        "Refusing to start: FORMCRAFT_ROLE is 'admin' on a serverless host. "
        "Set FORMCRAFT_ROLE=public in the Vercel project."
    )

from formcraft.app import app  # noqa: E402

__all__ = ["app"]
