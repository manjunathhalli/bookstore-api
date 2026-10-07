"""Business Central RAG chatbot — reasoning layer.

Two operations, mirroring the two things the user asked for:

* :func:`sync` — the manual "Sync now" action. Pulls records from Business
  Central (or sample data), turns *every field* of each record into a text
  blob, embeds it with the local model, and upserts the vectors into Qdrant.
* :func:`rag_chat` — the query-time path. Embeds the question, retrieves the
  most similar records from Qdrant, and asks the LLM to answer using ONLY that
  retrieved context (classic RAG, so the bot never invents figures).

Embeddings reuse :class:`app.core.ai.ClaudeService` (local sentence-transformers,
384-D, normalised) and the LLM reuses the same service's switchable Groq/Anthropic
backend — no new keys beyond the BC/Qdrant config.
"""

from __future__ import annotations

from app.bc.client import BusinessCentralClient
from app.bc.vectorstore import VectorStore, point_id
from app.core.ai import AIError, ClaudeService
from app.core.config import settings

# Keys that best identify a record, tried in order, for its Qdrant point id.
_KEY_FIELDS = ("number", "id", "no", "documentNumber", "code", "displayName")

# Records embedded + upserted per batch during sync (see :func:`sync`).
_EMBED_BATCH = 256

_SYSTEM = (
    "You are a data assistant for a Microsoft Business Central deployment.\n"
    "Answer the user's question using ONLY the CONTEXT records below, which were "
    "retrieved from the company's Business Central data (items, customers, sales "
    "orders, etc.).\n"
    "- Quote concrete values (numbers, quantities, prices, statuses, names) from "
    "the records.\n"
    "- If several records are relevant, summarise them clearly (a short list or "
    "table is fine).\n"
    "- If the CONTEXT does not contain the answer, say so plainly — never invent "
    "figures or records."
)


def _record_key(entity: str, record: dict, index: int) -> str:
    """Pick a stable business key for a record (falls back to its position)."""
    for field in _KEY_FIELDS:
        value = record.get(field)
        if value:
            return str(value)
    return f"row-{index}"


def record_to_text(entity: str, record: dict) -> str:
    """Flatten every field of a record into embeddable "Field: value" text.

    Includes the entity name as a header so a query like "sales order" retrieves
    the right kind of record even when no single field repeats the word.
    """
    lines = [f"Business Central {entity} record:"]
    for field, value in record.items():
        if value is None or value == "":
            continue
        if isinstance(value, (dict, list)):
            # Nested BC structures (e.g. dimensions) — keep them, compactly.
            value = str(value)
        label = field[0].upper() + field[1:]
        lines.append(f"{label}: {value}")
    return "\n".join(lines)


def sync(claude: ClaudeService, client: BusinessCentralClient, store: VectorStore) -> dict:
    """Pull configured BC entities, embed every record, upsert into Qdrant.

    Returns a summary dict: overall status, the data source per entity, and how
    many vectors were written. Safe to call repeatedly — deterministic point ids
    mean re-syncing updates existing records in place instead of duplicating.
    """
    if not claude.embeddings_enabled:
        return {"ok": False, "error": "Embeddings unavailable (install 'sentence-transformers')."}
    if not store.available:
        return {
            "ok": False,
            "error": (
                f"Qdrant is not reachable ({store.location}). "
                "For embedded mode, ensure QDRANT_PATH is set and writable; for a "
                "server, start it (docker run -p 6333:6333 qdrant/qdrant) or check QDRANT_URL."
            ),
        }

    # Probe the embedding dimension once so the collection matches the model.
    try:
        dim = len(claude.embed("dimension probe"))
    except AIError as exc:
        return {"ok": False, "error": str(exc)}
    store.ensure_collection(dim)

    per_entity: list[dict] = []
    errors: list[str] = []
    total = 0
    for entity in settings.bc_entity_list:
        records, source, error = client.fetch(entity)
        if error:
            # Live fetch failed and we fell back to sample data — record why so
            # a misconfiguration (wrong environment, entity, credentials) is
            # visible in the UI instead of silently showing "(sample)".
            errors.append(f"{entity}: {error}")
            if not records:
                # No bundled sample data for this entity (e.g. a custom OData
                # web service), so the fallback is empty. Skip the upsert — which
                # would report a misleading "0 records (sample)" — and leave any
                # previously-indexed vectors for this entity untouched.
                per_entity.append(
                    {"entity": entity, "records": 0, "source": source, "error": error}
                )
                continue
        # Prepare (id, text, payload) for every record first, then embed and
        # upsert in batches. Batched embedding is dramatically faster than one
        # call per record, and upserting per batch keeps memory bounded and lets
        # the indexed count grow visibly as a large sync progresses.
        prepared: list[tuple[str, str, dict]] = []
        for index, record in enumerate(records):
            text = record_to_text(entity, record)
            key = _record_key(entity, record, index)
            payload = {"entity": entity, "key": key, "text": text, "source": source, **record}
            prepared.append((point_id(entity, key), text, payload))

        written = 0
        for start in range(0, len(prepared), _EMBED_BATCH):
            chunk = prepared[start : start + _EMBED_BATCH]
            try:
                vectors = claude.embed_many([text for _, text, _ in chunk])
            except AIError as exc:
                return {"ok": False, "error": str(exc), "written_so_far": total + written}
            points = [(pid, vec, payload) for (pid, _, payload), vec in zip(chunk, vectors)]
            written += store.upsert(points)
        total += written
        entry = {"entity": entity, "records": written, "source": source}
        if error:
            entry["error"] = error
        per_entity.append(entry)

    result = {
        "ok": True,
        "total": total,
        "entities": per_entity,
        "collection": settings.qdrant_collection,
    }
    if errors:
        # Surface the live-fetch failure(s) at the top level too, so the UI can
        # show a warning even when it only reads a single summary field. Only
        # claim "used sample data" when a fallback actually produced records —
        # otherwise the failure left the index unchanged.
        used_sample = any(e["source"] == "sample" and e["records"] for e in per_entity)
        lead = (
            "Live Business Central fetch failed; used sample data. "
            if used_sample
            else "Live Business Central fetch failed; no sample data for these entities, so nothing was re-indexed. "
        )
        result["warning"] = lead + "; ".join(errors)
    return result


