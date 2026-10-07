"""AI feature logic — the reasoning layer shared by the web and API routers.

Each function here is the FastAPI equivalent of a controller method in the
Laravel AI Integration Guide. They combine the reusable :class:`ClaudeService`
(``app.core.ai``) with the project's SQLAlchemy models and reuse the existing
``book_store_product`` database — no feature stores anything the models don't
already own except the three AI columns added in the migration.

Every helper is defensive: on any :class:`AIError` (missing key, API outage) it
degrades gracefully rather than breaking the surrounding flow. Prompts constrain
the model to known labels / JSON keys and its output is always validated before
use — model output is never executed as code or SQL (all DB access goes through
SQLAlchemy bindings).
"""

from __future__ import annotations

import math

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.books.models import Book
from app.core.ai import AIError, ClaudeService
from app.core.weather import weather_answer
from app.feedback.models import Feedback
from app.orders.models import Order
from app.wishlist.models import WishList

# Labels/keys we accept back from the model — anything else is coerced/ignored.
_SENTIMENTS = {"Positive", "Neutral", "Negative"}


# --------------------------------------------------------------------------- #
# Feature 1 — Sentiment analysis on reviews
# --------------------------------------------------------------------------- #


def analyze_sentiment(claude: ClaudeService, feedback_text: str) -> str | None:
    """Classify a review as Positive / Neutral / Negative (fast model)."""
    system = (
        "You are a sentiment classifier. Reply with exactly one word: "
        "Positive, Neutral, or Negative."
    )
    try:
        label = claude.ask(
            f'Review: "{feedback_text}"', system, claude.fast_model, max_tokens=5
        ).strip()
    except AIError:
        return None
    return label if label in _SENTIMENTS else "Neutral"


# --------------------------------------------------------------------------- #
# Feature 7 — Content moderation
# --------------------------------------------------------------------------- #


def moderate(claude: ClaudeService, text_value: str) -> bool:
    """Return True when ``text_value`` is safe to store.

    Fail-open: on an API outage we never block a user over a non-critical
    review (see the guide's fail-open vs. fail-closed note). If no key is
    configured, moderation is simply skipped (returns True).
    """
    if not claude.enabled:
        return True
    system = (
        "You are a content moderator for a bookstore review section. Decide if "
        "the text contains hate, harassment, sexual content, or spam. Reply with "
        "ONLY the word SAFE or UNSAFE."
    )
    try:
        verdict = claude.ask(
            f'Text: "{text_value}"', system, claude.fast_model, max_tokens=5
        ).strip()
    except AIError:
        return True  # fail-open
    return verdict.upper() == "SAFE"


# --------------------------------------------------------------------------- #
# Feature 2 — AI book description generator (admin)
# --------------------------------------------------------------------------- #


def generate_description(claude: ClaudeService, name: str, author: str) -> str:
    """Write a 40–60 word marketing description for a book."""
    system = (
        "You are a bookstore copywriter. Write one engaging product description "
        "of 40-60 words. No headings."
    )
    prompt = f'Write a description for "{name}" by {author}.'
    try:
        return claude.ask(prompt, system, max_tokens=300).strip()
    except AIError:
        return ""


# --------------------------------------------------------------------------- #
# Feature 3 — Review summarization
# --------------------------------------------------------------------------- #


def summarize_reviews(claude: ClaudeService, db: Session, book_id: int) -> tuple[str, int]:
    """Condense up to 50 reviews of a book into a balanced 2–3 sentence summary.

    Returns ``(summary, review_count)`` so the UI can show exactly how many
    real reviews the summary was condensed from.
    """
    reviews = db.scalars(
        select(Feedback.feedback)
        .where(Feedback.book_id == book_id, Feedback.feedback.isnot(None))
        .limit(50)
    ).all()
    if not reviews:
        return "No reviews yet.", 0

    joined = "\n".join(f"{i + 1}. {r}" for i, r in enumerate(reviews))
    system = (
        "Summarize customer reviews in 2-3 sentences. Mention common praises and "
        "complaints. Be balanced."
    )
    try:
        return claude.ask(f"Reviews:\n{joined}", system, max_tokens=250).strip(), len(reviews)
    except AIError:
        return "The review summary is unavailable right now.", len(reviews)


