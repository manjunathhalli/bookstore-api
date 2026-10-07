"""Feedback web UI — mirrors AI\\FeedbackViewController. 'user' role only."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import service as ai
from app.auth.dependencies import require_web_role
from app.auth.models import User
from app.books.models import Book
from app.core.ai import get_claude
from app.core.database import get_db
from app.core.templating import flash, flash_errors, render

from .models import Feedback

router = APIRouter(prefix="/feedback", tags=["web-feedback"])
user_role = require_web_role("user")


def _avg_rating(db: Session, book_id: int):
    return db.scalar(select(func.avg(Feedback.rating)).where(Feedback.book_id == book_id))


@router.get("")
def index(request: Request, user: User = Depends(user_role), db: Session = Depends(get_db)):
    books = db.scalars(select(Book).order_by(Book.name)).all()
    average = request.session.pop("_average", None)
    lookup = request.session.pop("_lookup", None)
    sentiment = request.session.pop("_sentiment", None)
    return render(request, "feedback.html",
                  {"books": books, "average": average, "lookup": lookup, "sentiment": sentiment}, user=user)


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

    # AI Feature 7 — content moderation: reject abusive/spam reviews before save.
    # A fast LLM call classifies the text SAFE/UNSAFE *before* it ever reaches
    # the database — it never blocks on an outage (fails open, see ai.moderate).
    claude = get_claude()
    if not ai.moderate(claude, feedback):
        flash_errors(
            request,
            ["AI content moderation flagged this review as inappropriate (hate, "
             "harassment, sexual content or spam) and blocked it before it was saved."],
            {"feedback": feedback},
        )
        return RedirectResponse("/feedback", status_code=303)

    # AI Feature 1 — sentiment analysis: label the review as we store it. This
    # is the model's own read of the *text*, independent of the star rating
    # the shopper picked — compare the two below.
    sentiment = ai.analyze_sentiment(claude, feedback) if claude.enabled else None

    db.add(Feedback(user_id=user.id, book_id=book_id, feedback=feedback,
                    rating=rating, sentiment=sentiment))
    db.commit()

    avg = _avg_rating(db, book_id)
    request.session["_average"] = {"book": book.name, "rating": float(avg) if avg is not None else 0}
    request.session["_sentiment"] = {"sentiment": sentiment, "rating": rating}
    flash(request, "Thanks for providing us with detailed feedback about our service.")
    return RedirectResponse("/feedback", status_code=303)


@router.post("/average")
def average_rating(request: Request, book_id: int = Form(...), user: User = Depends(user_role), db: Session = Depends(get_db)):
    book = db.get(Book, book_id)
    avg = _avg_rating(db, book_id)

    # AI Feature 1, aggregated: how many of this book's stored reviews the
    # sentiment model labelled each way — real counts from the `sentiment`
    # column every review submission already fills in, not a fresh LLM call.
    sentiment_counts = dict(
        db.execute(
            select(Feedback.sentiment, func.count(Feedback.id))
            .where(Feedback.book_id == book_id, Feedback.sentiment.isnot(None))
            .group_by(Feedback.sentiment)
        ).all()
    )

    request.session["_lookup"] = {
        "book": book.name if book else None,
        "rating": float(avg) if avg is not None else 0,
        "sentiment_counts": sentiment_counts,
    }
    return RedirectResponse("/feedback", status_code=303)
