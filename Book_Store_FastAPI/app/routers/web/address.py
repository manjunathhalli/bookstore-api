"""Address web UI — mirrors AI\\AddressViewController. 'user' role only."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import require_web_role
from ...models import Address, User
from ...templating import flash, render

router = APIRouter(prefix="/address", tags=["web-address"])
user_role = require_web_role("user")


@router.get("")
def index(request: Request, user: User = Depends(user_role), db: Session = Depends(get_db)):
    addresses = db.scalars(select(Address).where(Address.user_id == user.id)).all()
    return render(request, "address/index.html", {"addresses": addresses}, user=user)


@router.post("")
def store(
    request: Request,
    address: str = Form(...),
    city: str = Form(...),
    state: str = Form(...),
    landmark: str = Form(...),
    pincode: int = Form(...),
    address_type: str = Form(...),
    user: User = Depends(user_role),
    db: Session = Depends(get_db),
):
    db.add(Address(
        user_id=user.id, address=address, city=city, state=state,
        landmark=landmark, pincode=pincode, address_type=address_type,
    ))
    db.commit()
    flash(request, "Address added successfully.")
    return RedirectResponse("/address", status_code=303)


def _owned_address(db: Session, aid: int, user_id: int) -> Address | None:
    address = db.get(Address, aid)
    if not address or address.user_id != user_id:
        return None
    return address


@router.get("/{id}/edit")
def edit(request: Request, id: int, user: User = Depends(user_role), db: Session = Depends(get_db)):
    address = _owned_address(db, id, user.id)
    if not address:
        flash(request, "This address is not yours.", "error")
        return RedirectResponse("/address", status_code=303)
    return render(request, "address/edit.html", {"address": address}, user=user)


@router.post("/{id}")
def update(
    request: Request,
    id: int,
    address: str = Form(...),
    city: str = Form(...),
    state: str = Form(...),
    landmark: str = Form(...),
    pincode: int = Form(...),
    address_type: str = Form(...),
    user: User = Depends(user_role),
    db: Session = Depends(get_db),
):
    record = _owned_address(db, id, user.id)
    if not record:
        flash(request, "This address is not yours.", "error")
        return RedirectResponse("/address", status_code=303)
    record.address = address
    record.city = city
    record.state = state
    record.landmark = landmark
    record.pincode = pincode
    record.address_type = address_type
    db.commit()
    flash(request, "Address updated successfully.")
    return RedirectResponse("/address", status_code=303)


@router.post("/{id}/delete")
def destroy(request: Request, id: int, user: User = Depends(user_role), db: Session = Depends(get_db)):
    record = _owned_address(db, id, user.id)
    if not record:
        flash(request, "This address is not yours.", "error")
        return RedirectResponse("/address", status_code=303)
    db.delete(record)
    db.commit()
    flash(request, "Address deleted successfully.")
    return RedirectResponse("/address", status_code=303)
