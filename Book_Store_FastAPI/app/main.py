"""Book Store — FastAPI port of the Laravel project.

Two interfaces, exactly like the original:
  * JWT REST API  (mounted under /api)  — parity with routes/api.php
  * Session web UI (mounted at root)    — parity with routes/web.php + Blade

Both share the same SQLAlchemy models and can run against the same MySQL
database the Laravel app uses (book_store_product).

The codebase is organised feature-first: each domain package (auth, books,
cart, wishlist, address, orders, feedback, dashboard, users, password) owns its
own models / schemas / routers, while cross-cutting concerns live in app.core.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.address import api as address_api, web as address_web
from app.ai import api as ai_api, web as ai_web
from app.auth import api as auth_api, web as auth_web
from app.auth.dependencies import RedirectException
from app.bc import api as bc_api, web as bc_web
from app.books import api as books_api, web as books_web
from app.cart import api as cart_api, web as cart_web
from app.core.config import settings
from app.core.database import Base, engine, ensure_ai_columns
from app.core.templating import flash, flash_errors
from app.dashboard import web as dashboard_web
from app.feedback import api as feedback_api, web as feedback_web
from app.orders import api as orders_api, web as orders_web
from app.password import web as password_web
from app.reports import api as reports_api, web as reports_web
from app.users import web as users_web
from app.wishlist import api as wishlist_api, web as wishlist_web

app = FastAPI(title=f"{settings.app_name} API", version="1.0.0")

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, max_age=60 * 60 * 24 * 7)

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
(STATIC_DIR / "book-covers").mkdir(exist_ok=True)
(STATIC_DIR / "reports").mkdir(exist_ok=True)  # Feature: Pandas/OpenPyXL report output
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def on_startup():
    if settings.create_tables:
        Base.metadata.create_all(bind=engine)
    # Add AI columns (sentiment / tags / embedding) to pre-existing tables.
    ensure_ai_columns()


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
for module in (
    auth_api, books_api, cart_api, wishlist_api, address_api, orders_api, feedback_api,
    ai_api, bc_api, reports_api,
):
    app.include_router(module.router, prefix="/api")

# Session web UI (parity with routes/web.php)
for module in (
    auth_web, dashboard_web, books_web, cart_web, wishlist_web,
    address_web, orders_web, feedback_web, users_web, password_web, ai_web, bc_web, reports_web,
):
    app.include_router(module.router)
