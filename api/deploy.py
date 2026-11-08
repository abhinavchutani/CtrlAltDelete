"""Deployment helpers (Render / Docker): serve the built React app and an optional shared password.

Both do nothing in local dev: `mount_web` needs `web/dist/` (made by `npm run build`), and the password gate is added
in api/main.py only when `APP_PASSWORD` is set.
"""
from __future__ import annotations

import base64
import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.db import REPO_ROOT

WEB_DIST = REPO_ROOT / "web" / "dist"
OPEN_PATHS = ("/api/health",)  # the host's health check must pass without the password


def mount_web(app: FastAPI, dist: Path = WEB_DIST) -> bool:
    """Serve dist/assets as static files and every other non-/api GET as index.html (the SPA routes)."""
    index = dist / "index.html"
    if not index.exists():
        return False
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404, "not found")
        f = (dist / path).resolve()
        if path and f.is_file() and f.is_relative_to(dist.resolve()):
            return FileResponse(f)  # public/ files such as the logo
        return FileResponse(index)
    return True


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """One shared password for the whole app (any user name). Keeps a public URL from spending the LLM quota."""

    def __init__(self, app, password: str) -> None:
        super().__init__(app)
        self.password = password

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in OPEN_PATHS or self._ok(request.headers.get("authorization", "")):
            return await call_next(request)
        return Response("Password required", status_code=401,
                        headers={"WWW-Authenticate": 'Basic realm="Field Radar"'})

    def _ok(self, header: str) -> bool:
        if not header.startswith("Basic "):
            return False
        try:
            _, _, pw = base64.b64decode(header[6:]).decode().partition(":")
        except Exception:  # noqa: BLE001 — a malformed header is just a failed login
            return False
        return secrets.compare_digest(pw, self.password)
