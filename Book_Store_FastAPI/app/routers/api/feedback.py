"""Feedback API — mirrors FeedbackController. Restricted to the 'user' role."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import require_api_role
from ...models import Book, Feedback, User
from ...schemas import AverageRatingRequest, FeedbackRequest

router = APIRouter(tags=["feedback"])
user_role = require_api_role("user")


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
def feedback(payload: FeedbackRequest, user: User = Depends(user_role), db: Session = Depends(get_db)):
    if not db.get(Book, payload.book_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")

    entry = Feedback(
        user_id=user.id,
        book_id=payload.book_id,
        feedback=payload.feedback,
        rating=payload.rating,
    )
    db.add(entry)
    db.commit()
    return {"status": 201, "message": "Thanks for providing us the detailed feedback about our service"}


@router.post("/getAverageRatingByBookId")
def get_average_rating(payload: AverageRatingRequest, user: User = Depends(user_role), db: Session = Depends(get_db)):
    average = db.scalar(select(func.avg(Feedback.rating)).where(Feedback.book_id == payload.book_id))
    return {"status": 200, "book_id": payload.book_id, "average_rating": float(average) if average is not None else None}
