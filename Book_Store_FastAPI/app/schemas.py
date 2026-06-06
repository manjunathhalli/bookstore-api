"""Pydantic schemas for the JWT REST API (mirrors the Laravel API validation)."""

from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic import ConfigDict


# --------------------------------------------------------------------------- #
# Users / auth
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# Books
# --------------------------------------------------------------------------- #


class BookCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=5, max_length=1000)
    author: str = Field(min_length=5, max_length=300)
    image: str
    price: float = Field(ge=0, alias="Price")
    quantity: int = Field(ge=0)

    model_config = ConfigDict(populate_by_name=True)


class BookUpdate(BaseModel):
    id: int
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=5, max_length=1000)
    author: str = Field(min_length=5, max_length=300)
    price: float = Field(ge=0, alias="Price")

    model_config = ConfigDict(populate_by_name=True)


class BookId(BaseModel):
    id: int


class AddQuantity(BaseModel):
    id: int
    quantity: int = Field(ge=1)


class SearchRequest(BaseModel):
    search: str


# --------------------------------------------------------------------------- #
# Cart / Wishlist
# --------------------------------------------------------------------------- #


class BookIdRequest(BaseModel):
    book_id: int


class CartIdRequest(BaseModel):
    cart_id: int


class WishlistIdRequest(BaseModel):
    wishlist_id: int


# --------------------------------------------------------------------------- #
# Address
# --------------------------------------------------------------------------- #


class AddressCreate(BaseModel):
    address: str = Field(min_length=2, max_length=600)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    landmark: str = Field(min_length=2, max_length=100)
    pincode: int
    address_type: str = Field(min_length=2, max_length=100)


class AddressUpdate(AddressCreate):
    id: int


class AddressId(BaseModel):
    id: int


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #


class OrderRequest(BaseModel):
    name: str
    address_id: int
    quantity: int = Field(ge=1)


# --------------------------------------------------------------------------- #
# Feedback
# --------------------------------------------------------------------------- #


class FeedbackRequest(BaseModel):
    book_id: int
    feedback: str = Field(min_length=4, max_length=1000)
    rating: int = Field(ge=1, le=5)


class AverageRatingRequest(BaseModel):
    book_id: int
