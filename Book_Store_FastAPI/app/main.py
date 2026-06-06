"""Book Store — FastAPI port of the Laravel project.

Two interfaces, exactly like the original:
  * JWT REST API  (mounted under /api)  — parity with routes/api.php
  * Session web UI (mounted at root)    — parity with routes/web.php + Blade

Both share the same SQLAlchemy models and can run against the same MySQL
database the Laravel app uses (book_store_product).
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import Base, engine
from .deps import RedirectException
from .templating import flash, flash_errors
from .routers.api import address as api_address
from .routers.api import auth as api_auth
from .routers.api import books as api_books
from .routers.api import cart as api_cart
from .routers.api import feedback as api_feedback
from .routers.api import orders as api_orders
from .routers.api import wishlist as api_wishlist
from .routers.web import address as web_address
from .routers.web import auth as web_auth
from .routers.web import books as web_books
from .routers.web import cart as web_cart
from .routers.web import dashboard as web_dashboard
from .routers.web import feedback as web_feedback
from .routers.web import orders as web_orders
from .routers.web import password as web_password
from .routers.web import users as web_users
from .routers.web import wishlist as web_wishlist

# Import models so create_all sees them.
from . import models  # noqa: F401

app = FastAPI(title=f"{settings.app_name} API", version="1.0.0")

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, max_age=60 * 60 * 24 * 7)

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
(STATIC_DIR / "book-covers").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def on_startup():
    if settings.create_tables:
        Base.metadata.create_all(bind=engine)


# --------------------------------------------------------------------------- #
# Web redirect / validation handling (so dependency guards can redirect)
# --------------------------------------------------------------------------- #


@app.exception_handler(RedirectException)
async def redirect_exception_handler(request: Request, exc: RedirectException):
    if exc.error:
        flash(request, exc.error, "error")
    if exc.status:
        flash(request, exc.status, "status")
    return RedirectResponse(exc.url, status_code=303)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # API requests get FastAPI's default JSON; web form posts get a friendly
    # flash + redirect back to where they came from.
    if request.url.path.startswith("/api"):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    messages = []
    for err in exc.errors():
        loc = " → ".join(str(part) for part in err["loc"] if part not in ("body", "query"))
        messages.append(f"{loc}: {err['msg']}" if loc else err["msg"])
    flash_errors(request, messages)
    referer = request.headers.get("referer", "/dashboard")
    return RedirectResponse(referer, status_code=303)


# --------------------------------------------------------------------------- #
# Routers
# --------------------------------------------------------------------------- #

# JWT REST API (parity with routes/api.php)
for r in (api_auth, api_books, api_cart, api_wishlist, api_address, api_orders, api_feedback):
    app.include_router(r.router, prefix="/api")

# Session web UI (parity with routes/web.php)
for r in (
    web_auth, web_dashboard, web_books, web_cart, web_wishlist,
    web_address, web_orders, web_feedback, web_users, web_password,
):
    app.include_router(r.router)
