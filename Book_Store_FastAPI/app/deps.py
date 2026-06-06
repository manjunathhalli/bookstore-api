"""Shared dependencies: authentication & role guards for both the JWT API
and the session-based web UI.

Roles mirror the Laravel app:
  - admin : manages the catalogue (Books CRUD/stock) and views Users.
  - user  : shops — Cart, Wishlist, Address, Orders, Feedback.
  - both  : Dashboard, browse Books, change own Password.
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import decode_access_token

# --------------------------------------------------------------------------- #
# Web (session) redirect handling
# --------------------------------------------------------------------------- #


class RedirectException(Exception):
    """Raised inside web dependencies/handlers to trigger a redirect with an
    optional flash message (handled in main.py)."""

    def __init__(self, url: str, error: str | None = None, status: str | None = None):
        self.url = url
        self.error = error
        self.status = status


# --------------------------------------------------------------------------- #
# JWT API authentication
# --------------------------------------------------------------------------- #

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_api_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authorization token not found")
    sub = decode_access_token(credentials.credentials)
    if sub is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, int(sub))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def require_api_role(role: str):
    def checker(user: User = Depends(get_current_api_user)) -> User:
        if user.role != role:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Only {role}s are allowed to do this")
        return user

    return checker


# --------------------------------------------------------------------------- #
# Web (session) authentication
# --------------------------------------------------------------------------- #


def get_optional_web_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, int(user_id))


def require_web_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_optional_web_user(request, db)
    if user is None:
        raise RedirectException("/login", error="Please sign in to continue.")
    return user


def require_web_role(role: str):
    def checker(user: User = Depends(require_web_user)) -> User:
        if user.role != role:
            raise RedirectException("/dashboard", error="You are not allowed to access that area.")
        return user

    return checker
