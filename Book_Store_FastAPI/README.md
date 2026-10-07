# Book Store — FastAPI

A faithful port of the Laravel **Book Store** project to **FastAPI**. Like the
original, it exposes **two interfaces** over the same data:

| Interface | Original (Laravel) | This project (FastAPI) |
|-----------|--------------------|------------------------|
| JWT REST API | `routes/api.php` + `App\Http\Controllers\*` | each feature's `app/<feature>/api.py`, mounted under **`/api`** |
| Session web UI (server-rendered) | `routes/web.php` + `App\Http\Controllers\AI\*` + Blade views | each feature's `app/<feature>/web.py` + Jinja2 templates, mounted at **`/`** |

Both share the same SQLAlchemy models and run against the **same MySQL schema**
(`book_store_product`) used by the Laravel app — `bcrypt` password hashes are
cross-compatible (`$2y$` ↔ `$2b$`), so accounts created in either app work in
both.

## Features (parity with the Laravel app)

- **Auth & roles** — register / login / logout, two roles: `admin`, `user`.
- **Books** — list, search (name/author), sort by price; admin-only create,
  update, delete and restock. Covers stored under `app/static/book-covers/`.
- **Cart** — add, increment, decrement (auto-remove at 0), remove. *(user)*
- **Wishlist** — add, move-to-cart, remove. *(user)*
- **Address** — CRUD, scoped to the signed-in user. *(user)*
- **Orders** — place an order (stock check + decrement, random order id) and
  view history. *(user)*
- **Feedback** — submit a 1–5 rating and view a book's average. *(user)*
- **Users directory** — admin-only list of accounts.
- **Password** — forgot (generates a reset token) + reset.
- **Reports** — admin-only Excel sales export, built in the background by a
  Celery worker with Pandas/OpenPyXL. *(admin)*

## AI features (switchable LLM: Groq / Anthropic / Ollama)

A native port of the *Book Store AI Integration Guide* — **11 numbered AI
features** plus **3 chatbot variants**, built on the same models/database.
The reusable client is `app/core/ai.py` (`ClaudeService`); the feature logic
is `app/ai/service.py`; the HTTP surface is `app/ai/web.py` (session UI,
under `/ai`) and `app/ai/api.py` (JWT REST, under `/api/ai`). Every feature
page shows not just the output but an inline **"how this worked"**
explanation grounded in the real data/trace behind it (e.g. which tool the
chatbot called, how many real reviews a summary was condensed from, the
actual order/wishlist counts fed into a recommendation).

| # | Feature | Where |
|---|---------|-------|
| 1 | **Sentiment analysis** — reviews labelled Positive/Neutral/Negative on submit, shown on the feedback page | hook in feedback store → `feedbacks.sentiment` |
| 2 | **Description generator** — admin "✨ Generate with AI" on the add-book form | `POST /ai/books/generate-description` |
| 3 | **Review summarization** — "✨ AI Review Summary" on the feedback page | `POST /ai/reviews/summary` |
| 4 | **Natural-language search** — "cheap thrillers under 500" → filters | `GET /ai/search` |
| 5a | **AI chatbot (LangChain agent)** — BookBot picks tools: catalog, orders, live weather, add-to-cart, place-order | `GET/POST /ai/chat`, `POST /api/ai/chat` |
| 5b | **AI chatbot (classic RAG)** — BookBot answers grounded only in the real catalogue + orders | `GET/POST /ai/rag-chat`, `POST /api/ai/chat-rag` |
| 5c | **AI chatbot (LangGraph)** — same tools as 5a, as an explicit graph; orders over ₹2,000 pause for a yes/no confirmation | `GET/POST /ai/graph-chat`, `POST /api/ai/chat-graph` |
| 6 | **Recommendations** — from your orders + wishlist, each with a reason | `GET /ai/recommendations` |
| 7 | **Content moderation** — abusive/spam reviews rejected before save (fail-open) | hook in feedback store |
| 8 | **Auto-tagging** — genre tags assigned when a book is created/updated, shown as 🧠 AI tags in the catalogue | hook in book store → `books.tags` |
| 9 | **Demand forecasting** — admin report over real order counts | `GET /ai/forecast` |
| 10 | **Semantic search** — search by meaning via local embeddings + cosine similarity | `GET /ai/semantic`, `books.embedding` |
| 11 | **Fine-tuning** (admin) — a local classifier trained on this store's own reviews, compared side-by-side with the zero-shot LLM | `GET /ai/finetune`, `POST /ai/finetune/{train,predict}` |

