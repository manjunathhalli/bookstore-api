"""Address API — mirrors AddressController. Restricted to the 'user' role."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_api_role
from app.auth.models import User
from app.core.database import get_db

from .models import Address
from .schemas import AddressCreate, AddressId, AddressUpdate

router = APIRouter(tags=["address"])
user_role = require_api_role("user")


def _serialize(a: Address) -> dict:
    return {
        "id": a.id,
        "user_id": a.user_id,
        "address": a.address,
        "city": a.city,
        "state": a.state,
        "landmark": a.landmark,
        "pincode": a.pincode,
        "address_type": a.address_type,
    }


@router.post("/addAddress", status_code=status.HTTP_201_CREATED)
def add_address(payload: AddressCreate, user: User = Depends(user_role), db: Session = Depends(get_db)):
    address = Address(user_id=user.id, **payload.model_dump())
    db.add(address)
    db.commit()
    return {"status": 201, "message": "Address added Successfully"}


@router.post("/updateAddress")
def update_address(payload: AddressUpdate, user: User = Depends(user_role), db: Session = Depends(get_db)):
    address = db.get(Address, payload.id)
    if not address or address.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Address not found for this user")
    for field, value in payload.model_dump(exclude={"id"}).items():
        setattr(address, field, value)
    db.commit()
    return {"status": 201, "message": "Address updated Successfully"}


@router.post("/deleteAddress")
def delete_address(payload: AddressId, user: User = Depends(user_role), db: Session = Depends(get_db)):
    address = db.get(Address, payload.id)
    if not address or address.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Address not found for this user")
    db.delete(address)
    db.commit()
    return {"status": 201, "message": "Address deleted Successfully"}


@router.post("/getAddress")
def get_address(user: User = Depends(user_role), db: Session = Depends(get_db)):
    addresses = db.scalars(select(Address).where(Address.user_id == user.id)).all()
    return {"status": 200, "addresses": [_serialize(a) for a in addresses]}
