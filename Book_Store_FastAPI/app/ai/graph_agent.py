"""LangGraph agent — BookBot as an explicit graph (Feature 5c).

:mod:`app.ai.agent` runs a fixed LangChain loop (think -> call a tool ->
observe -> repeat). This module builds the *same* tools into an explicit
graph instead, so the control flow can branch — something a plain loop
can't express cleanly:

* Placing an order over :data:`CONFIRM_THRESHOLD` routes to a "confirm" node
  that asks the shopper to reply yes/no, instead of buying immediately.
* A short conversation history is kept per user (in-memory) so the graph
  agent — unlike the one-shot :mod:`app.ai.agent` chatbot — has multi-turn
  memory: it can resolve "yes" on the *next* request to the order it asked
  about on this one.

The LLM backend is the same switchable provider as the other chatbot
(``settings.ai_provider``); tools are reused unmodified from
:mod:`app.ai.agent` so the safety model (typed Python functions, never raw
SQL, orders/carts scoped to the signed-in user) is identical.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .agent import _build_tools, _find_book, _make_llm, _output_text, agent_enabled

CONFIRM_THRESHOLD = 2000.0  # orders above this pause for an explicit "yes"
_HISTORY_TURNS = 6  # keep the last N human/assistant messages per user

_CONFIRM_WORDS = {"yes", "y", "confirm", "confirm order", "ok", "okay", "yep", "sure"}
_CANCEL_WORDS = {"no", "n", "cancel", "cancel order", "nope"}

# In-memory per-user state. A single-process dev app has nowhere else to put
# this without adding infrastructure; a real deployment would move both dicts
# to Redis/DB rows keyed by session, exactly like app.books.cache does for the
# catalogue cache.
_history: dict[int, list] = {}
_pending: dict[int, dict] = {}


def graph_agent_enabled() -> bool:
    """Same availability rule as the plain agent — same providers, same keys."""
    return agent_enabled()


def _remember(user_id: int, messages: list) -> None:
    """Keep only clean human/assistant text turns (drop tool-call plumbing)."""
    from langchain_core.messages import AIMessage, HumanMessage

    clean = [
        m for m in messages
        if isinstance(m, (HumanMessage, AIMessage)) and not getattr(m, "tool_calls", None)
    ]
    _history[user_id] = clean[-_HISTORY_TURNS:]


def _build_graph(db: Session, user_id: int, tools: list):
    """Compile the graph: agent -> (tools | confirm | end), tools -> agent."""
    from langchain_core.messages import AIMessage
    from langgraph.graph import END, MessagesState, StateGraph
    from langgraph.prebuilt import ToolNode

    llm = _make_llm().bind_tools(tools)

    # No type annotations on these nested functions: langgraph's add_node()
    # calls get_type_hints() on them, which resolves annotations against the
    # function's __globals__ (the *module*, not this enclosing closure) — with
    # `from __future__ import annotations` deferring evaluation, a annotation
    # naming a name only imported locally above (MessagesState) raises
    # NameError at graph-build time instead of just being skipped.
    def call_model(state):
        return {"messages": [llm.invoke(state["messages"])]}

    def confirm_node(state):
        last = state["messages"][-1]
        call = next(c for c in last.tool_calls if c["name"] == "place_order")
        args = call["args"] or {}
        book = _find_book(db, args.get("book_name", ""))
        quantity = max(1, int(args.get("quantity") or 1))
        if not book:
            text = f"I couldn't find a book called '{args.get('book_name')}' to order."
        else:
            total = quantity * float(book.price)
            _pending[user_id] = {
                "book_name": book.name, "quantity": quantity,
                "address_id": args.get("address_id"),
            }
            text = (
                f"That's {quantity} x '{book.name}' (Rs.{book.price} each) = Rs.{total:,.2f}. "
                "Reply 'yes' to confirm the order, or 'no' to cancel."
            )
        return {"messages": [AIMessage(content=text)]}

    def route(state):
        calls = getattr(state["messages"][-1], "tool_calls", None) or []
        if not calls:
            return END
        if any(c["name"] == "place_order" for c in calls):
            return "confirm"
        return "tools"

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("confirm", confirm_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", route, {"tools": "tools", "confirm": "confirm", END: END})
    graph.add_edge("tools", "agent")
    graph.add_edge("confirm", END)
    return graph.compile()


def run_graph_agent(db: Session, user_id: int, message: str) -> tuple[str, list[str]]:
    """Run one turn through the graph, resolving any pending order first.

    Returns ``(reply, trace)`` — ``trace`` names the graph node(s) this turn
    actually passed through (``tools`` entries show which tool ran, from the
    ``ToolMessage``s LangGraph appends to the message list), so the UI can
    show the branch the graph took, not just the LangChain-agent tool list.
    """
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    text = message.strip()
    lower = text.lower()
    tools = _build_tools(db, user_id)

    pending = _pending.pop(user_id, None)
    if pending is not None:
        if lower in _CONFIRM_WORDS:
            place_order = next(t for t in tools if t.name == "place_order")
            reply = place_order.invoke(pending)
            _remember(user_id, _history.get(user_id, []) + [
                HumanMessage(content=text), AIMessage(content=reply),
            ])
            return reply, ["resolved pending confirmation -> called `place_order` directly (no LLM call this turn)"]
        if lower in _CANCEL_WORDS:
            reply = "Order cancelled."
            _remember(user_id, _history.get(user_id, []) + [
                HumanMessage(content=text), AIMessage(content=reply),
            ])
            return reply, ["resolved pending confirmation -> cancelled (no LLM call this turn)"]
        # Any other reply means the shopper moved on — drop the stale
        # confirmation instead of silently blocking their new question.

    graph = _build_graph(db, user_id, tools)
    turn_start = _history.get(user_id, [])
    state = {"messages": turn_start + [HumanMessage(content=text)]}
    result = graph.invoke(state, {"recursion_limit": 8})
    messages = result["messages"]
    _remember(user_id, messages)

    # Only the messages this turn actually added — ToolMessages show which
    # tool(s) ran; a pending entry left for this user shows the "confirm"
    # branch paused for a yes/no instead of buying immediately.
    new_messages = messages[len(turn_start) + 1:]
    trace: list[str] = []
    for m in new_messages:
        if isinstance(m, ToolMessage):
            trace.append(f"graph node `tools` -> ran `{m.name}`")
    if user_id in _pending:
        trace.append("graph node `confirm` -> paused, awaiting your yes/no (order over Rs.2,000)")
    if not trace:
        trace.append("graph node `agent` -> answered directly, no tool needed")

    return _output_text(messages[-1].content), trace
