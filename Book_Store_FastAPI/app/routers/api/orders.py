"""Orders API — mirrors OrderController.placeOrder. Restricted to 'user' role."""

import random
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import require_api_role
from ...models import Address, Book, Order, User
from ...schemas import OrderRequest

router = APIRouter(tags=["orders"])
user_role = require_api_role("user")


def _generate_order_id(length: int = 10) -> str:
    return "".join(random.choices(string.digits + string.ascii_lowercase, k=length))


@router.post("/placeOrder", status_code=status.HTTP_201_CREATED)
def place_order(payload: OrderRequest, user: User = Depends(user_role), db: Session = Depends(get_db)):
    book = db.scalar(select(Book).where(Book.name == payload.name))
    if not book:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "We do not have this book in the store")
    if book.quantity < payload.quantity:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This much stock is unavailable for the book")

    address = db.get(Address, payload.address_id)
    if not address or address.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This address id is not available")

    total_price = payload.quantity * float(book.price)
    order = Order(
        user_id=user.id,
        book_id=book.id,
        address_id=address.id,
        order_id=_generate_order_id(),
    )
    db.add(order)
    book.quantity -= payload.quantity
    db.commit()

    return {
        "status": 201,
        "message": "Order placed Successfully",
        "order_id": order.order_id,
        "total_price": total_price,
    }