# --------------------------------------------------------------------------- #
# Feature 4 — Natural-language search (intent parsing)
# --------------------------------------------------------------------------- #


def parse_search_filters(claude: ClaudeService, query: str) -> dict:
    """Turn a free-text query into a structured filter dict (never raw SQL)."""
    system = (
        "You convert a book-store search query into JSON filters.\n"
        "Return ONLY JSON with optional keys:\n"
        '  "keywords","author","max_price","min_price",\n'
        '  "sort" ("price_asc"|"price_desc"|"newest"). Omit unused keys.'
    )
    try:
        filters = claude.ask_json(query, system, claude.fast_model)
    except AIError:
        return {}
    return filters if isinstance(filters, dict) else {}


def smart_search(claude: ClaudeService, db: Session, query: str) -> tuple[list[Book], dict]:
    """Parse ``query`` into filters, then apply them with SQLAlchemy bindings."""
    filters = parse_search_filters(claude, query)

    stmt = select(Book)
    keywords = filters.get("keywords")
    if keywords:
        like = f"%{keywords}%"
        stmt = stmt.where((Book.name.like(like)) | (Book.description.like(like)))
    if filters.get("author"):
        stmt = stmt.where(Book.author.like(f"%{filters['author']}%"))
    # price is stored as a string column; filter in Python to compare numerically.
    books = list(db.scalars(stmt).all())

    def _price(b: Book) -> float:
        try:
            return float(b.price)
        except (TypeError, ValueError):
            return 0.0

    def _num(value) -> float | None:
        """Coerce a possibly-messy model value ("5,000", "under 500") to a float."""
        if value is None:
            return None
        try:
            return float(str(value).replace(",", "").strip())
        except (TypeError, ValueError):
            return None

    max_price = _num(filters.get("max_price"))
    if max_price is not None:
        books = [b for b in books if _price(b) <= max_price]
    min_price = _num(filters.get("min_price"))
    if min_price is not None:
        books = [b for b in books if _price(b) >= min_price]

    sort = filters.get("sort")
    if sort == "price_asc":
        books.sort(key=_price)
    elif sort == "price_desc":
        books.sort(key=_price, reverse=True)
    elif sort == "newest":
        books.sort(key=lambda b: b.id, reverse=True)

    return books, filters


# --------------------------------------------------------------------------- #
# Feature 5 — AI chatbot. Two independent variants share the retrieval helper
# below:
#   * chat_reply      — LangChain tool-calling agent (weather + catalog + orders)
#   * rag_chat_reply  — the original manual RAG (Claude over retrieved context)
# --------------------------------------------------------------------------- #


def _order_context(db: Session, user_id: int) -> str:
    """Build a short, grounded summary of the signed-in user's recent orders.

    Only this user's rows are ever loaded (filtered by ``user_id`` through a
    SQLAlchemy binding), so the bot can answer "what did I order?" or "where is
    my order?" without exposing anyone else's purchases.
    """
    rows = db.execute(
        select(Order.order_id, Book.name, Book.author, Book.price, Order.created_at)
        .join(Book, Order.book_id == Book.id)
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(20)
    ).all()
    if not rows:
        return "The customer has not placed any orders yet."

    lines = []
    for r in rows:
        ref = r.order_id or "N/A"
        placed = r.created_at.strftime("%Y-%m-%d") if r.created_at else "unknown date"
        lines.append(
            f"- Order #{ref}: \"{r.name}\" by {r.author} (Rs.{r.price}), placed {placed}"
        )
    return "\n".join(lines)


