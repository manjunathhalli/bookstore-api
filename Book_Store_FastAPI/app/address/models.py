"""Address model — a shopper's saved delivery addresses."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.auth.models import User


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
