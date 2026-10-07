"""LangChain tool-calling agent for BookBot (Feature 5).

This replaces the old manual "keyword-detect weather else RAG" branch with a
proper agent: the LLM is given a set of *tools* and decides which to call for a
given message. Your existing helpers become the tools, so the safety model is
unchanged — the model never sees raw SQL, only typed Python functions that run
parameterised queries.

The LLM backend is switchable via ``settings.ai_provider``:

* ``"groq"``      — free tool-calling backend (llama-3.3-70b). Needs GROQ_API_KEY.
* ``"anthropic"`` — reuse the Claude key/model already in config (paid credits).
* ``"ollama"``    — local model via Ollama (e.g. qwen2.5). No API key, no network.

All LangChain imports are performed lazily inside the functions below so that
this module (and :func:`agent_enabled`) can be imported even when the optional
``langchain`` packages are not installed — callers degrade gracefully.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.address.models import Address
from app.books.models import Book
from app.cart.models import Cart
from app.core.config import settings
from app.core.weather import get_weather
from app.orders.models import Order

# Shared system prompt — tells the agent when to reach for each tool.
_SYSTEM = (
    'You are "BookBot", a friendly assistant for an online bookstore.\n'
    "Use the available tools to answer:\n"
    "- Weather questions -> the `weather` tool (live data).\n"
    "- Book/product questions -> the `search_catalog` tool.\n"
    "- Questions about the customer's own purchases -> the `my_orders` tool.\n"
    "- Add a book to the cart -> the `add_to_cart` tool.\n"
    "- Buy / place an order -> the `place_order` tool. Only order when the customer "
    "clearly asks to buy, and state the book and quantity in your reply.\n"
    "Recommend specific titles with their price. Be concise and friendly. "
    "If a tool returns nothing useful, say so honestly rather than inventing facts."
)


def _find_book(db: Session, name: str) -> Book | None:
    """Resolve a book by exact title, then by a loose keyword match."""
    book = db.scalar(select(Book).where(Book.name == name))
    if book:
        return book
    return db.scalar(select(Book).where(Book.name.like(f"%{name}%")))


def agent_enabled() -> bool:
    """True when the configured chatbot backend has an API key.

    Independent of :attr:`ClaudeService.enabled` (which tracks the *Anthropic*
    key used by the other AI features) so the chatbot can run on Groq while the
    rest of the app has no Claude key.
    """
    if settings.ai_provider == "anthropic":
        return bool(settings.anthropic_api_key)
    if settings.ai_provider == "ollama":
        return True  # local, no key — assumed reachable; agent falls back on failure
    return bool(settings.groq_api_key)


def _make_llm():
    """Build the tool-calling chat model selected by ``settings.ai_provider``."""
    if settings.ai_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            temperature=0.3,
        )
    if settings.ai_provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0.3,
        )
    # Default: Groq (free tool-calling).
    from langchain_groq import ChatGroq

    return ChatGroq(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=0.3,
    )


def _build_tools(db: Session, user_id: int) -> list:
    """Wrap the existing data helpers as LangChain tools bound to this request.

    The tools close over ``db`` / ``user_id``; the model only supplies plain
    string arguments, never SQL, and ``my_orders`` is scoped to the signed-in
    user so the agent can never read another customer's purchases.
    """
    from langchain_core.tools import tool

    @tool
    def weather(city: str) -> str:
        """Get the current live weather for a city. Input: a city name."""
        return get_weather(city) or f"Sorry, I couldn't find the weather for '{city}'."

    @tool
    def search_catalog(query: str) -> str:
        """Search the bookstore catalog by title, author, or description keywords."""
        like = f"%{query}%"
        books = db.scalars(
            select(Book)
            .where(
                Book.name.like(like)
                | Book.author.like(like)
                | Book.description.like(like)
            )
            .limit(15)
        ).all()
        if not books:
            return "No matching books found in the catalog."
        return "\n".join(
            f"- {b.name} by {b.author} (Rs.{b.price}): {(b.description or '')[:120]}"
            for b in books
        )

    @tool
    def my_orders(query: str = "") -> str:
        """List the signed-in customer's own past orders (history/status)."""
        # Imported lazily to avoid a circular import (service imports this module).
        from app.ai.service import _order_context

        return _order_context(db, user_id)

    @tool
    def add_to_cart(book_name: str, quantity: int = 1) -> str:
        """Add a book to the signed-in customer's cart by title (default quantity 1)."""
        book = _find_book(db, book_name)
        if not book:
            return f"I couldn't find a book called '{book_name}' in the catalog."
        if book.quantity == 0:
            return f"'{book.name}' is out of stock."
        existing = db.scalar(
            select(Cart).where(Cart.book_id == book.id, Cart.user_id == user_id)
        )
        if existing:
            return f"'{book.name}' is already in your cart."
        db.add(Cart(book_id=book.id, user_id=user_id, book_quantity=max(1, quantity)))
        db.commit()
        return f"Added {max(1, quantity)} x '{book.name}' (Rs.{book.price}) to your cart."

    @tool
    def place_order(book_name: str, quantity: int = 1, address_id: int | None = None) -> str:
        """Place an order for the signed-in customer and deduct stock.

        If the customer has several saved addresses and none is given, returns the
        list so the agent can ask which address_id to ship to.
        """
        book = _find_book(db, book_name)
        if not book:
            return f"I couldn't find a book called '{book_name}' in the catalog."
        quantity = max(1, quantity)
        if book.quantity < quantity:
            return f"Only {book.quantity} of '{book.name}' left in stock."

        # Resolve the delivery address — always scoped to this customer.
        if address_id is not None:
            address = db.get(Address, address_id)
            if not address or address.user_id != user_id:
                return "That address id isn't one of yours."
        else:
            addresses = db.scalars(
                select(Address).where(Address.user_id == user_id)
            ).all()
            if not addresses:
                return "You have no saved address yet — please add one on the Address page first."
            if len(addresses) > 1:
                opts = "; ".join(f"#{a.id} ({a.address_type}, {a.city})" for a in addresses)
                return f"You have several addresses — which should I ship to? {opts}"
            address = addresses[0]

        from app.orders.web import _generate_order_id

        order = Order(
            user_id=user_id, book_id=book.id, address_id=address.id,
            order_id=_generate_order_id(),
        )
        db.add(order)
        book.quantity -= quantity
        db.commit()
        total = quantity * float(book.price)
        return (
            f"Order {order.order_id} placed: {quantity} x '{book.name}' "
            f"to {address.address_type} ({address.city}) — total Rs.{total:,.2f}."
        )

    return [weather, search_catalog, my_orders, add_to_cart, place_order]


