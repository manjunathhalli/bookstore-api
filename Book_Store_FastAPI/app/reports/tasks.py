"""Celery task: build the admin sales report as an .xlsx (Features: Celery,
Pandas, OpenPyXL).

Why this needs a background task at all: for a big store this query + Excel
write can take seconds — long enough that blocking an HTTP request on it would
tie up a worker thread and leave the admin staring at a spinner. Instead the
API/web endpoint just *enqueues* this function and returns immediately with a
task id; the browser polls a status endpoint until the file is ready.

Runs in a **separate OS process** (the Celery worker), not inside FastAPI, so
it cannot use the ``Depends(get_db)`` request-scoped session — it opens and
closes its own ``SessionLocal()`` instead.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import func, select

from app.address.models import Address
from app.auth.models import User
from app.books.models import Book
from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.orders.models import Order

REPORTS_DIR = Path(__file__).resolve().parents[1] / "static" / "reports"


def _orders_dataframe(db) -> pd.DataFrame:
    """Every order joined with its book, customer and delivery address —
    exactly the row shape you'd want in a sales spreadsheet."""
    customer = func.concat(User.first_name, " ", User.last_name).label("customer")
    stmt = (
        select(
            Order.order_id,
            Order.created_at.label("placed_at"),
            customer,
            User.email,
            Book.name.label("book"),
            Book.author,
            Book.genre,
            Order.quantity,
            Book.price.label("unit_price"),
            Order.total_price,
            Address.city.label("delivery_city"),
        )
        .outerjoin(User, Order.user_id == User.id)
        .outerjoin(Book, Order.book_id == Book.id)
        .outerjoin(Address, Order.address_id == Address.id)
        .order_by(Order.id)
    )
    rows = db.execute(stmt).mappings().all()
    return pd.DataFrame(rows)


@celery_app.task(bind=True, name="reports.generate_orders_report")
def generate_orders_report(self) -> dict:
    """Build ``static/reports/<task-id>.xlsx`` and return where to find it."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        df = _orders_dataframe(db)
    finally:
        db.close()

    filename = f"orders-report-{self.request.id}.xlsx"
    path = REPORTS_DIR / filename
    # openpyxl is the *engine* Pandas hands the DataFrame to for the actual
    # .xlsx file format (Excel's zipped-XML format) — Pandas itself only knows
    # how to shape rows/columns, not how to write that file format.
    df.to_excel(path, index=False, sheet_name="Orders", engine="openpyxl")

    return {"filename": filename, "rows": len(df), "download_url": f"/static/reports/{filename}"}
