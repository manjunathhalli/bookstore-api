"""AI features — JWT REST API (parity with the session web UI).

Mounted under ``/api/ai``. Read/assistant endpoints require any authenticated
user; content-generation and analytics endpoints require the ``admin`` role,
mirroring the web split.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_api_user, require_api_role
from app.auth.models import User
from app.core.ai import ClaudeService, get_claude
from app.core.database import get_db

from . import service
from .schemas import (
    ChatRequest,
    DescriptionRequest,
    FineTunePredictRequest,
    SmartSearchRequest,
    TagRequest,
)

router = APIRouter(prefix="/ai", tags=["ai"])


def _serialize(book) -> dict:
    return {
        "id": book.id,
        "name": book.name,
        "author": book.author,
        "Price": book.price,
        "score": round(getattr(book, "score", 0.0), 4) if hasattr(book, "score") else None,
    }


def _require_enabled(claude: ClaudeService) -> None:
    if not claude.enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "AI is not configured")


# --------------------------------------------------------------------------- #
# Feature 5a — Chatbot (LangChain agent: catalog + orders + live weather)
# --------------------------------------------------------------------------- #


@router.post("/chat")
def chat(
    payload: ChatRequest,
    user: User = Depends(get_current_api_user),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    # chat_reply routes through the LangChain agent, picks the LLM backend, and
    # falls back to the free key-less weather tool when no chatbot key is set.
    reply, trace = service.chat_reply(claude, db, payload.message, user.id)
    return {"status": 200, "reply": reply, "trace": trace}


# --------------------------------------------------------------------------- #
# Feature 5c — Chatbot (LangGraph: same tools, explicit graph + confirmation)
# --------------------------------------------------------------------------- #


@router.post("/chat-graph")
def chat_graph(
    payload: ChatRequest,
    user: User = Depends(get_current_api_user),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    reply, trace = service.graph_chat_reply(claude, db, payload.message, user.id)
    return {"status": 200, "reply": reply, "trace": trace}


# --------------------------------------------------------------------------- #
# Feature 5b — Chatbot (classic RAG: Claude over the retrieved catalogue)
# --------------------------------------------------------------------------- #


@router.post("/chat-rag")
def chat_rag(
    payload: ChatRequest,
    user: User = Depends(get_current_api_user),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    # The classic RAG bot uses Anthropic directly (no tools, no live data).
    _require_enabled(claude)
    reply, trace = service.rag_chat_reply(claude, db, payload.message, user.id)
    return {"status": 200, "reply": reply, "trace": trace}


# --------------------------------------------------------------------------- #
# Feature 4 — Natural-language search
# --------------------------------------------------------------------------- #


@router.post("/smart-search")
def smart_search(
    payload: SmartSearchRequest,
    _: User = Depends(get_current_api_user),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    _require_enabled(claude)
    books, filters = service.smart_search(claude, db, payload.q)
    return {"status": 200, "filters": filters, "books": [_serialize(b) for b in books]}


# --------------------------------------------------------------------------- #
# Feature 10 — Semantic search
# --------------------------------------------------------------------------- #


@router.post("/semantic-search")
def semantic_search(
    payload: SmartSearchRequest,
    _: User = Depends(get_current_api_user),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    if not claude.embeddings_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Embeddings are not configured")
    books = service.semantic_search(claude, db, payload.q)
    return {"status": 200, "books": [_serialize(b) for b in books]}


@router.post("/reindex-embeddings")
def reindex_embeddings(
    _: User = Depends(require_api_role("admin")),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    if not claude.embeddings_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Embeddings are not configured")
    return {"status": 200, "reindexed": service.reindex_embeddings(claude, db)}


# --------------------------------------------------------------------------- #
# Feature 6 — Recommendations
# --------------------------------------------------------------------------- #


@router.get("/recommendations")
def recommendations(
    user: User = Depends(get_current_api_user),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    _require_enabled(claude)
    recs, basis = service.recommend(claude, db, user.id)
    return {
        "status": 200,
        "basis": basis,
        "recommendations": [
            {"book": _serialize(r["book"]), "reason": r["reason"]} for r in recs
        ],
    }


# --------------------------------------------------------------------------- #
# Feature 3 — Review summarization
# --------------------------------------------------------------------------- #


@router.get("/reviews/{book_id}/summary")
def review_summary(
    book_id: int,
    _: User = Depends(get_current_api_user),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    _require_enabled(claude)
    summary, count = service.summarize_reviews(claude, db, book_id)
    return {"status": 200, "summary": summary, "review_count": count}


# --------------------------------------------------------------------------- #
# Feature 2 — Description generator (admin)
# --------------------------------------------------------------------------- #


@router.post("/generate-description")
def generate_description(
    payload: DescriptionRequest,
    _: User = Depends(require_api_role("admin")),
    claude: ClaudeService = Depends(get_claude),
):
    _require_enabled(claude)
    description = service.generate_description(claude, payload.name, payload.author)
    if not description:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Description could not be generated")
    return {"status": 200, "description": description}


# --------------------------------------------------------------------------- #
# Feature 8 — Auto-tagging (admin)
# --------------------------------------------------------------------------- #


@router.post("/auto-tag")
def auto_tag(
    payload: TagRequest,
    _: User = Depends(require_api_role("admin")),
    claude: ClaudeService = Depends(get_claude),
):
    _require_enabled(claude)
    return {"status": 200, "tags": service.auto_tag(claude, payload.name, payload.description)}


# --------------------------------------------------------------------------- #
# Feature 9 — Demand forecasting (admin)
# --------------------------------------------------------------------------- #


@router.get("/forecast")
def forecast(
    _: User = Depends(require_api_role("admin")),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    _require_enabled(claude)
    return {"status": 200, "forecast": service.forecast(claude, db)}


# --------------------------------------------------------------------------- #
# Feature 11 — Fine-tuning (local classifier trained on this store's reviews)
# --------------------------------------------------------------------------- #


@router.get("/finetune/status")
def finetune_status(
    _: User = Depends(get_current_api_user),
    db: Session = Depends(get_db),
):
    return {"status": 200, **service.finetune_stats(db)}


@router.post("/finetune/train")
def finetune_train(
    _: User = Depends(require_api_role("admin")),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    try:
        meta = service.finetune_train(claude, db)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return {"status": 200, "trained": meta}


@router.post("/finetune/predict")
def finetune_predict(
    payload: FineTunePredictRequest,
    _: User = Depends(get_current_api_user),
    claude: ClaudeService = Depends(get_claude),
):
    return {"status": 200, **service.finetune_compare(claude, payload.text)}
