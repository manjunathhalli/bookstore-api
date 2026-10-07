"""Dashboard — mirrors AI\\DashboardController."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.address.models import Address
from app.auth.dependencies import require_web_user
from app.auth.models import User
from app.books.models import Book
from app.cart.models import Cart
from app.core.database import get_db
from app.core.templating import render
from app.feedback.models import Feedback
from app.orders.models import Order
from app.wishlist.models import WishList

router = APIRouter(tags=["web-dashboard"])


def _count(db: Session, model, *where) -> int:
    stmt = select(func.count()).select_from(model)
    for w in where:
        stmt = stmt.where(w)
    return db.scalar(stmt) or 0


@router.get("/dashboard")
def dashboard(request: Request, user: User = Depends(require_web_user), db: Session = Depends(get_db)):
    if user.role == "admin":
        stats = {
            "books": _count(db, Book),
            "users": _count(db, User),
            "orders": _count(db, Order),
            "feedbacks": _count(db, Feedback),
        }
    else:
        stats = {
            "books": _count(db, Book),
            "carts": _count(db, Cart, Cart.user_id == user.id),
            "wishlists": _count(db, WishList, WishList.user_id == user.id),
            "addresses": _count(db, Address, Address.user_id == user.id),
            "orders": _count(db, Order, Order.user_id == user.id),
        }
    return render(request, "dashboard.html", {"stats": stats, "role": user.role}, user=user)
