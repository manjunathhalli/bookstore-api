"""Redis cache-aside helpers for the book catalogue (Feature: Redis).

The catalogue (``GET /api/displayAllBooks``) is read far more often than it
changes, so it's a textbook fit for the **cache-aside** pattern:

1. On read: ask Redis first; a hit skips the database entirely.
2. On miss: read the database, then store the result in Redis with a TTL.
3. On write (create/update/delete/restock): delete the cache key so the next
   read is forced back to the database and repopulates it.

Every function is best-effort — if Redis is down, callers fall back to
querying MySQL directly (the app is correct without Redis, just slower).
"""

from __future__ import annotations

import json
import logging

from app.core.config import settings
from app.core.redis_client import redis_client

logger = logging.getLogger(__name__)

BOOKS_CACHE_KEY = "books:all"


def get_cached_books() -> list[dict] | None:
    try:
        raw = redis_client.get(BOOKS_CACHE_KEY)
    except Exception:  # noqa: BLE001 - Redis being unreachable must not break reads
        logger.warning("Redis unavailable, skipping cache read", exc_info=True)
        return None
    return json.loads(raw) if raw else None


def set_cached_books(books: list[dict]) -> None:
    try:
        redis_client.setex(BOOKS_CACHE_KEY, settings.redis_cache_seconds, json.dumps(books))
    except Exception:  # noqa: BLE001 - caching is an optimisation, never fatal
        logger.warning("Redis unavailable, skipping cache write", exc_info=True)


def invalidate_books_cache() -> None:
    try:
        redis_client.delete(BOOKS_CACHE_KEY)
    except Exception:  # noqa: BLE001
        logger.warning("Redis unavailable, skipping cache invalidation", exc_info=True)
