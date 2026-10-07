"""Request/response schemas for the AI endpoints (web fetch + JWT API)."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class DescriptionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    author: str = Field(min_length=1, max_length=255)


class SmartSearchRequest(BaseModel):
    q: str = Field(min_length=1, max_length=500)


class TagRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, max_length=1000)


class FineTunePredictRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
