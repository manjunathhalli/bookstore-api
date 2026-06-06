"""Users directory web UI — mirrors AI\\UserViewController. Admin only."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...database import get_db
from ...deps import require_web_role
from ...models import User
from ...templating import render

router = APIRouter(prefix="/users", tags=["web-users"])
admin_role = require_web_role("admin")


@router.get("")
def index(request: Request, user: User = Depends(admin_role), db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.id.desc())).all()
    return render(request, "users/index.html", {"users": users}, user=user)
