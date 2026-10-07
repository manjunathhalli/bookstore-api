"""Wishlist schemas for the JWT REST API."""

from pydantic import BaseModel


class BookIdRequest(BaseModel):
    book_id: int


class WishlistIdRequest(BaseModel):
    wishlist_id: int
