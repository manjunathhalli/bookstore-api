"""Wishlist web UI — mirrors AI\\WishlistViewController. 'user' role only."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import require_web_role
from ...models import Book, Cart, User, WishList
from ...templating import flash, render

router = APIRouter(prefix="/wishlist", tags=["web-wishlist"])
user_role = require_web_role("user")


def _wishlist_items(db: Session, user_id: int):
    return db.execute(
        select(WishList.id, Book.name, Book.author, Book.price)
        .join(Book, WishList.book_id == Book.id)
        .where(WishList.user_id == user_id)
    ).all()


@router.get("")
def index(request: Request, user: User = Depends(user_role), db: Session = Depends(get_db)):
    books = db.scalars(select(Book).order_by(Book.name)).all()
    items = _wishlist_items(db, user.id)
    return render(request, "wishlist/index.html", {"books": books, "items": items}, user=user)


@router.post("")
def store(request: Request, book_id: int = Form(...), user: User = Depends(user_role), db: Session = Depends(get_db)):
    book = db.get(Book, book_id)
    if not book:
        flash(request, "Book not found.", "error")
    elif book.quantity == 0:
        flash(request, "OUT OF STOCK from the bookstore.", "error")
    elif db.scalar(select(WishList).where(WishList.book_id == book.id, WishList.user_id == user.id)):
        flash(request, "Book already added to the wishlist.", "error")
    else:
        db.add(WishList(book_id=book.id, user_id=user.id))
        db.commit()
        flash(request, f'"{book.name}" added to wishlist.')
    return RedirectResponse("/wishlist", status_code=303)


def _owned_wishlist(db: Session, wid: int, user_id: int) -> WishList | None:
    wishlist = db.get(WishList, wid)
    if not wishlist or wishlist.user_id != user_id:
        return None
    return wishlist


@router.post("/move-to-cart")
def move_to_cart(request: Request, id: int = Form(...), user: User = Depends(user_role), db: Session = Depends(get_db)):
    wishlist = _owned_wishlist(db, id, user.id)
    if not wishlist:
        flash(request, "This item is not in your wishlist.", "error")
        return RedirectResponse("/wishlist", status_code=303)

    book = db.get(Book, wishlist.book_id)
    if not book:
        flash(request, "Book not found.", "error")
    elif book.quantity == 0:
        flash(request, "OUT OF STOCK.", "error")
    elif db.scalar(select(Cart).where(Cart.book_id == book.id, Cart.user_id == user.id)):
        flash(request, "Book already added in cart.", "error")
    else:
        db.add(Cart(book_id=book.id, user_id=user.id))
        db.delete(wishlist)
        db.commit()
        flash(request, f'"{book.name}" moved to cart.')
    return RedirectResponse("/wishlist", status_code=303)


@router.post("/delete")
def destroy(request: Request, id: int = Form(...), user: User = Depends(user_role), db: Session = Depends(get_db)):
    wishlist = _owned_wishlist(db, id, user.id)
    if not wishlist:
        flash(request, "This item is not in your wishlist.", "error")
        return RedirectResponse("/wishlist", status_code=303)
    db.delete(wishlist)
    db.commit()
    flash(request, "Book removed from wishlist.")
    return RedirectResponse("/wishlist", status_code=303)
