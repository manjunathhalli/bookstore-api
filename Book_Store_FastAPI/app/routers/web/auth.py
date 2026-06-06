"""Session-based auth for the web UI — mirrors AI\\AuthController."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import get_optional_web_user
from ...models import User
from ...security import hash_password, verify_password
from ...templating import flash, flash_errors, render

router = APIRouter(tags=["web-auth"])


@router.get("/")
def home():
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/login")
def show_login(request: Request, user: User | None = Depends(get_optional_web_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "auth/login.html")


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(password, user.password):
        flash_errors(request, [], {"email": email})
        flash(request, "Invalid email or password.", "error")
        return RedirectResponse("/login", status_code=303)

    request.session["user_id"] = user.id
    flash(request, f"Welcome back, {user.first_name}!")
    return RedirectResponse("/dashboard", status_code=303)


@router.get("/register")
def show_register(request: Request, user: User | None = Depends(get_optional_web_user)):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return render(request, "auth/register.html")


@router.post("/register")
def register(
    request: Request,
    role: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    phone_no: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    errors = []
    if role not in ("user", "admin"):
        errors.append("Account type must be user or admin.")
    if len(password) < 6:
        errors.append("Password must be at least 6 characters.")
    if password != confirm_password:
        errors.append("Passwords do not match.")
    if db.scalar(select(User).where(User.email == email)):
        errors.append("The email has already been taken.")

    if errors:
        flash_errors(request, errors, {
            "role": role, "first_name": first_name, "last_name": last_name,
            "phone_no": phone_no, "email": email,
        })
        return RedirectResponse("/register", status_code=303)

    user = User(
        role=role, first_name=first_name, last_name=last_name,
        phone_no=phone_no, email=email, password=hash_password(password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    request.session["user_id"] = user.id
    flash(request, f"Account created — you are now signed in as {user.role}.")
    return RedirectResponse("/dashboard", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    flash(request, "You have been logged out.")
    return RedirectResponse("/login", status_code=303)
