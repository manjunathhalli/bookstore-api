"""Shared Redis connection (Feature: Redis cache).

One client, reused everywhere, exactly like ``engine``/``SessionLocal`` in
``core/database.py``. Every caller wraps its Redis calls in ``try/except`` and
falls back to the database — a Redis outage should slow the app down, never
break it.
"""

from __future__ import annotations

import redis

from .config import settings

# ``decode_responses=True`` so callers get ``str`` back instead of ``bytes``.
redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)


def get_redis() -> redis.Redis:
    """FastAPI dependency / accessor for the shared Redis client."""
    return redis_client