There is also a **second, separate chatbot** over Microsoft Business Central
data — see [Business Central chatbot](#business-central-chatbot-second-ai-feature-set) below.

Text features (1–9, 11) call an LLM server-side; the key never reaches the
browser, and each feature degrades gracefully when no key/model is
reachable. **The LLM backend is switchable** with `AI_PROVIDER` — it drives
*every* text feature and all three chatbots:

- **`groq`** *(default)* — **free**, OpenAI-compatible. Get a key at
  <https://console.groq.com/keys>.
- **`ollama`** — **free, local, key-less**. Install [Ollama](https://ollama.com),
  `ollama pull qwen2.5`, and leave the key blank — nothing leaves your machine.
- **`anthropic`** — Anthropic Claude (paid credits).

```
# Free default — everything runs on Groq
AI_PROVIDER=groq
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_MODEL_FAST=llama-3.1-8b-instant

# Or run fully local with Ollama (no key, no network)
# AI_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=qwen2.5

# Or switch to Anthropic Claude
# AI_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_MODEL=claude-sonnet-4-6
# ANTHROPIC_MODEL_FAST=claude-haiku-4-5-20251001
```

The shared `ClaudeService` (`app/core/ai.py`) dispatches to Anthropic's
Messages API, Groq's Chat Completions API, or a local Ollama's `/api/chat`,
depending on `AI_PROVIDER`; callers are unchanged. The two LangChain-based
chatbots (5a/5c) use the same setting via `app/ai/agent.py`'s own
provider-switch, independent of whichever provider the rest of the app uses
(Anthropic directly) via `ClaudeService.enabled`.

### Semantic search embeddings (local — no API key)

Anthropic does **not** offer an embeddings API, so Semantic Search (Feature 10,
and Fine-Tuning's Feature 11) runs a **local** embedding model
(`all-MiniLM-L6-v2`, 384-dim) instead of the Voyage AI service used originally.
Nothing external is called and no key is needed — install a dependency and it
works. Two interchangeable backends produce the identical model/vectors:

- **[`fastembed`](https://github.com/qdrant/fastembed)** *(preferred)* — ONNX
  runtime with Microsoft-signed DLLs. Use this if Windows **Smart App
  Control** is on, which blocks PyTorch's unsigned DLLs.
- **[`sentence-transformers`](https://www.sbert.net/)** — PyTorch backend,
  used as a fallback when `fastembed` isn't installed/loadable.

```
pip install -r requirements.txt   # includes both fastembed and sentence-transformers
```

On first use the model (~80 MB) is downloaded once from Hugging Face and cached
locally; every call after that is fully offline. If neither backend can be
loaded, Semantic Search (and Fine-Tuning) simply stay hidden — the other
features are unaffected. The retired Voyage AI code is preserved, commented
out, in `app/core/ai.py` for reference.

The three AI columns (`feedbacks.sentiment`, `books.tags`, `books.embedding`)
are added automatically on startup for pre-existing databases. Run **Reindex
embeddings** on the Semantic Search page (or `POST /api/ai/reindex-embeddings`)
to vectorise books created before the embedding model was available.

### AI chatbot — three separate variants (Feature 5)

There are **three independent chatbots**, all reachable from the AI hub. Pick
whichever you want to demo; they share the retrieval helpers but nothing else:

| Variant | Page / endpoint | Backend | Needs |
|---------|-----------------|---------|-------|
| **5a — LangChain agent** | `/ai/chat`, `POST /api/ai/chat` | tool-calling agent | active `AI_PROVIDER` key |
| **5b — Classic RAG** | `/ai/rag-chat`, `POST /api/ai/chat-rag` | LLM over retrieved context | active `AI_PROVIDER` key |
| **5c — LangGraph agent** | `/ai/graph-chat`, `POST /api/ai/chat-graph` | same tools as 5a, as an explicit graph | active `AI_PROVIDER` key |

All three bots use whatever `AI_PROVIDER` is set to (Groq by default — so all
run free). The **classic RAG** bot (5b) is the original implementation: it
retrieves up to 15 relevant books plus your recent orders, pastes them into
the prompt, and asks the LLM to answer *only* from that context — no tools,
no live weather. It lives in `service.rag_chat_reply`.

The **LangChain agent** (5a) is described below. The **LangGraph agent** (5c,
`app/ai/graph_agent.py`) reuses 5a's exact tools but wires them as an explicit
graph instead of a fixed loop, so it can *branch*: a `place_order` over
₹2,000 routes to a `confirm` node that asks for an explicit yes/no instead of
buying immediately, and it keeps a short per-user conversation history across
turns (something a one-shot agent call can't do). Every bot reply also shows
a "🔧 how it answered" trace — which tool ran, or which graph branch was taken.

#### LangChain agent (Feature 5a)

Instead of a hardcoded `if` that guessed intent, the LLM decides which **tool**
to call for each message:

| Tool | Kind | What it does | Backing code |
|------|------|--------------|--------------|
| `weather` | fetch (live) | Current weather for a city — **free, no API key** | `app/core/weather.py` (Open-Meteo) |
| `search_catalog` | fetch (DB) | Keyword search over the real book catalogue | `app/ai/agent.py` → SQLAlchemy |
| `my_orders` | fetch (DB) | The signed-in customer's own order history | `app/ai/agent.py` → `_order_context` |
| `add_to_cart` | **action** | Adds a book to the customer's cart by title | `app/ai/agent.py` → `Cart` (mirrors `cart/web.py`) |
| `place_order` | **action** | Places an order, deducts stock, resolves the address | `app/ai/agent.py` → `Order` (mirrors `orders/web.py`) |

The two **action** tools *write* to the database — so the agent can now buy books
by chat (e.g. *"order 2 copies of Sapiens to my home address"*). Every tool is
scoped to the signed-in `user_id`, and the action tools reuse the exact
stock/ownership guards from the web forms. This is the capability classic RAG
(5b) structurally cannot have — it can only produce text, never commit a row.

The agent lives in **`app/ai/agent.py`**; `chat_reply` (`app/ai/service.py`)
delegates to it, and the web/API routes are unchanged.

**Switchable LLM backend.** A tool-calling agent needs an LLM that supports
tool-calling, chosen with `AI_PROVIDER`:

- **`groq`** *(default)* — **free** tool-calling backend (llama-3.3-70b). Get a
  key at <https://console.groq.com/keys>. Best for testing at no cost.
- **`anthropic`** — reuse your existing `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL`.

```
# ---- Chatbot agent (LangChain, Feature 5) ----
AI_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

**Weather works with no LLM key at all.** The `weather` tool calls
[Open-Meteo](https://open-meteo.com) (free, key-less), and `chat_reply` falls
back to it directly when no chatbot key is set — so you can test the integration
before signing up for anything. It ranks geocoding matches by population and
maps common renamed Indian cities (Bangalore→Bengaluru, Bombay→Mumbai, …).

**Step-by-step to enable the full agent:**

1. `pip install -r requirements.txt` (now includes `langchain`, `langchain-groq`,
   `langchain-anthropic`).
2. Create a free key at <https://console.groq.com/keys>.
3. In `.env` set `AI_PROVIDER=groq` and `GROQ_API_KEY=gsk_...`.
4. Restart the server and open `/ai/chat`. Try:
   - *"recommend a cheap thriller"* → `search_catalog`
   - *"what did I order?"* → `my_orders`
   - *"is it raining in Delhi?"* → `weather`
   - *"add Sapiens to my cart"* → `add_to_cart` (**writes** a cart row)
   - *"order 2 copies of Sapiens to my home address"* → `place_order` (**writes** an order, deducts stock)
   - *"find me a mystery and tell me the weather in Tokyo"* → **two tools in one turn**

A full walkthrough with the actual code is in
**`Book_Store_FastAPI_Chatbot_LangChain.docx`** (regenerate with
`python build_chatbot_doc.py`).

### Business Central chatbot (second AI feature set)

A **separate, second chatbot** — entirely independent of BookBot above — that
answers questions over **Microsoft Dynamics 365 Business Central** data
(items, customers, sales orders) instead of the book catalogue. It lives in
`app/bc/` (own `client.py`, `vectorstore.py`, `service.py`, `schemas.py`,
`api.py`, `web.py`) and is reachable at `/bc/chat` (web) and `/api/bc/*` (JWT).

How it works: BC records are fetched (real Azure AD client-credentials OData/
REST call in `app/bc/client.py`, or — with no BC credentials set — a bundled
`app/bc/sample_data.py` fallback so the whole pipeline works key-lessly),
embedded with the same local model as Semantic Search, and stored in
**[Qdrant](https://qdrant.tech)**, a real vector database. Queries retrieve
the closest-matching records from Qdrant and the active `AI_PROVIDER` LLM
answers grounded in them — RAG, same pattern as chatbot 5b, but over a
different data source and a real vector DB instead of a plain SQL column.

```
# Zero-setup: leave BC_* blank to test against bundled sample data
QDRANT_PATH=./qdrant_storage   # embedded mode — no Qdrant server needed

# Real Business Central data (Azure AD app registration required):
# BC_TENANT_ID=...
# BC_CLIENT_ID=...
# BC_CLIENT_SECRET=...
# BC_ENVIRONMENT=Production
# BC_COMPANY=...
# BC_ENTITIES=items,customers,salesOrders
```

Ingestion is a manual **"Sync now"** action (admin); retrieval runs
automatically on every chat query. See `.env.example` for every `BC_*`/
`QDRANT_*` variable.

## Infrastructure features (Alembic, Redis, Celery, Reports, Docker, Pytest)

Beyond the CRUD features above, this repo is also a worked example of the
rest of a production Python stack, each one bolted onto the same codebase.
**`LEARNING_GUIDE.md` sections 11–18** explain each in depth (why, exactly
where in the code, and the commands to run it); this is just the map:

| Feature | Where | Try it |
|---|---|---|
| **Alembic** (schema migrations) | `alembic/` — 2 real migrations (`books.genre`, `orders.quantity`/`total_price`) | `alembic upgrade head` |
| **Redis** (catalogue cache) | `app/core/redis_client.py`, `app/books/cache.py` | `docker run -p 6379:6379 redis:7-alpine`, then hit `/api/displayAllBooks` twice |
| **Celery** (background jobs) | `app/core/celery_app.py`, `app/reports/tasks.py` | `celery -A app.core.celery_app worker --loglevel=info --pool=solo` |
| **Pandas + OpenPyXL** (Excel report) | `app/reports/tasks.py` | admin → `/reports` → **Generate report** |
| **Pytest** (test suite) | `tests/` | `pytest` — no MySQL/Redis/Celery needed, see `tests/conftest.py` |
| **Docker** (whole stack, one command) | `Dockerfile`, `docker-compose.yml` | `docker compose up --build` |
| **AWS** (deploying for real) | `AWS_DEPLOYMENT_GUIDE.md` | documentation only — no account required to read it |

## Requirements

- Python 3.11+
- A running MySQL (XAMPP's MySQL is fine). Create the database if it does not
  exist: `CREATE DATABASE book_store_product;` — tables are created
  automatically on startup (`CREATE_TABLES=true`), or via `alembic upgrade head`
  once you've adopted migrations (see `LEARNING_GUIDE.md` Section 11).
- Optional: **Redis** (catalogue cache + Celery broker/backend) and a
  **Celery worker** (background report generation) — the app runs fine
  without either; those two features simply stay idle/inactive.

## Setup

```powershell
cd C:\xampp\htdocs\Book_Store_FastAPI

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

copy .env.example .env   # then edit DB credentials if needed
```

> For the AI chatbot, also set a free `GROQ_API_KEY` in `.env`
> (see [AI chatbot — LangChain agent](#ai-chatbot--langchain-agent--live-weather-feature-5)).
> Weather questions work even without it.

## Run

```powershell
python run.py
# or: uvicorn app.main:app --reload
```

- Web UI:        http://127.0.0.1:8000/
- Swagger (API): http://127.0.0.1:8000/docs
- ReDoc:         http://127.0.0.1:8000/redoc

## Using the JWT API

```bash
# Register
curl -X POST http://127.0.0.1:8000/api/register -H "Content-Type: application/json" \
  -d '{"role":"admin","first_name":"Ada","last_name":"Lovelace","phone_no":"9999999999","email":"ada@example.com","password":"secret1","confirm_password":"secret1"}'

# Login -> returns {"access_token": "..."}
curl -X POST http://127.0.0.1:8000/api/login -H "Content-Type: application/json" \
  -d '{"email":"ada@example.com","password":"secret1"}'

# Authenticated call
curl http://127.0.0.1:8000/api/displayAllBooks -H "Authorization: Bearer <token>"
```

All API endpoint names match the Laravel routes (`addingBook`,
`addBookToCartByBookId`, `placeOrder`, `getAverageRatingByBookId`, …).

## API endpoint map (→ Laravel)

| Method & path | Role | Laravel controller |
|---------------|------|--------------------|
| `POST /api/register` `/login` `/logout` | – | UserController |
| `POST /api/forgotPassword` `/resetPassword` | – / token | ForgotPasswordController |
| `POST /api/addingBook` `/updateBookById` `/deleteBookById` `/addQuantityToExistBook` | admin | BookController |
| `GET /api/displayAllBooks` `/sortPriceLowToHigh` `/sortPriceHighToLow` · `POST /api/searchBookByKeyword` | any | BookController |
| `POST /api/addBookToCartByBookId` `/deleteBookByCartId` `/increamentBookQuantityInCart` `/decrementBookQuantityInCart` `/addBookToCartByWishlistId` · `GET /api/getAllBooksInCart` | user | CartController |
| `POST /api/addBookToWishlistByBookId` `/deleteBookByWishlistId` · `GET /api/getAllBooksInWishlist` | user | WishlistController |
| `POST /api/addAddress` `/updateAddress` `/deleteAddress` `/getAddress` | user | AddressController |
| `POST /api/placeOrder` | user | OrderController |
| `POST /api/feedback` `/getAverageRatingByBookId` | user | FeedbackController |

## Project layout

The project is organised **feature-first** (the "fastapi-best-practices" style):
each domain is a self-contained package, and cross-cutting concerns live in
`app/core`.

```
Book_Store_FastAPI/
├── run.py                   # dev entrypoint: python run.py (uvicorn --reload)
├── requirements.txt
├── .env.example             # copy to .env
├── alembic.ini
├── alembic/                 # schema migrations (LEARNING_GUIDE.md §11)
│   ├── env.py
│   └── versions/            # 0001_initial_schema.py, 0002_add_genre_and_order_totals.py
├── tests/                   # pytest suite (§16) — no MySQL/Redis/Celery required
│   └── conftest.py          #   in-memory SQLite + TestClient fixtures
├── Dockerfile, docker-compose.yml, .dockerignore   # §17
├── AWS_DEPLOYMENT_GUIDE.md                          # §18
├── README.md, LEARNING_GUIDE.md, BUILD_*.md         # docs (this file is the map)
└── app/
    ├── main.py               # app wiring, middleware, exception handlers, router includes
    ├── core/                 # cross-cutting infrastructure — no feature-specific logic
    │   ├── config.py         #   env-driven settings (.env) — Settings/pydantic-settings
    │   ├── database.py       #   SQLAlchemy engine/session, Base, TimestampMixin
    │   ├── security.py       #   bcrypt + JWT
    │   ├── templating.py     #   Jinja2 env, flash messages, render()
    │   ├── redis_client.py   #   shared Redis client (§12)
    │   ├── celery_app.py     #   shared Celery app (§13)
    │   ├── ai.py              #   ClaudeService — LLM calls + local embeddings, shared by app/ai
    │   └── weather.py         #   Open-Meteo client (free, key-less) — used by the chatbot's weather tool
    │
    │   # --- feature packages — each is self-contained: own models/schemas/routers ---
    ├── auth/                 # register/login/roles — the template every other feature follows
    │   ├── models.py         #   SQLAlchemy model(s) for the feature
    │   ├── schemas.py        #   Pydantic request models (API)
    │   ├── dependencies.py   #   auth/role guards (API JWT + web session)
    │   ├── api.py            #   JWT REST API router  (routes/api.php parity)
    │   └── web.py            #   session web UI router (routes/web.php parity)
    ├── books/  cart/  wishlist/  address/  orders/  feedback/   # api.py + web.py + models.py + schemas.py
    │   └── books/cache.py    #   Redis cache-aside helpers (§12)
    ├── ai/                   # AI features (11 numbered + 3 chatbot variants) — see README "AI features"
    │   ├── service.py        #   feature logic shared by web.py/api.py (sentiment, search, recs, forecast, …)
    │   ├── agent.py           #   LangChain tool-calling agent (Feature 5a)
    │   ├── graph_agent.py     #   LangGraph explicit graph — order confirmation branch (Feature 5c)
    │   ├── finetune.py        #   local classifier trained on this store's reviews (Feature 11)
    │   ├── schemas.py, api.py, web.py
    ├── bc/                   # 2nd chatbot: Business Central data → Qdrant vectors → RAG
    │   ├── client.py          #   BC OData fetch (falls back to sample_data.py key-lessly)
    │   ├── vectorstore.py      #   Qdrant embedded-mode client
    │   ├── sample_data.py, service.py, schemas.py, api.py, web.py
    ├── reports/              # api.py + web.py + tasks.py — Celery/Pandas/OpenPyXL report (§13, §15)
    ├── dashboard/  users/  password/                             # web.py only (no own models)
    ├── templates/            # Jinja2 templates (Blade view parity), one subfolder per feature + ai/, bc/
    └── static/book-covers, static/reports   # uploaded covers / generated reports
```

Each feature exposes its routers as `app.<feature>.api:router` and
`app.<feature>.web:router`, which `main.py` includes under `/api` and `/`
respectively — `app/ai` and `app/bc` follow the exact same `api.py`/`web.py`
split, just with `service.py` (and, for `ai/`, `agent.py`/`graph_agent.py`/
`finetune.py`) holding the extra feature logic instead of a flat `service.py`
alone. Shared auth/role guards live in `app/auth/dependencies.py`; shared
infrastructure (nothing feature-specific) lives in `app/core`. The full
walkthrough of everything past the core CRUD app — Alembic/Redis/Celery/
Pandas/Pytest/Docker/AWS — is in `LEARNING_GUIDE.md` sections 11–18.

## Notes / intentional differences

- The Laravel API stored covers on **S3** and sent **queued e-mails** for
  orders and password resets. As the Laravel *web* views already did, this port
  keeps things self-contained: covers go to local `static/`, and reset tokens
  are shown/returned instead of e-mailed.
- JWT is stateless, so `logout` just instructs the client to drop the token.
