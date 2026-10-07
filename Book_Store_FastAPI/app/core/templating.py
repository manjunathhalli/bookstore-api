"""Jinja2 template configuration, flash messaging and a render() helper.

Flash messages and "old input" / validation errors are stashed in the signed
session cookie (the PRG pattern used by the Laravel/Blade frontend) and popped
on the next render.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import settings

if TYPE_CHECKING:
    from app.auth.models import User

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# --------------------------------------------------------------------------- #
# Flash helpers
# --------------------------------------------------------------------------- #


def flash(request: Request, message: str, category: str = "status") -> None:
    """Queue a one-off message (category: 'status' or 'error')."""
    request.session.setdefault("_flash", {})[category] = message


def flash_errors(request: Request, errors: list[str], old: dict[str, Any] | None = None) -> None:
    """Queue validation errors plus the submitted values to repopulate a form."""
    request.session["_errors"] = errors
    request.session["_old"] = old or {}


def _pop(request: Request, key: str, default: Any):
    value = request.session.pop(key, default)
    return value


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #


def render(
    request: Request,
    template: str,
    context: dict[str, Any] | None = None,
    *,
    user: User | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    flash_messages = _pop(request, "_flash", {})
    base = {
        "app_name": settings.app_name,
        "current_user": user,
        "status": flash_messages.get("status"),
        "error": flash_messages.get("error"),
        "errors": _pop(request, "_errors", []),
        "old": _pop(request, "_old", {}),
    }
    if context:
        base.update(context)
    return templates.TemplateResponse(request, template, base, status_code=status_code)
