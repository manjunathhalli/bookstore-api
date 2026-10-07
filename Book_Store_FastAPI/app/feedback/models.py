"""Feedback model — a shopper's rating and review for a book."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.auth.models import User
    from app.books.models import Book


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))
    feedback: Mapped[str] = mapped_column(String(255))
    rating: Mapped[int] = mapped_column(Integer)
    # AI feature: sentiment label ("Positive"/"Neutral"/"Negative") assigned by
    # Claude when the review is saved. Nullable so pre-AI rows still load.
    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)

    user: Mapped["User"] = relationship(back_populates="feedbacks")
    book: Mapped["Book"] = relationship()
