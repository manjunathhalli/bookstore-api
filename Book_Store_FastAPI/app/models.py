"""SQLAlchemy models mirroring the Laravel migrations / Eloquent models.

Table and column names match the existing `book_store_product` schema so this
app can run against the very same MySQL database the Laravel app uses.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class TimestampMixin:
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


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


class Book(Base, TimestampMixin):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(1000))
    author: Mapped[str] = mapped_column(String(255))
    image: Mapped[str] = mapped_column(String(255))
    # Laravel migration created this column as lowercase `price`; the Eloquent
    # model referenced it as `Price`. MySQL column names are case-insensitive.
    price: Mapped[str] = mapped_column("price", String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="books")


class Cart(Base, TimestampMixin):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))
    book_quantity: Mapped[int] = mapped_column(Integer, default=1)

    user: Mapped["User"] = relationship(back_populates="carts")
    book: Mapped["Book"] = relationship()


class WishList(Base, TimestampMixin):
    __tablename__ = "wishlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))

    user: Mapped["User"] = relationship(back_populates="wishlists")
    book: Mapped["Book"] = relationship()


class Address(Base, TimestampMixin):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    address: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(255))
    landmark: Mapped[str] = mapped_column(String(255))
    pincode: Mapped[int] = mapped_column(Integer)
    address_type: Mapped[str] = mapped_column(String(255), default="home")

    user: Mapped["User"] = relationship(back_populates="addresses")


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))
    address_id: Mapped[int] = mapped_column(Integer, ForeignKey("addresses.id"))
    order_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship()
    book: Mapped["Book"] = relationship()
    address: Mapped["Address"] = relationship()


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))
    feedback: Mapped[str] = mapped_column(String(255))
    rating: Mapped[int] = mapped_column(Integer)

    user: Mapped["User"] = relationship(back_populates="feedbacks")
    book: Mapped["Book"] = relationship()
