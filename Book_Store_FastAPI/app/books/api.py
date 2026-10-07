"""Books API — mirrors BookController. Admin-only mutations; everyone may read."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai import service as ai
from app.auth.dependencies import get_current_api_user, require_api_role
from app.auth.models import User
from app.core.ai import AIError, get_claude
from app.core.database import get_db

from .cache import get_cached_books, invalidate_books_cache, set_cached_books
from .models import Book
from .schemas import AddQuantity, BookCreate, BookId, BookUpdate, SearchRequest

router = APIRouter(tags=["books"])


def _serialize(book: Book) -> dict:
    return {
        "id": book.id,
        "name": book.name,
        "description": book.description,
        "author": book.author,
        "image": book.image,
        "Price": book.price,
        "quantity": book.quantity,
        "genre": book.genre,
    }


@router.post("/addingBook", status_code=status.HTTP_201_CREATED)
def adding_book(
    payload: BookCreate,
    admin: User = Depends(require_api_role("admin")),
    db: Session = Depends(get_db),
):
    book = Book(
        user_id=admin.id,
        name=payload.name,
        description=payload.description,
        author=payload.author,
        image=payload.image,
        price=str(payload.price),
        quantity=payload.quantity,
        genre=payload.genre,
    )

    # AI Features 8 & 10 — auto-tag and embed the new book (best-effort).
    claude = get_claude()
    if claude.enabled:
        book.tags = ai.auto_tag(claude, book.name, book.description)
    if claude.embeddings_enabled:
        try:
            book.embedding = ai.embed_book_text(claude, book.name, book.author, book.description)
        except AIError:
            pass

    db.add(book)
    db.commit()
    db.refresh(book)
    invalidate_books_cache()
    return {"status": 201, "message": "Book created successfully", "book": _serialize(book)}


@router.post("/updateBookById")
def update_book(
    payload: BookUpdate,
    admin: User = Depends(require_api_role("admin")),
    db: Session = Depends(get_db),
):
    book = db.get(Book, payload.id)
    if not book:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find a book with that id")

    book.name = payload.name
    book.description = payload.description
    book.author = payload.author
    book.price = str(payload.price)
    book.genre = payload.genre
    db.commit()
    invalidate_books_cache()
    return {"status": 201, "message": "Book updated successfully"}


@router.post("/deleteBookById")
def delete_book(
    payload: BookId,
    admin: User = Depends(require_api_role("admin")),
    db: Session = Depends(get_db),
):
    book = db.get(Book, payload.id)
    if not book:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find a book with that id")
    db.delete(book)
    db.commit()
    invalidate_books_cache()
    return {"status": 201, "message": "Book deleted Successfully"}


@router.post("/addQuantityToExistBook")
def add_quantity(
    payload: AddQuantity,
    admin: User = Depends(require_api_role("admin")),
    db: Session = Depends(get_db),
):
    book = db.get(Book, payload.id)
    if not book:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Could not find a book with that id")
    book.quantity += payload.quantity
    db.commit()
    invalidate_books_cache()
    return {"status": 201, "message": "Quantity updated to existing book successfully"}


@router.get("/displayAllBooks")
def display_all_books(_: User = Depends(get_current_api_user), db: Session = Depends(get_db)):
    cached = get_cached_books()
    if cached is not None:
        return {"status": 200, "books": cached, "cached": True}

    books = db.scalars(select(Book).order_by(Book.name)).all()
    serialized = [_serialize(b) for b in books]
    set_cached_books(serialized)
    return {"status": 200, "books": serialized, "cached": False}


@router.get("/sortPriceLowToHigh")
def sort_low_to_high(_: User = Depends(get_current_api_user), db: Session = Depends(get_db)):
    books = db.scalars(select(Book)).all()
    books.sort(key=lambda b: float(b.price))
    return {"status": 200, "books": [_serialize(b) for b in books]}


@router.get("/sortPriceHighToLow")
def sort_high_to_low(_: User = Depends(get_current_api_user), db: Session = Depends(get_db)):
    books = db.scalars(select(Book)).all()
    books.sort(key=lambda b: float(b.price), reverse=True)
    return {"status": 200, "books": [_serialize(b) for b in books]}


@router.post("/searchBookByKeyword")
def search_book(
    payload: SearchRequest,
    _: User = Depends(get_current_api_user),
    db: Session = Depends(get_db),
):
    like = f"%{payload.search}%"
    books = db.scalars(
        select(Book).where(or_(Book.name.like(like), Book.author.like(like)))
    ).all()
    return {"status": 200, "books": [_serialize(b) for b in books]}
