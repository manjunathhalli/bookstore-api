"""User model — the core account entity shared across every feature.

Table and column names match the existing `book_store_product` schema so this
app can run against the very same MySQL database the Laravel app uses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.address.models import Address
    from app.books.models import Book
    from app.cart.models import Cart
    from app.feedback.models import Feedback
    from app.wishlist.models import WishList


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(255), default="user")
    first_name: Mapped[str] = mapped_column(String(255))
    last_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone_no: Mapped[str] = mapped_column(String(255))
    password: Mapped[str] = mapped_column(String(255))

    books: Mapped[list["Book"]] = relationship(back_populates="user")
    carts: Mapped[list["Cart"]] = relationship(back_populates="user")
    wishlists: Mapped[list["WishList"]] = relationship(back_populates="user")
    addresses: Mapped[list["Address"]] = relationship(back_populates="user")
    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="user")
