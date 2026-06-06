"""Feedback web UI — mirrors AI\\FeedbackViewController. 'user' role only."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import require_web_role
from ...models import Book, Feedback, User
from ...templating import flash, render

router = APIRouter(prefix="/feedback", tags=["web-feedback"])
user_role = require_web_role("user")


def _avg_rating(db: Session, book_id: int):
    return db.scalar(select(func.avg(Feedback.rating)).where(Feedback.book_id == book_id))


@router.get("")
def index(request: Request, user: User = Depends(user_role), db: Session = Depends(get_db)):
    books = db.scalars(select(Book).order_by(Book.name)).all()
    average = request.session.pop("_average", None)
    lookup = request.session.pop("_lookup", None)
    return render(request, "feedback.html",
                  {"books": books, "average": average, "lookup": lookup}, user=user)


@router.post("")
def store(
    request: Request,
    book_id: int = Form(...),
    rating: int = Form(...),
    feedback: str = Form(...),
    user: User = Depends(user_role),
    db: Session = Depends(get_db),
):
    book = db.get(Book, book_id)
    if not book:
        flash(request, "Book not found.", "error")
        return RedirectResponse("/feedback", status_code=303)

    db.add(Feedback(user_id=user.id, book_id=book_id, feedback=feedback, rating=rating))
    db.commit()

    avg = _avg_rating(db, book_id)
    request.session["_average"] = {"book": book.name, "rating": float(avg) if avg is not None else 0}
    flash(request, "Thanks for providing us with detailed feedback about our service.")
    return RedirectResponse("/feedback", status_code=303)


@router.post("/average")
def average_rating(request: Request, book_id: int = Form(...), user: User = Depends(user_role), db: Session = Depends(get_db)):
    book = db.get(Book, book_id)
    avg = _avg_rating(db, book_id)
    request.session["_lookup"] = {
        "book": book.name if book else None,
        "rating": float(avg) if avg is not None else 0,
    }
    return RedirectResponse("/feedback", status_code=303)
