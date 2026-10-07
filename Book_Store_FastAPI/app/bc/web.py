"""Business Central chatbot — session web UI (mounted at ``/bc``).

* ``GET  /bc/chat`` — the chat page (with a "Sync now" button + live status).
* ``POST /bc/chat`` — answer one question via RAG over the Qdrant index.
* ``POST /bc/sync`` — admin-only ingest of BC records into Qdrant (JSON reply,
  called by the "Sync now" button via fetch).
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.auth.dependencies import require_web_role, require_web_user
from app.auth.models import User
from app.bc.client import BusinessCentralClient, get_bc_client
from app.bc.vectorstore import VectorStore, get_vector_store
from app.core.ai import ClaudeService, get_claude
from app.core.templating import render

from . import service
from .schemas import BCChatRequest

router = APIRouter(prefix="/bc", tags=["web-business-central"])
admin_role = require_web_role("admin")


@router.get("/chat")
def chat_page(
    request: Request,
    user: User = Depends(require_web_user),
    claude: ClaudeService = Depends(get_claude),
    client: BusinessCentralClient = Depends(get_bc_client),
    store: VectorStore = Depends(get_vector_store),
):
    return render(
        request,
        "bc/chat.html",
        {"is_admin": user.role == "admin", "bc": service.status(claude, client, store)},
        user=user,
    )


@router.post("/chat")
def chat_send(
    payload: BCChatRequest,
    user: User = Depends(require_web_user),
    claude: ClaudeService = Depends(get_claude),
    store: VectorStore = Depends(get_vector_store),
):
    reply = service.rag_chat(claude, store, payload.message)
    return JSONResponse({"reply": reply})


@router.get("/suggestions")
def chat_suggestions(
    _: User = Depends(require_web_user),
    claude: ClaudeService = Depends(get_claude),
    store: VectorStore = Depends(get_vector_store),
):
    """Content-aware suggested questions, derived from the indexed BC records."""
    return JSONResponse({"suggestions": service.suggestions(claude, store)})


@router.post("/sync")
def sync_now(
    user: User = Depends(admin_role),
    claude: ClaudeService = Depends(get_claude),
    client: BusinessCentralClient = Depends(get_bc_client),
    store: VectorStore = Depends(get_vector_store),
):
    return JSONResponse({"result": service.sync(claude, client, store)})