def chat_reply(claude: ClaudeService, db: Session, message: str, user_id: int) -> tuple[str, list[str]]:
    """Answer a shopper's question via the LangChain tool-calling agent.

    The agent (:mod:`app.ai.agent`) has tools for live weather, catalog search
    and the customer's own orders, and the LLM decides which to call — replacing
    the old manual keyword/RAG branch. The LLM backend is switchable (Groq by
    default, Anthropic optionally) via ``settings.ai_provider``.

    When no chatbot LLM key is configured we still answer weather questions from
    the free, key-less API so the integration can be tested without credentials.
    The ``claude`` argument is retained for signature compatibility with the
    other features but is unused here (the agent builds its own LLM).

    Returns ``(reply, trace)`` — ``trace`` lists the tool(s), if any, the agent
    chose to call this turn, so the UI can show *how* the answer was produced.
    """
    from app.ai.agent import agent_enabled, run_agent

    if not agent_enabled():
        answer = weather_answer(message)
        if answer:
            return answer, ["no LLM key configured -> answered from the free Open-Meteo weather API directly"]
        return "The AI assistant is not configured yet.", []
    try:
        return run_agent(db, user_id, message)
    except Exception:
        # Any agent/LLM/network failure: fall back to the key-less weather tool
        # when the question is weather-related, else a friendly error.
        answer = weather_answer(message)
        if answer:
            return answer, ["agent call failed -> fell back to the free Open-Meteo weather API"]
        return "Sorry, I'm having trouble reaching the assistant right now. Please try again.", []


def graph_chat_reply(claude: ClaudeService, db: Session, message: str, user_id: int) -> tuple[str, list[str]]:
    """Answer via the LangGraph agent (Feature 5c) — the same tools as
    :func:`chat_reply`, wired as an explicit graph so a `place_order` above
    :data:`app.ai.graph_agent.CONFIRM_THRESHOLD` pauses for a yes/no reply
    instead of buying immediately, and a short history persists across turns.

    Returns ``(reply, trace)`` — see :func:`app.ai.graph_agent.run_graph_agent`.
    """
    from app.ai.graph_agent import graph_agent_enabled, run_graph_agent

    if not graph_agent_enabled():
        answer = weather_answer(message)
        if answer:
            return answer, ["no LLM key configured -> answered from the free Open-Meteo weather API directly"]
        return "The AI assistant is not configured yet.", []
    try:
        return run_graph_agent(db, user_id, message)
    except Exception:
        answer = weather_answer(message)
        if answer:
            return answer, ["agent call failed -> fell back to the free Open-Meteo weather API"]
        return "Sorry, I'm having trouble reaching the assistant right now. Please try again.", []


def rag_chat_reply(claude: ClaudeService, db: Session, message: str, user_id: int) -> tuple[str, list[str]]:
    """Original RAG chatbot (Feature 5, classic variant).

    Retrieves up to 15 relevant books plus the user's recent orders, pastes them
    into the system prompt as grounding context, and asks Claude to answer using
    ONLY that context — no tools, no live data. Kept as a separate feature
    alongside the LangChain agent (:func:`chat_reply`); it uses the Anthropic
    :class:`ClaudeService` directly and needs ``ANTHROPIC_API_KEY``.

    Returns ``(reply, trace)`` — ``trace`` names the retrieval step that
    actually ran (keyword match vs. catalogue fallback) and how many rows it
    found, so the UI can show the "R" of RAG, not just the generated answer.
    """
    like = f"%{message}%"
    books = db.scalars(
        select(Book)
        .where((Book.name.like(like)) | (Book.author.like(like)) | (Book.description.like(like)))
        .limit(15)
    ).all()
    if books:
        retrieval_note = f"keyword search matched {len(books)} book(s) in name/author/description"
    else:
        # Fall back to a slice of the catalogue so the bot still has context.
        books = db.scalars(select(Book).order_by(Book.name).limit(15)).all()
        retrieval_note = f"no keyword match -> fell back to {len(books)} catalogue row(s) as context"

    catalog = "\n".join(
        f"- {b.name} by {b.author} (Rs.{b.price}): {(b.description or '')[:120]}"
        for b in books
    )
    orders = _order_context(db, user_id)
    system = (
        'You are "BookBot", a friendly bookstore assistant.\n'
        "Answer using ONLY the CATALOG and MY ORDERS sections below.\n"
        "- For product questions, recommend specific titles with price.\n"
        "- For order questions (order history, status, what/when they bought, "
        "order reference numbers), answer from MY ORDERS. These are the signed-in "
        "customer's own orders. If MY ORDERS is empty, say they have no orders yet.\n"
        f"CATALOG:\n{catalog}\n\nMY ORDERS:\n{orders}"
    )
    trace = [
        f"retrieve: {retrieval_note}",
        "augment: pasted those rows + your recent orders into the system prompt",
        "generate: Claude answered using ONLY that pasted context (no live DB access)",
    ]
    try:
        return claude.ask(message, system, max_tokens=600).strip(), trace
    except AIError:
        return "Sorry, I'm having trouble reaching the assistant right now. Please try again.", []


