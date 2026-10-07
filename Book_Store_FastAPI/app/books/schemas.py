"""Book schemas for the JWT REST API."""

from pydantic import BaseModel, ConfigDict, Field


class BookCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=5, max_length=1000)
    author: str = Field(min_length=5, max_length=300)
    image: str
    price: float = Field(ge=0, alias="Price")
    quantity: int = Field(ge=0)
    genre: str | None = Field(default=None, max_length=100)

    model_config = ConfigDict(populate_by_name=True)


class BookUpdate(BaseModel):
    id: int
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(min_length=5, max_length=1000)
    author: str = Field(min_length=5, max_length=300)
    price: float = Field(ge=0, alias="Price")
    genre: str | None = Field(default=None, max_length=100)

    model_config = ConfigDict(populate_by_name=True)


class BookId(BaseModel):
    id: int


class AddQuantity(BaseModel):
    id: int
    quantity: int = Field(ge=1)


class SearchRequest(BaseModel):
    search: str
