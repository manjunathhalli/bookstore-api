"""AI features — session web UI (parity with the Laravel AI Blade controllers).

Mounted at ``/ai``. Browsing/chat/search/recommendations are open to any signed
in user; the description generator, demand forecast and embedding reindex are
admin-only, matching the guide's split between shopper- and admin-facing tools.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import require_web_role, require_web_user
from app.auth.models import User
from app.ai.agent import agent_enabled
from app.core.ai import ClaudeService, get_claude
from app.core.database import get_db
from app.core.templating import flash, render

from . import service
from .schemas import ChatRequest, DescriptionRequest, FineTunePredictRequest

router = APIRouter(prefix="/ai", tags=["web-ai"])
admin_role = require_web_role("admin")


# --------------------------------------------------------------------------- #
# Hub
# --------------------------------------------------------------------------- #


@router.get("")
def hub(
    request: Request,
    user: User = Depends(require_web_user),
    claude: ClaudeService = Depends(get_claude),
):
    return render(
        request,
        "ai/hub.html",
        {"is_admin": user.role == "admin", "ai_enabled": claude.enabled,
         "embeddings_enabled": claude.embeddings_enabled,
         "config_key": claude.key_env_name},
        user=user,
    )


# --------------------------------------------------------------------------- #
# Feature 5a — AI chatbot (LangChain agent: catalog + orders + live weather)
# --------------------------------------------------------------------------- #


@router.get("/chat")
def chat_page(
    request: Request,
    user: User = Depends(require_web_user),
    claude: ClaudeService = Depends(get_claude),
):
    return render(
        request,
        "ai/chat.html",
        {
            "ai_enabled": agent_enabled(),
            "post_url": "/ai/chat",
            "config_key": "GROQ_API_KEY",
            "chat_page_title": "AI Chatbot (Agent)",
            "chat_h1": "🤖 BookBot Agent",
            "chat_subtitle": "A LangChain agent that picks tools — books, your orders, or live weather.",
            "suggestions": [
                "Recommend a mystery book under 500",
                "What's the weather in Bengaluru?",
                "What have I ordered so far?",
                "Add Clean Code to my cart",
            ],
        },
        user=user,
    )


@router.post("/chat")
def chat_send(
    payload: ChatRequest,
    user: User = Depends(require_web_user),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    # chat_reply routes through the LangChain agent, selects the LLM backend,
    # and falls back to the free key-less weather tool when no key is set.
    reply, trace = service.chat_reply(claude, db, payload.message, user.id)
    return JSONResponse({"reply": reply, "trace": trace})


# --------------------------------------------------------------------------- #
# Feature 5c — AI chatbot (LangGraph: same tools, explicit graph + confirmation)
# --------------------------------------------------------------------------- #


@router.get("/graph-chat")
def graph_chat_page(
    request: Request,
    user: User = Depends(require_web_user),
    claude: ClaudeService = Depends(get_claude),
):
    return render(
        request,
        "ai/chat.html",
        {
            "ai_enabled": agent_enabled(),
            "post_url": "/ai/graph-chat",
            "config_key": "GROQ_API_KEY",
            "chat_page_title": "AI Chatbot (LangGraph)",
            "chat_h1": "🕸️ BookBot Graph Agent",
            "chat_subtitle": (
                "Same tools as the Agent chatbot, wired as an explicit LangGraph graph — "
                "orders over Rs.2,000 pause for your yes/no confirmation, and it remembers "
                "the last few turns."
            ),
            "suggestions": [
                "Order 5 copies of The Midnight Library",
                "Recommend a thriller under 500",
                "What's the weather in Mysuru?",
                "What have I ordered before?",
            ],
        },
        user=user,
    )


@router.post("/graph-chat")
def graph_chat_send(
    payload: ChatRequest,
    user: User = Depends(require_web_user),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    reply, trace = service.graph_chat_reply(claude, db, payload.message, user.id)
    return JSONResponse({"reply": reply, "trace": trace})


# --------------------------------------------------------------------------- #
# Feature 5b — AI chatbot (classic RAG: Claude over the retrieved catalogue)
# --------------------------------------------------------------------------- #


@router.get("/rag-chat")
def rag_chat_page(
    request: Request,
    user: User = Depends(require_web_user),
    claude: ClaudeService = Depends(get_claude),
):
    return render(
        request,
        "ai/chat.html",
        {
            "ai_enabled": claude.enabled,
            "post_url": "/ai/rag-chat",
            "config_key": claude.key_env_name,
            "chat_page_title": "AI Chatbot (RAG)",
            "chat_h1": "💬 BookBot (RAG)",
            "chat_subtitle": "Classic RAG — answers grounded only in our real catalogue and your orders.",
            "suggestions": [
                "What fantasy books do you have?",
                "Recommend something by George Orwell",
                "What did I order last?",
                "Tell me about your cheapest books",
            ],
        },
        user=user,
    )


@router.post("/rag-chat")
def rag_chat_send(
    payload: ChatRequest,
    user: User = Depends(require_web_user),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    if not claude.enabled:
        return JSONResponse(
            {"reply": "The RAG assistant is not configured yet (set ANTHROPIC_API_KEY).", "trace": []}
        )
    reply, trace = service.rag_chat_reply(claude, db, payload.message, user.id)
    return JSONResponse({"reply": reply, "trace": trace})


# --------------------------------------------------------------------------- #
# Feature 4 — Natural-language search  &  Feature 10 — Semantic search
# --------------------------------------------------------------------------- #


@router.get("/search")
def smart_search(
    request: Request,
    q: str = "",
    user: User = Depends(require_web_user),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    books: list = []
    filters: dict = {}
    query = q.strip()
    if query and claude.enabled:
        books, filters = service.smart_search(claude, db, query)
    return render(
        request,
        "ai/search.html",
        {
            "mode": "smart",
            "title": "Natural-Language Search",
            "subtitle": "Ask in plain English — e.g. “cheap thrillers under 500”.",
            "action": "/ai/search",
            "query": query,
            "books": books,
            "filters": filters,
            "ai_enabled": claude.enabled,
            "suggestions": [
                "cheap thrillers under 500",
                "books by George Orwell",
                "expensive books sorted by price",
                "newest books under 1000",
            ],
        },
        user=user,
    )


@router.get("/semantic")
def semantic_search(
    request: Request,
    q: str = "",
    user: User = Depends(require_web_user),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    books: list = []
    query = q.strip()
    if query and claude.embeddings_enabled:
        books = service.semantic_search(claude, db, query)
    return render(
        request,
        "ai/search.html",
        {
            "mode": "semantic",
            "title": "Semantic Search",
            "subtitle": "Search by meaning — e.g. “overcoming fear and building confidence”.",
            "action": "/ai/semantic",
            "query": query,
            "books": books,
            "filters": {},
            "ai_enabled": claude.embeddings_enabled,
            "suggestions": [
                "overcoming fear and building confidence",
                "a story about time travel and regret",
                "space adventure with a strong female lead",
                "learning to code from scratch",
            ],
        },
        user=user,
    )


@router.post("/reindex-embeddings")
def reindex_embeddings(
    request: Request,
    user: User = Depends(admin_role),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    if not claude.embeddings_enabled:
        flash(request, "Embeddings are unavailable (install 'fastembed').", "error")
    else:
        count = service.reindex_embeddings(claude, db)
        flash(request, f"Generated embeddings for {count} book(s).")
    return RedirectResponse("/ai/semantic", status_code=303)


# --------------------------------------------------------------------------- #
# Feature 6 — Personalized recommendations
# --------------------------------------------------------------------------- #


@router.get("/recommendations")
def recommendations(
    request: Request,
    user: User = Depends(require_web_user),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    recs, basis = service.recommend(claude, db, user.id) if claude.enabled else ([], {})
    return render(
        request,
        "ai/recommendations.html",
        {"recommended": recs, "basis": basis, "ai_enabled": claude.enabled},
        user=user,
    )


# --------------------------------------------------------------------------- #
# Feature 9 — Demand forecasting (admin)
# --------------------------------------------------------------------------- #


@router.get("/forecast")
def forecast(
    request: Request,
    user: User = Depends(admin_role),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    rows = service.forecast(claude, db) if claude.enabled else []
    return render(
        request,
        "ai/forecast.html",
        {"forecast": rows, "ai_enabled": claude.enabled},
        user=user,
    )


# --------------------------------------------------------------------------- #
# Feature 2 — Book description generator (admin, called via fetch)
# --------------------------------------------------------------------------- #


@router.post("/books/generate-description")
def generate_description(
    payload: DescriptionRequest,
    user: User = Depends(admin_role),
    claude: ClaudeService = Depends(get_claude),
):
    if not claude.enabled:
        return JSONResponse({"error": "AI is not configured."}, status_code=503)
    description = service.generate_description(claude, payload.name, payload.author)
    return JSONResponse({"description": description})


# --------------------------------------------------------------------------- #
# Feature 3 — Review summarization (called via fetch from the feedback page)
# --------------------------------------------------------------------------- #


@router.post("/reviews/summary")
def review_summary(
    book_id: int = Form(...),
    user: User = Depends(require_web_user),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    if not claude.enabled:
        return JSONResponse({"summary": "The AI summary feature is not configured.", "count": 0})
    summary, count = service.summarize_reviews(claude, db, book_id)
    return JSONResponse({"summary": summary, "count": count})


# --------------------------------------------------------------------------- #
# Feature 11 — Fine-tuning (admin): train + test a classifier on real reviews
# --------------------------------------------------------------------------- #


@router.get("/finetune")
def finetune_page(
    request: Request,
    user: User = Depends(admin_role),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    return render(
        request,
        "ai/finetune.html",
        {"stats": service.finetune_stats(db), "embeddings_enabled": claude.embeddings_enabled},
        user=user,
    )


@router.post("/finetune/train")
def finetune_train(
    request: Request,
    user: User = Depends(admin_role),
    claude: ClaudeService = Depends(get_claude),
    db: Session = Depends(get_db),
):
    try:
        meta = service.finetune_train(claude, db)
        flash(
            request,
            f"Fine-tuned on {meta['n_examples']} reviews — "
            f"{'holdout' if meta['holdout'] else 'train'} accuracy {meta['accuracy']:.0%}.",
        )
    except ValueError as exc:
        flash(request, str(exc), "error")
    return RedirectResponse("/ai/finetune", status_code=303)


@router.post("/finetune/predict")
def finetune_predict(
    payload: FineTunePredictRequest,
    user: User = Depends(admin_role),
    claude: ClaudeService = Depends(get_claude),
):
    return JSONResponse(service.finetune_compare(claude, payload.text))
