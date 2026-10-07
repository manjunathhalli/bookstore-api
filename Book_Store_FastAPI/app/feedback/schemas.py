"""Feedback schemas for the JWT REST API."""

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    book_id: int
    feedback: str = Field(min_length=4, max_length=1000)
    rating: int = Field(ge=1, le=5)


class AverageRatingRequest(BaseModel):
    book_id: int
