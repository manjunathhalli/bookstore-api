"""Books web UI — mirrors AI\\BookViewController.

Everyone may browse; only admins may add / edit / delete / restock. Cover
images are stored on the local 'static/book-covers' disk (the Laravel web view
did the same with the public disk, avoiding the API's S3 dependency).
"""

import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai import service as ai
from app.auth.dependencies import require_web_role, require_web_user
from app.auth.models import User
from app.core.ai import AIError, get_claude
from app.core.database import get_db
from app.core.templating import flash, flash_errors, render

from .cache import invalidate_books_cache
from .models import Book


def _ai_enrich(book: Book) -> None:
    """AI Features 8 & 10: auto-tag and embed a book on create/update.

    Best-effort — a missing key or API outage leaves the columns null and the
    book is saved regardless.
    """
    claude = get_claude()
    if claude.enabled:
        book.tags = ai.auto_tag(claude, book.name, book.description)
    if claude.embeddings_enabled:
        try:
            book.embedding = ai.embed_book_text(claude, book.name, book.author, book.description)
        except AIError:
            pass

router = APIRouter(prefix="/books", tags=["web-books"])
admin_role = require_web_role("admin")

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "static" / "book-covers"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXT = {".jpeg", ".jpg", ".png", ".gif", ".svg"}


def _save_image(file: UploadFile) -> str | None:
    if not file or not file.filename:
        return None
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        return None
    name = f"{secrets.token_hex(8)}{ext}"
    (UPLOAD_DIR / name).write_bytes(file.file.read())
    return f"/static/book-covers/{name}"


@router.get("")
def index(
    request: Request,
    q: str = "",
    sort: str = "",
    user: User = Depends(require_web_user),
    db: Session = Depends(get_db),
):
    query = q.strip()
    if query:
        like = f"%{query}%"
        books = db.scalars(select(Book).where(or_(Book.name.like(like), Book.author.like(like)))).all()
    elif sort == "low":
        books = sorted(db.scalars(select(Book)).all(), key=lambda b: float(b.price))
    elif sort == "high":
        books = sorted(db.scalars(select(Book)).all(), key=lambda b: float(b.price), reverse=True)
    else:
        books = db.scalars(select(Book).order_by(Book.name)).all()

    return render(request, "books/index.html",
                  {"books": books, "sort": sort, "query": query, "is_admin": user.role == "admin"},
                  user=user)


@router.post("")
def store(
    request: Request,
    name: str = Form(...),
    author: str = Form(...),
    description: str = Form(...),
    Price: float = Form(...),
    quantity: int = Form(...),
    genre: str = Form(""),
    image: UploadFile = File(...),
    user: User = Depends(admin_role),
    db: Session = Depends(get_db),
):
    errors = []
    if db.scalar(select(Book).where(Book.name == name)):
        errors.append("A book with that name already exists.")
    image_url = _save_image(image)
    if image_url is None:
        errors.append("A valid cover image (jpeg, png, jpg, gif, svg) is required.")

    if errors:
        flash_errors(request, errors)
        return RedirectResponse("/books", status_code=303)

    book = Book(
        user_id=user.id, name=name, author=author, description=description,
        image=image_url, price=str(Price), quantity=quantity, genre=genre.strip() or None,
    )
    _ai_enrich(book)
    db.add(book)
    db.commit()
    invalidate_books_cache()
    flash(request, f'Book "{name}" created successfully.')
    return RedirectResponse("/books", status_code=303)


@router.post("/add-quantity")
def add_quantity(
    request: Request,
    id: int = Form(...),
    quantity: int = Form(...),
    user: User = Depends(admin_role),
    db: Session = Depends(get_db),
):
    book = db.get(Book, id)
    if not book:
        flash(request, "Book not found.", "error")
        return RedirectResponse("/books", status_code=303)
    book.quantity += quantity
    db.commit()
    invalidate_books_cache()
    flash(request, f'Added {quantity} unit(s) to "{book.name}" (now {book.quantity}).')
    return RedirectResponse("/books", status_code=303)


@router.get("/{id}/edit")
def edit(request: Request, id: int, user: User = Depends(admin_role), db: Session = Depends(get_db)):
    book = db.get(Book, id)
    if not book:
        flash(request, "Book not found.", "error")
        return RedirectResponse("/books", status_code=303)
    return render(request, "books/edit.html", {"book": book}, user=user)


@router.post("/{id}")
def update(
    request: Request,
    id: int,
    name: str = Form(...),
    author: str = Form(...),
    description: str = Form(...),
    Price: float = Form(...),
    genre: str = Form(""),
    image: UploadFile = File(None),
    user: User = Depends(admin_role),
    db: Session = Depends(get_db),
):
    book = db.get(Book, id)
    if not book:
        flash(request, "Book not found.", "error")
        return RedirectResponse("/books", status_code=303)

    clash = db.scalar(select(Book).where(Book.name == name, Book.id != id))
    if clash:
        flash_errors(request, ["A book with that name already exists."])
        return RedirectResponse(f"/books/{id}/edit", status_code=303)

    book.name = name
    book.author = author
    book.description = description
    book.price = str(Price)
    book.genre = genre.strip() or None
    new_image = _save_image(image) if image and image.filename else None
    if new_image:
        book.image = new_image
    _ai_enrich(book)  # refresh tags + embedding for the new content
    db.commit()
    invalidate_books_cache()
    flash(request, f'Book "{book.name}" updated successfully.')
    return RedirectResponse("/books", status_code=303)


@router.post("/{id}/delete")
def destroy(request: Request, id: int, user: User = Depends(admin_role), db: Session = Depends(get_db)):
    book = db.get(Book, id)
    if not book:
        flash(request, "Book not found.", "error")
        return RedirectResponse("/books", status_code=303)
    name = book.name
    db.delete(book)
    db.commit()
    invalidate_books_cache()
    flash(request, f'Book "{name}" deleted successfully.')
    return RedirectResponse("/books", status_code=303)
