"""Feedback API — mirrors FeedbackController. Restricted to the 'user' role."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import service as ai
from app.auth.dependencies import require_api_role
from app.auth.models import User
from app.books.models import Book
from app.core.ai import get_claude
from app.core.database import get_db

from .models import Feedback
from .schemas import AverageRatingRequest, FeedbackRequest

router = APIRouter(tags=["feedback"])
user_role = require_api_role("user")


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
def feedback(payload: FeedbackRequest, user: User = Depends(user_role), db: Session = Depends(get_db)):
    if not db.get(Book, payload.book_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")

    # AI Feature 7 — content moderation before storing user text.
    claude = get_claude()
    if not ai.moderate(claude, payload.feedback):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Your review was flagged as inappropriate")

    # AI Feature 1 — sentiment analysis label.
    sentiment = ai.analyze_sentiment(claude, payload.feedback) if claude.enabled else None

    entry = Feedback(
        user_id=user.id,
        book_id=payload.book_id,
        feedback=payload.feedback,
        rating=payload.rating,
        sentiment=sentiment,
    )
    db.add(entry)
    db.commit()
    return {"status": 201, "message": "Thanks for providing us the detailed feedback about our service"}


@router.post("/getAverageRatingByBookId")
def get_average_rating(payload: AverageRatingRequest, user: User = Depends(user_role), db: Session = Depends(get_db)):
    average = db.scalar(select(func.avg(Feedback.rating)).where(Feedback.book_id == payload.book_id))
    return {"status": 200, "book_id": payload.book_id, "average_rating": float(average) if average is not None else None}
