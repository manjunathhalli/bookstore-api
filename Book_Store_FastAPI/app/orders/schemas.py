"""Order schemas for the JWT REST API."""

from pydantic import BaseModel, Field


class OrderRequest(BaseModel):
    name: str
    address_id: int
    quantity: int = Field(ge=1)
