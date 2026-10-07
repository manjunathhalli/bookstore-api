"""Address schemas for the JWT REST API."""

from pydantic import BaseModel, Field


class AddressCreate(BaseModel):
    address: str = Field(min_length=2, max_length=600)
    city: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    landmark: str = Field(min_length=2, max_length=100)
    pincode: int
    address_type: str = Field(min_length=2, max_length=100)


class AddressUpdate(AddressCreate):
    id: int


class AddressId(BaseModel):
    id: int
