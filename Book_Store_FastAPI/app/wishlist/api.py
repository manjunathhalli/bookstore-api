"""Wishlist API — mirrors WishlistController. Restricted to the 'user' role."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_api_role
from app.auth.models import User
from app.books.models import Book
from app.core.database import get_db

from .models import WishList
from .schemas import BookIdRequest, WishlistIdRequest

router = APIRouter(tags=["wishlist"])
user_role = require_api_role("user")


@router.post("/addBookToWishlistByBookId", status_code=status.HTTP_201_CREATED)
def add_book_to_wishlist(payload: BookIdRequest, user: User = Depends(user_role), db: Session = Depends(get_db)):
    book = db.get(Book, payload.book_id)
    if not book:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")
    if book.quantity == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OUT OF STOCK")
    if db.scalar(select(WishList).where(WishList.book_id == book.id, WishList.user_id == user.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Book already added to the wishlist")

    db.add(WishList(book_id=book.id, user_id=user.id))
    db.commit()
    return {"status": 201, "message": "Book added to wishlist Successfully"}


@router.get("/getAllBooksInWishlist")
def get_all_books_in_wishlist(user: User = Depends(user_role), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Book.id, Book.name, Book.author, Book.description, Book.price)
        .join(Book, WishList.book_id == Book.id)
        .where(WishList.user_id == user.id)
    ).all()
    books = [
        {"id": r.id, "name": r.name, "author": r.author, "description": r.description, "Price": r.price}
        for r in rows
    ]
    return {"status": 200, "books": books}


@router.post("/deleteBookByWishlistId")
def delete_book_by_wishlist_id(payload: WishlistIdRequest, user: User = Depends(user_role), db: Session = Depends(get_db)):
    wishlist = db.get(WishList, payload.wishlist_id)
    if not wishlist or wishlist.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Wishlist item not found for this user")
    db.delete(wishlist)
    db.commit()
    return {"status": 201, "message": "Book deleted from wishlist Successfully"}
