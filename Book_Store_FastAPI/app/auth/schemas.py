"""Auth schemas for the JWT REST API (mirrors the Laravel API validation)."""

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    role: str = Field(pattern="^(user|admin)$")
    first_name: str = Field(min_length=2, max_length=50)
    last_name: str = Field(min_length=2, max_length=50)
    phone_no: str = Field(min_length=10)
    email: EmailStr = Field(max_length=100)
    password: str = Field(min_length=6)
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if v != info.data.get("password"):
            raise ValueError("confirm_password must match password")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(max_length=100)


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=6)
    confirm_password: str

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if v != info.data.get("new_password"):
            raise ValueError("confirm_password must match new_password")
        return v
