"""SQLAlchemy engine, session factory, declarative base and shared mixins."""

from collections.abc import Generator
from datetime import datetime

from sqlalchemy import DateTime, create_engine, func, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime | None] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Lightweight column migration for the AI features
# --------------------------------------------------------------------------- #
#
# ``Base.metadata.create_all`` only CREATEs missing *tables* — it never ALTERs
# an existing one. When this app runs against the Laravel-created MySQL schema,
# the AI columns (feedbacks.sentiment, books.tags, books.embedding) won't exist
# yet, so we add them idempotently on startup. New/empty databases already get
# the columns from ``create_all``; there this is a no-op.

# column name -> SQL type used in the ALTER statement.
_AI_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "feedbacks": [("sentiment", "VARCHAR(20) NULL")],
    "books": [("genre", "VARCHAR(100) NULL"), ("tags", "JSON NULL"), ("embedding", "JSON NULL")],
}


def ensure_ai_columns() -> None:
    """Add any missing AI columns to pre-existing tables (best-effort)."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table, columns in _AI_COLUMNS.items():
            if table not in existing_tables:
                continue  # create_all will have made it with the columns
            present = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns:
                if name in present:
                    continue
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                except Exception:  # noqa: BLE001 - never block startup on this
                    # e.g. permissions, or a backend that lacks JSON — the app
                    # still runs; the affected AI feature just stays inactive.
                    pass