# --------------------------------------------------------------------------- #
# Feature 6 — Personalized recommendations
# --------------------------------------------------------------------------- #


def recommend(claude: ClaudeService, db: Session, user_id: int) -> tuple[list[dict], dict]:
    """Recommend up to 4 catalogue books for a user, each with a reason.

    Returns ``(recommendations, basis)`` — ``basis`` is the real counts fed
    into the prompt (ordered/wishlisted/catalogue sizes), so the UI can show
    exactly what evidence the model reasoned over.
    """
    ordered = db.scalars(
        select(Book.name)
        .join(Order, Order.book_id == Book.id)
        .where(Order.user_id == user_id)
        .distinct()
    ).all()
    wished = db.scalars(
        select(Book.name)
        .join(WishList, WishList.book_id == Book.id)
        .where(WishList.user_id == user_id)
        .distinct()
    ).all()

    catalog = db.scalars(select(Book)).all()
    by_id = {b.id: b for b in catalog}
    listing = "\n".join(f"{b.id}: {b.name} by {b.author}" for b in catalog)

    basis = {
        "ordered_count": len(ordered), "wishlist_count": len(wished),
        "catalog_count": len(catalog),
    }

    system = (
        "You are a book recommender. From the CATALOG pick up to 4 books the user "
        'will enjoy. Return ONLY a JSON array: [{"id":<id>,"reason":"<sentence>"}]. '
        "Do not recommend books already ordered."
    )
    prompt = (
        f"Ordered: {', '.join(ordered)}\n"
        f"Wishlist: {', '.join(wished)}\n\nCATALOG:\n{listing}"
    )

    try:
        picks = claude.ask_json(prompt, system)
    except AIError:
        return [], basis
    if not isinstance(picks, list):
        return [], basis

    recommendations: list[dict] = []
    for pick in picks:
        if not isinstance(pick, dict):
            continue
        # The model may return the id as a number or a string — coerce to int.
        try:
            book = by_id.get(int(pick.get("id")))
        except (TypeError, ValueError):
            book = None
        if book:
            recommendations.append({"book": book, "reason": pick.get("reason", "")})
    return recommendations, basis


# --------------------------------------------------------------------------- #
# Feature 8 — Auto-tagging / categorization
# --------------------------------------------------------------------------- #


def auto_tag(claude: ClaudeService, name: str, description: str) -> list[str]:
    """Return 1–4 lowercase genre tags for a book (fast model)."""
    system = (
        "You tag books by genre. From the title and description, return ONLY a "
        'JSON array of 1-4 lowercase genre tags, e.g. ["fiction","thriller","mystery"].'
    )
    prompt = f"Title: {name}\nDescription: {description}"
    try:
        tags = claude.ask_json(prompt, system, claude.fast_model)
    except AIError:
        return []
    if not isinstance(tags, list):
        return []
    return [t for t in tags if isinstance(t, str)][:4]


