"""JWT auth + forgot/reset password — mirrors UserController &
ForgotPasswordController from the Laravel API."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import get_current_api_user
from ...models import User
from ...schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from ...security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "The email has already been taken")

    user = User(
        role=payload.role,
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone_no=payload.phone_no,
        email=payload.email,
        password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"status": 201, "message": "User successfully registered", "user_id": user.id}


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600}


@router.post("/logout")
def logout(_: User = Depends(get_current_api_user)):
    # JWT is stateless; the client simply discards the token.
    return {"status": 200, "message": "User successfully logged out"}


@router.post("/forgotPassword")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "we can not find the user with that e-mail address")

    token = create_access_token(user.id)
    # The Laravel API e-mails this token; here we return it directly.
    return {"status": 200, "message": "Password reset token generated", "token": token}


@router.post("/resetPassword")
def reset_password(
    payload: ResetPasswordRequest,
    user: User = Depends(get_current_api_user),
    db: Session = Depends(get_db),
):
    user.password = hash_password(payload.new_password)
    db.commit()
    return {"status": 201, "message": "Password reset successful!"}
