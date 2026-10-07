"""Order model — a placed order line linking shopper, book and address."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.address.models import Address
    from app.auth.models import User
    from app.books.models import Book


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))
    address_id: Mapped[int] = mapped_column(Integer, ForeignKey("addresses.id"))
    order_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Added via Alembic migration 0002 (see alembic/versions/) — the original
    # Laravel schema never recorded these, so total revenue had to be
    # recomputed from live stock, which the Feature 12 sales report needs.
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    total_price: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped["User"] = relationship()
    book: Mapped["Book"] = relationship()
    address: Mapped["Address"] = relationship()
