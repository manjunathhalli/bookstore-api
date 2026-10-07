"""Business Central chatbot — JWT REST API (mounted under ``/api/bc``).

Chat and status are open to any authenticated user; the ingest ("sync") is
admin-only, matching how the other data-loading/analytics endpoints are gated.
"""

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_api_user, require_api_role
from app.auth.models import User
from app.bc.client import BusinessCentralClient, get_bc_client
from app.bc.vectorstore import VectorStore, get_vector_store
from app.core.ai import ClaudeService, get_claude

from . import service
from .schemas import BCChatRequest

router = APIRouter(prefix="/bc", tags=["business-central"])


@router.get("/status")
def bc_status(
    _: User = Depends(get_current_api_user),
    claude: ClaudeService = Depends(get_claude),
    client: BusinessCentralClient = Depends(get_bc_client),
    store: VectorStore = Depends(get_vector_store),
):
    return {"status": 200, **service.status(claude, client, store)}


@router.post("/sync")
def bc_sync(
    _: User = Depends(require_api_role("admin")),
    claude: ClaudeService = Depends(get_claude),
    client: BusinessCentralClient = Depends(get_bc_client),
    store: VectorStore = Depends(get_vector_store),
):
    """Pull Business Central records (or sample data) into the Qdrant index."""
    return {"status": 200, "result": service.sync(claude, client, store)}


@router.get("/suggestions")
def bc_suggestions(
    _: User = Depends(get_current_api_user),
    claude: ClaudeService = Depends(get_claude),
    store: VectorStore = Depends(get_vector_store),
):
    """Content-aware suggested questions, derived from the indexed BC records."""
    return {"status": 200, "suggestions": service.suggestions(claude, store)}


@router.post("/chat")
def bc_chat(
    payload: BCChatRequest,
    _: User = Depends(get_current_api_user),
    claude: ClaudeService = Depends(get_claude),
    store: VectorStore = Depends(get_vector_store),
):
    reply = service.rag_chat(claude, store, payload.message)
    return {"status": 200, "reply": reply}
