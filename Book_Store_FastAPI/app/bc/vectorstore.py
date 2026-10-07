"""Qdrant vector store wrapper for the Business Central chatbot.

A thin layer over ``qdrant-client`` that the service uses to store and search
BC record vectors. Kept isolated so the rest of the app never imports Qdrant
directly, and so everything degrades gracefully when the package isn't
installed or the server isn't running.

* ``qdrant-client`` missing  -> :meth:`available` is False, calls raise
  :class:`VectorStoreError`; the UI shows a "run Qdrant" hint.
* server unreachable         -> the same, surfaced with the underlying error.

The collection uses cosine distance to match the normalised vectors produced by
the local ``sentence-transformers`` model (see :class:`app.core.ai.ClaudeService`).
"""

from __future__ import annotations

import uuid

from app.core.config import settings

# Stable namespace so re-ingesting the same record overwrites its point rather
# than creating a duplicate (id = uuid5(namespace, "entity:record-key")).
_NAMESPACE = uuid.UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")


class VectorStoreError(RuntimeError):
    """Raised when a Qdrant operation cannot be completed."""


def point_id(entity: str, key: str) -> str:
    """Deterministic Qdrant point id for a record, so re-sync upserts in place."""
    return str(uuid.uuid5(_NAMESPACE, f"{entity}:{key}"))


class VectorStore:
    """Manages the single Business Central collection in Qdrant."""

    def __init__(self) -> None:
        self._client = None
        self._checked = False

    # ------------------------------------------------------------------ #
    # Connection
    # ------------------------------------------------------------------ #

    def _connect(self):
        """Lazily create the Qdrant client (cached). Returns None if unavailable."""
        if self._checked:
            return self._client
        self._checked = True
        try:
            from qdrant_client import QdrantClient
        except ImportError:
            self._client = None
            return None
        if settings.qdrant_path:
            # Embedded mode: no server, vectors persisted to a local folder.
            self._client = QdrantClient(path=settings.qdrant_path)
        else:
            self._client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
                timeout=30,
            )
        return self._client

    @property
    def location(self) -> str:
        """Human-readable description of where vectors are stored (for messages)."""
        if settings.qdrant_path:
            return f"embedded folder '{settings.qdrant_path}'"
        return settings.qdrant_url

    def _require(self):
        client = self._connect()
        if client is None:
            raise VectorStoreError(
                "qdrant-client is not installed — run 'pip install qdrant-client'."
            )
        return client

    @property
    def available(self) -> bool:
        """True when the client library is importable AND the server responds."""
        client = self._connect()
        if client is None:
            return False
        try:
            client.get_collections()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Collection lifecycle
    # ------------------------------------------------------------------ #

    def ensure_collection(self, dim: int) -> None:
        """Create the collection (cosine, ``dim``-D) if it does not yet exist."""
        from qdrant_client.models import Distance, VectorParams

        client = self._require()
        name = settings.qdrant_collection
        try:
            exists = client.collection_exists(name)
        except Exception as exc:
            raise VectorStoreError(f"Cannot reach Qdrant at {settings.qdrant_url}: {exc}") from exc

        if not exists:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )

    # ------------------------------------------------------------------ #
    # Write / read
    # ------------------------------------------------------------------ #

    def upsert(self, points: list[tuple[str, list[float], dict]]) -> int:
        """Upsert ``(id, vector, payload)`` tuples. Returns the count written."""
        from qdrant_client.models import PointStruct

        client = self._require()
        if not points:
            return 0
        structs = [PointStruct(id=pid, vector=vec, payload=payload) for pid, vec, payload in points]
        client.upsert(collection_name=settings.qdrant_collection, points=structs)
        return len(structs)

    def search(self, vector: list[float], top_k: int = 8) -> list[dict]:
        """Return the payloads of the ``top_k`` nearest records, each with score."""
        client = self._require()
        name = settings.qdrant_collection
        try:
            if not client.collection_exists(name):
                return []
            hits = client.search(
                collection_name=name,
                query_vector=vector,
                limit=top_k,
                with_payload=True,
            )
        except Exception as exc:
            raise VectorStoreError(f"Qdrant search failed: {exc}") from exc

        results = []
        for hit in hits:
            payload = dict(hit.payload or {})
            payload["_score"] = round(float(hit.score), 4)
            results.append(payload)
        return results

    def sample(self, limit: int = 20) -> list[dict]:
        """Return up to ``limit`` stored payloads (no vector needed).

        Used to derive content-aware question suggestions from whatever is
        actually indexed. Returns an empty list when the collection is absent.
        """
        client = self._require()
        name = settings.qdrant_collection
        try:
            if not client.collection_exists(name):
                return []
            points, _ = client.scroll(
                collection_name=name,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            raise VectorStoreError(f"Qdrant scroll failed: {exc}") from exc
        return [dict(p.payload or {}) for p in points]

    def count(self) -> int:
        """Number of vectors stored (0 when the collection is absent)."""
        client = self._require()
        name = settings.qdrant_collection
        try:
            if not client.collection_exists(name):
                return 0
            return client.count(collection_name=name, exact=True).count
        except Exception as exc:
            raise VectorStoreError(f"Qdrant count failed: {exc}") from exc


# Shared instance — the underlying qdrant-client manages its own connections.
vector_store = VectorStore()


def get_vector_store() -> VectorStore:
    """FastAPI dependency / accessor for the shared vector store."""
    return vector_store
