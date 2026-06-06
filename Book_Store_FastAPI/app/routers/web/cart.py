"""Cart web UI — mirrors AI\\CartViewController. 'user' role only."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import require_web_role
from ...models import Book, Cart, User
from ...templating import flash, render

router = APIRouter(prefix="/cart", tags=["web-cart"])
user_role = require_web_role("user")


def _cart_items(db: Session, user_id: int):
    return db.execute(
        select(Cart.id, Book.name, Book.author, Book.price, Cart.book_quantity)
        .join(Book, Cart.book_id == Book.id)
        .where(Cart.user_id == user_id)
    ).all()


@router.get("")
def index(request: Request, user: User = Depends(user_role), db: Session = Depends(get_db)):
    books = db.scalars(select(Book).order_by(Book.name)).all()
    items = _cart_items(db, user.id)
    return render(request, "cart/index.html", {"books": books, "items": items}, user=user)


@router.post("")
def store(request: Request, book_id: int = Form(...), user: User = Depends(user_role), db: Session = Depends(get_db)):
    book = db.get(Book, book_id)
    if not book:
        flash(request, "Book not found.", "error")
    elif book.quantity == 0:
        flash(request, "This book is OUT OF STOCK.", "error")
    elif db.scalar(select(Cart).where(Cart.book_id == book.id, Cart.user_id == user.id)):
        flash(request, "Book already added to the cart.", "error")
    else:
        db.add(Cart(book_id=book.id, user_id=user.id))
        db.commit()
        flash(request, f'"{book.name}" added to cart.')
    return RedirectResponse("/cart", status_code=303)


def _owned_cart(db: Session, cart_id: int, user_id: int) -> Cart | None:
    cart = db.get(Cart, cart_id)
    if not cart or cart.user_id != user_id:
        return None
    return cart


@router.post("/increment")
def increment(request: Request, id: int = Form(...), user: User = Depends(user_role), db: Session = Depends(get_db)):
    cart = _owned_cart(db, id, user.id)
    if not cart:
        flash(request, "This item is not in your cart.", "error")
        return RedirectResponse("/cart", status_code=303)
    cart.book_quantity += 1
    db.commit()
    flash(request, "Quantity increased.")
    return RedirectResponse("/cart", status_code=303)


@router.post("/decrement")
def decrement(request: Request, id: int = Form(...), user: User = Depends(user_role), db: Session = Depends(get_db)):
    cart = _owned_cart(db, id, user.id)
    if not cart:
        flash(request, "This item is not in your cart.", "error")
        return RedirectResponse("/cart", status_code=303)
    cart.book_quantity -= 1
    if cart.book_quantity <= 0:
        db.delete(cart)
        db.commit()
        flash(request, "Item removed from cart (quantity reached 0).")
    else:
        db.commit()
        flash(request, "Quantity decreased.")
    return RedirectResponse("/cart", status_code=303)


@router.post("/delete")
def destroy(request: Request, id: int = Form(...), user: User = Depends(user_role), db: Session = Depends(get_db)):
    cart = _owned_cart(db, id, user.id)
    if not cart:
        flash(request, "This item is not in your cart.", "error")
        return RedirectResponse("/cart", status_code=303)
    db.delete(cart)
    db.commit()
    flash(request, "Book removed from cart.")
    return RedirectResponse("/cart", status_code=303)
