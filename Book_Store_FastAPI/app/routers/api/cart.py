"""Cart API — mirrors CartController. Restricted to the 'user' role."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import require_api_role
from ...models import Book, Cart, User, WishList
from ...schemas import BookIdRequest, CartIdRequest, WishlistIdRequest

router = APIRouter(tags=["cart"])
user_role = require_api_role("user")


@router.post("/addBookToCartByBookId", status_code=status.HTTP_201_CREATED)
def add_book_to_cart(payload: BookIdRequest, user: User = Depends(user_role), db: Session = Depends(get_db)):
    book = db.get(Book, payload.book_id)
    if not book:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")
    if book.quantity == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OUT OF STOCK")

    existing = db.scalar(
        select(Cart).where(Cart.book_id == book.id, Cart.user_id == user.id)
    )
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Book already added to the cart")

    cart = Cart(book_id=book.id, user_id=user.id)
    db.add(cart)
    db.commit()
    return {"status": 201, "message": "Book added to cart Successfully"}


@router.get("/getAllBooksInCart")
def get_all_books_in_cart(user: User = Depends(user_role), db: Session = Depends(get_db)):
    rows = db.execute(
        select(
            Book.id, Book.name, Book.author, Book.description, Book.price, Cart.book_quantity
        )
        .join(Book, Cart.book_id == Book.id)
        .where(Cart.user_id == user.id)
    ).all()
    books = [
        {
            "id": r.id,
            "name": r.name,
            "author": r.author,
            "description": r.description,
            "Price": r.price,
            "book_quantity": r.book_quantity,
        }
        for r in rows
    ]
    return {"status": 200, "books": books}


@router.post("/deleteBookByCartId")
def delete_book_by_cart_id(payload: CartIdRequest, user: User = Depends(user_role), db: Session = Depends(get_db)):
    cart = db.get(Cart, payload.cart_id)
    if not cart or cart.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart not found for this user")
    db.delete(cart)
    db.commit()
    return {"status": 201, "message": "Book deleted from cart Successfully"}


@router.post("/increamentBookQuantityInCart")
def increment_quantity(payload: CartIdRequest, user: User = Depends(user_role), db: Session = Depends(get_db)):
    cart = db.get(Cart, payload.cart_id)
    if not cart or cart.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart not found for this user")
    cart.book_quantity += 1
    db.commit()
    return {"status": 201, "message": "Book quantity increment Successfully"}


@router.post("/decrementBookQuantityInCart")
def decrement_quantity(payload: CartIdRequest, user: User = Depends(user_role), db: Session = Depends(get_db)):
    cart = db.get(Cart, payload.cart_id)
    if not cart or cart.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cart not found for this user")
    cart.book_quantity -= 1
    if cart.book_quantity <= 0:
        db.delete(cart)
        db.commit()
        return {"status": 201, "message": "Item removed from cart (quantity reached 0)"}
    db.commit()
    return {"status": 201, "message": "Book quantity decrement Successfully"}


@router.post("/addBookToCartByWishlistId", status_code=status.HTTP_201_CREATED)
def add_book_from_wishlist(payload: WishlistIdRequest, user: User = Depends(user_role), db: Session = Depends(get_db)):
    wishlist = db.get(WishList, payload.wishlist_id)
    if not wishlist or wishlist.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Wishlist item not found for this user")

    book = db.get(Book, wishlist.book_id)
    if not book:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")
    if book.quantity == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "OUT OF STOCK")
    if db.scalar(select(Cart).where(Cart.book_id == book.id, Cart.user_id == user.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Book already added in cart")

    db.add(Cart(book_id=book.id, user_id=user.id))
    db.delete(wishlist)
    db.commit()
    return {"status": 201, "message": "Book added to cart from wishlist Successfully"}