# --------------------------------------------------------------------------- #
# Feature 9 — Demand forecasting (admin)
# --------------------------------------------------------------------------- #


def forecast(claude: ClaudeService, db: Session) -> list[dict]:
    """Rank likely-to-sell titles from real order counts + AI reasoning.

    Uses all-time order counts (a fresh store rarely has 90 days of history);
    the aggregation is real DB data, the model only interprets and ranks it.
    """
    rows = db.execute(
        select(
            Book.name,
            func.count(Order.id).label("orders_count"),
            Book.quantity.label("stock"),
        )
        .join(Order, Order.book_id == Book.id)
        .group_by(Book.id, Book.name, Book.quantity)
        .order_by(func.count(Order.id).desc())
        .limit(30)
    ).all()
    if not rows:
        return []

    data = "\n".join(
        f"{r.name}: {r.orders_count} orders, {r.stock} in stock" for r in rows
    )
    system = (
        "You are a demand-forecasting analyst for a bookstore. Given order counts "
        "and current stock, return ONLY a JSON array of up to 8 objects: "
        '[{"book":"<name>","trend":"rising|steady|falling","restock":true|false,'
        '"reason":"<short>"}]. Flag restock=true when demand is high but stock is low.'
    )
    try:
        result = claude.ask_json(f"DATA:\n{data}", system)
    except AIError:
        return []
    return result if isinstance(result, list) else []


# --------------------------------------------------------------------------- #
# Feature 10 — Semantic search (embeddings + cosine similarity)
# --------------------------------------------------------------------------- #


def embed_book_text(claude: ClaudeService, name: str, author: str, description: str) -> list[float]:
    """Build and embed the searchable text for a book (local model)."""
    return claude.embed(f"{name} {author} {description}")


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors."""
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def semantic_search(claude: ClaudeService, db: Session, query: str, limit: int = 12) -> list[Book]:
    """Rank books whose stored embedding is closest in meaning to ``query``."""
    try:
        query_vec = claude.embed(query)
    except AIError:
        return []
    if not query_vec:
        return []

    scored: list[tuple[float, Book]] = []
    for book in db.scalars(select(Book).where(Book.embedding.isnot(None))).all():
        score = cosine(query_vec, book.embedding or [])
        book.score = score  # transient attribute for the template
        scored.append((score, book))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [book for _, book in scored[:limit]]


def reindex_embeddings(claude: ClaudeService, db: Session) -> int:
    """Generate embeddings for every book missing one. Returns the count done."""
    done = 0
    for book in db.scalars(select(Book).where(Book.embedding.is_(None))).all():
        try:
            book.embedding = embed_book_text(claude, book.name, book.author, book.description)
            done += 1
        except AIError:
            break  # stop on outage; keep what we have
    if done:
        db.commit()
    return done


# --------------------------------------------------------------------------- #
# Feature 11 — Fine-tuning: a classifier trained on this store's own reviews,
# shown side-by-side with the zero-shot LLM classifier (Feature 1).
# --------------------------------------------------------------------------- #


def finetune_stats(db: Session) -> dict:
    """Labelled-data readiness plus the last training run's metadata, if any."""
    from app.ai.finetune import dataset_stats, finetuned_enabled, metadata

    stats = dataset_stats(db)
    stats["trained"] = finetuned_enabled()
    stats["meta"] = metadata()
    return stats


def finetune_train(claude: ClaudeService, db: Session) -> dict:
    """Train (or retrain) the local classifier. Raises ValueError if not ready."""
    from app.ai.finetune import train

    return train(claude, db)


def finetune_compare(claude: ClaudeService, text: str) -> dict:
    """Zero-shot LLM classifier (Feature 1) vs. the fine-tuned local one (Feature 11)."""
    from app.ai.finetune import predict

    zero_shot = analyze_sentiment(claude, text) if claude.enabled else None
    finetuned = predict(claude, text)
    return {"zero_shot": zero_shot, "finetuned": finetuned}