def _output_text(output) -> str:
    """Flatten an AgentExecutor ``output`` into plain text.

    Groq (OpenAI-compatible) returns the reply as a plain string, but
    ``ChatAnthropic`` returns a list of content blocks
    (``[{"type": "text", "text": "..."}]``). Calling ``.strip()`` on that list
    raised ``AttributeError`` — swallowed by the caller's broad ``except`` — so
    the Anthropic chatbot silently fell back to the generic error. Handle both.
    """
    if isinstance(output, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in output
        ).strip()
    return (output or "").strip()


def run_agent(db: Session, user_id: int, message: str) -> tuple[str, list[str]]:
    """Run one chatbot turn through the LangChain agent.

    Returns ``(reply, trace)`` where ``trace`` is a human-readable line per
    tool the model chose to call, in order — built from
    ``AgentExecutor``'s ``intermediate_steps`` (``return_intermediate_steps``)
    so the UI can show *which decision the agent made*, not just its final
    text. An empty trace means the model answered directly, with no tool call.
    """
    from langchain.agents import AgentExecutor, create_tool_calling_agent
    from langchain_core.prompts import ChatPromptTemplate

    tools = _build_tools(db, user_id)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _SYSTEM),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )
    agent = create_tool_calling_agent(_make_llm(), tools, prompt)
    executor = AgentExecutor(
        agent=agent, tools=tools, max_iterations=4, verbose=False,
        return_intermediate_steps=True,
    )
    result = executor.invoke({"input": message})

    trace: list[str] = []
    for action, observation in result.get("intermediate_steps", []):
        tool_input = action.tool_input
        args = ", ".join(f"{k}={v!r}" for k, v in tool_input.items()) if isinstance(tool_input, dict) else repr(tool_input)
        trace.append(f"called `{action.tool}({args})`")
    return _output_text(result.get("output")), trace
