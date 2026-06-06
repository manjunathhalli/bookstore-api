"""Orders web UI — mirrors AI\\OrderViewController. 'user' role only."""

import random
import string

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import require_web_role, require_web_user
from ...models import Address, Book, Order, User
from ...templating import flash, render

router = APIRouter(prefix="/orders", tags=["web-orders"])
user_role = require_web_role("user")


def _generate_order_id(length: int = 10) -> str:
    return "".join(random.choices(string.digits + string.ascii_lowercase, k=length))


def _orders_query(db: Session, user_id: int | None = None):
    """Order rows joined with book/address/customer. Pass user_id to scope to a
    single customer (the shopper's own history); omit it for the store-wide
    admin view."""
    customer = func.concat(User.first_name, " ", User.last_name).label("customer")
    stmt = (
        select(
            Order.id, Order.order_id, Order.created_at,
            Book.name.label("book_name"), Book.price,
            Address.city, Address.address_type, customer,
        )
        .outerjoin(Book, Order.book_id == Book.id)
        .outerjoin(Address, Order.address_id == Address.id)
        .outerjoin(User, Order.user_id == User.id)
        .order_by(Order.id.desc())
    )
    if user_id is not None:
        stmt = stmt.where(Order.user_id == user_id)
    return db.execute(stmt).all()


def _orders_for(db: Session, user_id: int):
    return _orders_query(db, user_id)


@router.get("")
def index(request: Request, user: User = Depends(require_web_user), db: Session = Depends(get_db)):
    # Admins get a read-only, store-wide view; shoppers see their own history
    # plus the "place an order" form.
    if user.role == "admin":
        orders = _orders_query(db)
        return render(request, "orders/index.html",
                      {"books": [], "addresses": [], "orders": orders}, user=user)

    books = db.scalars(select(Book).order_by(Book.name)).all()
    addresses = db.scalars(select(Address).where(Address.user_id == user.id)).all()
    orders = _orders_query(db, user.id)
    return render(request, "orders/index.html",
                  {"books": books, "addresses": addresses, "orders": orders}, user=user)


@router.post("")
def store(
    request: Request,
    name: str = Form(...),
    address_id: int = Form(...),
    quantity: int = Form(...),
    user: User = Depends(user_role),
    db: Session = Depends(get_db),
):
    book = db.scalar(select(Book).where(Book.name == name))
    if not book:
        flash(request, "We do not have this book in the store.", "error")
        return RedirectResponse("/orders", status_code=303)
    if book.quantity < quantity:
        flash(request, "This much stock is unavailable for the book.", "error")
        return RedirectResponse("/orders", status_code=303)

    address = db.get(Address, address_id)
    if not address or address.user_id != user.id:
        flash(request, "This address id is not available.", "error")
        return RedirectResponse("/orders", status_code=303)

    total_price = quantity * float(book.price)
    order = Order(
        user_id=user.id, book_id=book.id, address_id=address.id,
        order_id=_generate_order_id(),
    )
    db.add(order)
    book.quantity -= quantity
    db.commit()

    flash(request, f"Order {order.order_id} placed for {quantity} × {book.name} — total ₹{total_price:,.2f}.")
    return RedirectResponse("/orders", status_code=303)
