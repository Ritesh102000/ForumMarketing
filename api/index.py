"""Vercel entrypoint.

Vercel's Python runtime serves any ASGI app exported as `app` from a file under
`api/`. Everything else — routing, static files, templates — is the same code
that runs locally.

This deploys the PUBLIC role: form rendering and submission only. The admin
surface is never registered here, so there is no login page on the internet.
Deploying with FORMCRAFT_ROLE=admin is refused below rather than silently
publishing the builder.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("FORMCRAFT_ROLE", "public")
os.environ.setdefault("FORMCRAFT_SERVERLESS", "1")

from formcraft.config import settings  # noqa: E402

if settings.is_admin_role:
    raise RuntimeError(
        "Refusing to start: FORMCRAFT_ROLE is 'admin' on a serverless host. "
        "The admin surface is meant to run only on your own machine. "
        "Set FORMCRAFT_ROLE=public in the Vercel project's environment variables."
    )

from formcraft.app import app  # noqa: E402

__all__ = ["app"]
