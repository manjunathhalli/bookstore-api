"""Book model — the catalogue entry owned by an admin user."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.auth.models import User


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
    # Added via Alembic migration 0002 — see alembic/versions/ and
    # LEARNING_GUIDE.md section 8's "add a genre column" exercise, now done
    # for real with a migration instead of dropping the table.
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # AI features (stored as JSON columns):
    #   tags      — list[str] genre labels for auto-tagging & filtering (Claude)
    #   embedding — list[float] local sentence-transformers vector for semantic search
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="books")
