"""Password forgot/reset web UI — mirrors AI\\PasswordViewController.

Any signed-in user may use this. The generated reset token is shown on screen
(the Laravel API would e-mail it)."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_web_user
from app.auth.models import User
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.core.templating import flash, flash_errors, render

router = APIRouter(prefix="/password", tags=["web-password"])


@router.get("")
def index(request: Request, user: User = Depends(require_web_user)):
    token = request.session.pop("_reset_token", None)
    return render(request, "password/index.html", {"token": token}, user=user)


@router.post("/forgot")
def forgot(request: Request, email: str = Form(...), user: User = Depends(require_web_user), db: Session = Depends(get_db)):
    target = db.scalar(select(User).where(User.email == email))
    if not target:
        flash(request, "We cannot find a user with that email address.", "error")
        return RedirectResponse("/password", status_code=303)

    request.session["_reset_token"] = create_access_token(target.id)
    flash(request, "Password reset token generated (the API would e-mail this).")
    return RedirectResponse("/password", status_code=303)


@router.post("/reset")
def reset(
    request: Request,
    email: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    user: User = Depends(require_web_user),
    db: Session = Depends(get_db),
):
    if new_password != confirm_password:
        flash_errors(request, ["Passwords do not match."], {"email": email})
        return RedirectResponse("/password", status_code=303)

    target = db.scalar(select(User).where(User.email == email))
    if not target:
        flash(request, "Cannot find a user with this email address.", "error")
        return RedirectResponse("/password", status_code=303)

    target.password = hash_password(new_password)
    db.commit()
    flash(request, "Password reset successful!")
    return RedirectResponse("/password", status_code=303)
