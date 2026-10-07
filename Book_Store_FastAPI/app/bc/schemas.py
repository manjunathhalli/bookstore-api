"""Request schemas for the Business Central chatbot endpoints."""

from pydantic import BaseModel, Field


class BCChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