def rag_chat(claude: ClaudeService, store: VectorStore, message: str, top_k: int = 8) -> str:
    """Answer ``message`` from the most similar BC records stored in Qdrant."""
    if not claude.embeddings_enabled:
        return "The assistant needs the local embedding model (install 'sentence-transformers')."
    if not store.available:
        return (
            f"The vector database is not reachable ({store.location}). "
            "Check QDRANT_PATH (embedded) or start a Qdrant server, then click “Sync now”."
        )

    try:
        query_vec = claude.embed(message)
        matches = store.search(query_vec, top_k=top_k)
    except (AIError, Exception):  # noqa: BLE001 — degrade on any retrieval failure
        return "Sorry, I couldn't search the Business Central data right now. Please try again."

    if not matches:
        return (
            "I don't have any Business Central data indexed yet. "
            "Click “Sync now” to load it, then ask again."
        )

    context = "\n\n".join(f"[{i + 1}] {m.get('text', '')}" for i, m in enumerate(matches))
    system = f"{_SYSTEM}\n\nCONTEXT:\n{context}"
    if not claude.enabled:
        # No LLM key: still useful — return the retrieved records directly.
        return (
            "The LLM backend isn't configured, so here are the most relevant "
            f"Business Central records I found:\n\n{context}"
        )
    try:
        return claude.ask(message, system, max_tokens=700).strip()
    except AIError:
        return "Sorry, I'm having trouble reaching the assistant right now. Please try again."


_SUGGEST_SYSTEM = (
    "You help users explore a Microsoft Business Central dataset via a chatbot.\n"
    "Given a SAMPLE of the indexed records below, propose short, natural questions "
    "a user could ask that the data can actually answer.\n"
    "- Ground every question in fields/values that appear in the sample (document "
    "types, locations, item names, vendors, dates, quantities, statuses…).\n"
    "- Keep each question under 12 words, specific, and answerable from this data.\n"
    "- Vary them (counts, filters by a value, summaries, look-ups).\n"
    'Respond with ONLY JSON: {"questions": ["...", "..."]}'
)

# Fields worth turning into "which/how many by X" suggestions, in priority order.
_SUGGEST_FACETS = (
    "Document_Type", "Entry_Type", "Location_Code", "documentType", "status",
    "itemCategoryCode", "city", "type", "customerName",
)


def _fallback_suggestions(entity: str, records: list[dict], n: int) -> list[str]:
    """Deterministic suggestions from real field values (no LLM needed)."""
    label = entity.replace("_", " ").lower()
    out: list[str] = [f"How many {label} are indexed?", f"Summarize the {label}."]
    for field in _SUGGEST_FACETS:
        values: list[str] = []
        for rec in records:
            val = rec.get(field)
            if val not in (None, "", " ") and str(val) not in values:
                values.append(str(val))
            if len(values) >= 2:
                break
        pretty = field.replace("_", " ").lower()
        for val in values:
            out.append(f"Which {label} have {pretty} “{val}”?")
    # De-dupe preserving order, then trim to n.
    seen: set[str] = set()
    unique = [q for q in out if not (q in seen or seen.add(q))]
    return unique[:n]


def suggestions(claude: ClaudeService, store: VectorStore, n: int = 6) -> list[str]:
    """Content-aware question suggestions derived from the indexed records.

    Samples what's actually in Qdrant and asks the LLM to propose questions the
    data can answer; falls back to deterministic, value-based prompts when the
    LLM is unavailable. Returns ``[]`` when nothing is indexed yet.
    """
    if not store.available:
        return []
    try:
        records = store.sample(20)
    except Exception:  # noqa: BLE001 — suggestions are best-effort
        return []
    if not records:
        return []

    entity = str(records[0].get("entity") or (settings.bc_entity_list or ["records"])[0])

    if claude.enabled:
        # Compact context: the pre-flattened "text" of a few records.
        blobs = [str(r.get("text") or "") for r in records[:8] if r.get("text")]
        context = "\n\n".join(blobs)[:4000]
        system = f"{_SUGGEST_SYSTEM}\n\nSAMPLE RECORDS:\n{context}"
        try:
            data = claude.ask_json(f"Propose {n} questions.", system, max_tokens=400)
            qs = data.get("questions") if isinstance(data, dict) else None
            cleaned = [str(q).strip() for q in (qs or []) if str(q).strip()]
            if cleaned:
                return cleaned[:n]
        except AIError:
            pass  # fall through to deterministic suggestions

    return _fallback_suggestions(entity, records, n)


def status(claude: ClaudeService, client: BusinessCentralClient, store: VectorStore) -> dict:
    """Small status snapshot for the UI (config + how many vectors are indexed)."""
    try:
        indexed = store.count() if store.available else 0
    except Exception:  # noqa: BLE001
        indexed = 0
    return {
        "bc_configured": client.configured,
        "qdrant_available": store.available,
        "embeddings_enabled": claude.embeddings_enabled,
        "llm_enabled": claude.enabled,
        "indexed": indexed,
        "entities": settings.bc_entity_list,
    }
