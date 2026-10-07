# Book Store (FastAPI) — Build It From Scratch (Learning Guide)

This guide teaches you how this project is built, step by step, in the **order you
would actually write it**. By the end you will understand every file, why it
exists, and how a request flows from the browser to the database and back.

It is written for learning, so it explains the *why*, not just the *what*.

**Sections 1–10** build the core app (this is the original guide). **Sections
11–18** then add the rest of a production-style Python stack on top of it —
each one bolted onto this same codebase, in the order you'd naturally reach
for them once the basics work. **Sections 19–20** add the AI layer: a
switchable LLM client, RAG, tool-calling agents (LangChain/LangGraph), local
embeddings, fine-tuning, and a second RAG chatbot over a real vector database
(Qdrant):

```
Python → FastAPI → Pydantic → SQLAlchemy → Alembic → MySQL → JWT/OAuth2
       → Dependency Injection → Redis → Celery → HTTPX → Pandas/OpenPyXL
       → Pytest → Docker → AWS → LLM APIs → Embeddings → RAG
       → LangChain / LangGraph agents → Fine-tuning → Qdrant
```

| Layer | What it does here | Where | Section |
|---|---|---|---|
| **Python** | The language everything below is written in. | everywhere | — |
| **FastAPI** | Routes URLs to functions, validates request/response shapes. | every `api.py`/`web.py` | 6 |
| **Pydantic** | Validates JSON bodies + typed settings from `.env`. | every `schemas.py`, `core/config.py` | 4, 5 |
| **SQLAlchemy** | The ORM — Python classes ↔ database tables. | every `models.py`, `core/database.py` | 2, 3 |
| **Alembic** | Versioned, incremental schema changes (no more dropping tables). | `alembic/` | **11** |
| **MySQL** | Where the rows actually live. | `core/config.database_url` | 4 |
| **JWT / OAuth2** | Proves "who is this?" on the stateless API door. | `core/security.py`, `auth/` | 4, 5 |
| **Dependency Injection** | `Depends(...)` wires DB sessions + auth guards into routes. | `auth/dependencies.py` | 5 |
| **Redis** | Caches the book catalogue so repeat reads skip the DB. | `core/redis_client.py`, `books/cache.py` | **12** |
| **Celery** | Runs slow work (building a report) off the request thread. | `core/celery_app.py`, `reports/tasks.py` | **13** |
| **HTTPX** | Calls external HTTP APIs (Claude/Groq/Ollama, Business Central) server-side. | `core/ai.py`, `bc/client.py` | **14** |
| **Pandas / OpenPyXL** | Turns SQL rows into a downloadable Excel sales report. | `reports/tasks.py` | **15** |
| **Pytest** | Automated tests — no manual clicking through `/docs` to check a fix. | `tests/` | **16** |
| **Docker** | One command runs the whole stack (app + worker + MySQL + Redis). | `Dockerfile`, `docker-compose.yml` | **17** |
| **AWS** | Where it actually runs for real users. | see `AWS_DEPLOYMENT_GUIDE.md` | **18** |
| **LLM APIs / RAG / Agents** | A switchable LLM (Groq/Anthropic/Ollama) powers 11 AI features + 2 BookBot chatbot variants (RAG, LangChain agent) that reason over real rows instead of training data. | `core/ai.py`, `ai/service.py`, `ai/agent.py` | **19** |
| **LangGraph / Fine-tuning / Embeddings** | A 3rd chatbot variant as an explicit branching graph; a local classifier trained on this store's reviews; local embeddings for semantic search. | `ai/graph_agent.py`, `ai/finetune.py`, `core/ai.py` | **19** |
| **Qdrant (vector DB)** | A 2nd, separate chatbot does RAG over Business Central data stored in a real vector database instead of a SQL column. | `bc/` | **20** |

---

## 1. What are we building?

A small **online book store** with **two front doors** over the *same* data:

| Door | What it is | Who uses it | Lives in |
|------|------------|-------------|----------|
| **REST API** | Returns JSON, uses a JWT token | Mobile apps, Postman, other programs | each feature's `app/<feature>/api.py` |
| **Web UI** | Returns HTML pages, uses a login cookie | A human in a browser | each feature's `app/<feature>/web.py` |

Both doors talk to the **same database tables** (users, books, carts, etc.)
through the **same models**. That is the central idea: write the data layer
once, expose it two ways.

**Features:** register/login, browse & search books, admin manages the catalogue,
users add to cart/wishlist, save addresses, place orders, and leave 1–5 star feedback.

---

## 2. The mental model (read this before any code)

Think of the app as **layers**. A request falls down through them and a response
climbs back up:

```
        Browser / Postman
              │
              ▼
   ┌───────────────────────┐
   │  Router  (the URL)     │  app/<feature>/api.py · web.py  "hit /books → run this"
   ├───────────────────────┤
   │  Schema  (the shape)   │  app/<feature>/schemas.py       "the input must look like this"
   ├───────────────────────┤
   │  Deps    (the guard)   │  app/auth/dependencies.py       "logged in? are you admin?"
   ├───────────────────────┤
   │  Model   (the table)   │  app/<feature>/models.py        "this maps to a database table"
   ├───────────────────────┤
   │  Database (the engine) │  app/core/database.py           "open/close the DB connection"
   └───────────────────────┘
              │
              ▼
            MySQL
```

The code is organised **feature-first**: each domain (auth, books, cart, …) is a
self-contained package holding its own `models.py`, `schemas.py`, `api.py` and
`web.py`. Cross-cutting infrastructure lives under `app/core/`:
- `core/config.py` — settings (DB password, secret key) read from a `.env` file.
- `core/database.py` — the engine/session + the `Base`/`TimestampMixin` models share.
- `core/security.py` — password hashing + JWT token creation.
- `core/templating.py` — turns data into HTML pages (web door only).
- `auth/dependencies.py` — the auth/role guards every feature reuses.
- `main.py` — the wiring that bolts all of the above together.

**Golden rule of learning this codebase:** when confused, follow one request
from the URL (router) downward. Everything else is support.

---

## 3. Folder structure explained

```
Book_Store_FastAPI/
│
├── run.py               # ① START HERE — the "go" button: python run.py
├── requirements.txt     # the list of libraries to install
├── .env                 # YOUR secret settings (DB password, etc.) — never commit
├── .env.example         # a template of .env to copy from
├── README.md            # quick reference
│
└── app/                 # ALL the application code lives here
    ├── main.py          # ② the wiring — builds the app, attaches everything
    │
    ├── core/            # cross-cutting infrastructure (shared by every feature)
    │   ├── config.py       # settings loaded from .env
    │   ├── database.py     # SQLAlchemy engine + session helper + Base/TimestampMixin
    │   ├── security.py     # ④ password hashing + JWT tokens
    │   └── templating.py   # ⑦ Jinja2 setup + flash messages + render() helper
    │
    ├── auth/            # ⑥ a FEATURE package — one self-contained domain
    │   ├── models.py       # ③ the User table, as a Python class
    │   ├── schemas.py      # ④ the shape of this feature's API request bodies
    │   ├── dependencies.py # ⑤ reusable guards: "must be logged in / must be admin"
    │   ├── api.py          #     JSON API  → mounted under /api
    │   └── web.py          #     HTML pages → mounted at /
    │
    ├── books/           # each feature follows the same shape: models / schemas / api / web
    ├── cart/            #   "
    ├── wishlist/        #   "
    ├── address/         #   "
    ├── orders/          #   "
    ├── feedback/        #   "
    ├── dashboard/       # web.py only (a screen with no table of its own)
    ├── users/           # web.py only (admin directory; reuses auth's User model)
    ├── password/        # web.py only (forgot/reset; reuses auth's User model)
    │
    ├── templates/       # ⑦ the HTML files (Jinja2), only the web door uses these
    │   ├── base.html         # the shared layout (header, nav, CSS) — others extend it
    │   ├── auth/login.html, auth/register.html
    │   ├── books/index.html, books/edit.html
    │   ├── dashboard.html, cart/index.html, ... etc.
    │
    └── static/          # files served as-is (uploaded book cover images)
        └── book-covers/
```

The numbered items (①–⑦) are the order we will build them in Section 6. Notice
the numbers no longer map to single files but to **roles**: infrastructure lives
in `core/`, and every feature package repeats the same `models → schemas →
dependencies → api/web` shape.

---

## 4. Setup from scratch (do this first)

### Prerequisites
- **Python 3.11+** — check with `python --version`.
- **MySQL running** — XAMPP's MySQL panel is fine. (You *could* swap to SQLite,
  see the note at the end.)

### Step-by-step (PowerShell on Windows)

```powershell
# 1. Go to the project folder
cd C:\Users\manju\OneDrive\Desktop\python\Book_Store_FastAPI

# 2. Create an isolated "virtual environment" so libraries don't pollute your system
python -m venv .venv

# 3. Activate it (you'll see (.venv) appear in your prompt)
.\.venv\Scripts\Activate.ps1

# 4. Install all the libraries listed in requirements.txt
pip install -r requirements.txt

# 5. Create your settings file from the template, then edit DB credentials
copy .env.example .env
notepad .env
```

### Create the database (one time)
Open phpMyAdmin (or the MySQL shell) and run:
```sql
CREATE DATABASE book_store_product;
```
You do **not** create the tables by hand — the app does that automatically on
startup (because `CREATE_TABLES=true`). See `main.py`'s `on_startup`.

### Run it
```powershell
python run.py
```
Then open:
- Web UI → http://127.0.0.1:8000/
- API docs (Swagger, try endpoints live) → http://127.0.0.1:8000/docs

**What just happened:** `run.py` told `uvicorn` (the web server) to load
`app.main:app`. On startup the app created all the tables. Now it is listening
for requests.

---

## 5. Understand the key libraries (1-line each)

| Library | Job |
|---------|-----|
| **FastAPI** | The web framework — routes URLs to Python functions, validates input. |
| **uvicorn** | The actual server that runs FastAPI and listens on a port. |
| **SQLAlchemy** | The ORM — lets you use Python objects instead of writing raw SQL. |
| **PyMySQL** | The driver SQLAlchemy uses to talk to MySQL. |
| **Pydantic** | Validates request data and reads settings (the schemas + config). |
| **passlib + bcrypt** | Hashes passwords safely (never store plain passwords). |
| **PyJWT** | Creates/reads the JWT token used by the API door. |
| **Jinja2** | Templating engine — fills `{{ values }}` into HTML for the web door. |
| **itsdangerous** | Signs the session cookie so users can't tamper with it. |
| **Alembic** | Generates/runs versioned schema migrations. → Section 11 |
| **redis** | Python client for the Redis cache. → Section 12 |
| **celery** | Runs background jobs on a separate worker process. → Section 13 |
| **httpx** | Makes outbound HTTP calls to external APIs (already listed above). → Section 14 |
| **pandas** | Shapes SQL rows into a table for export. → Section 15 |
| **openpyxl** | The engine Pandas uses to write real `.xlsx` files. → Section 15 |
| **pytest** | Runs the automated test suite. → Section 16 |

---

## 6. Build it from scratch — the correct order

Here is the order to *write* the files so each one only depends on things that
already exist. This is exactly how you would build it yourself.

### ① `core/config.py` — settings first
Everything needs settings (the DB URL, the secret key). Read them from `.env`
using Pydantic so they're typed and validated.

```python
class Settings(BaseSettings):
    app_name: str = "Book Store"
    secret_key: str = "insecure-dev-secret-change-me"
    db_host: str = "127.0.0.1"
    db_database: str = "book_store_product"
    db_username: str = "root"
    db_password: str = ""
    # ...
    @property
    def database_url(self) -> str:        # builds the full connection string
        return f"mysql+pymysql://{self.db_username}:{self.db_password}@..."

settings = get_settings()   # one shared instance everyone imports
```
**Why a property for `database_url`?** So the rest of the app never has to know
how to assemble the connection string — it just asks `settings.database_url`.

### ② `core/database.py` — the connection
Create the SQLAlchemy `engine` (the pool of DB connections), a `SessionLocal`
factory (each request gets its own short-lived session), and the `Base` class
that all models inherit from. This is also where the shared `TimestampMixin`
lives, so every feature's models can import both from one place.

```python
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):   # models inherit from this
    pass

def get_db():                  # FastAPI dependency: open a session, always close it
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
**Key idea — `get_db`:** Any endpoint that needs the database writes
`db: Session = Depends(get_db)`. FastAPI runs `get_db`, hands you a session, and
guarantees it gets closed afterward (the `finally`). You never leak connections.

### ③ `<feature>/models.py` — the tables
Each class = one table, and it lives in **its own feature package** (the `User`
table in `auth/models.py`, `Book` in `books/models.py`, and so on). Each
`mapped_column` = one column. `relationship()` links tables across features
(e.g. a User *has many* Books) using string class names so the packages don't
import each other at module load.

```python
class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(255), default="user")
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255))      # stores the HASH
    books: Mapped[list["Book"]] = relationship(back_populates="user")
```
**Tables here:** `User`, `Book`, `Cart`, `WishList`, `Address`, `Order`,
`Feedback`. The `TimestampMixin` adds `created_at` / `updated_at` to all of them
for free.

**Why this matters:** once a table is a Python class, you write
`db.get(User, 5)` instead of `SELECT * FROM users WHERE id=5`. The ORM converts.

### ④ `core/security.py` + `<feature>/schemas.py` — protect and validate

`core/security.py` does two jobs:
- **Hash passwords** so a database leak doesn't expose them.
  ```python
  hash_password("secret1")          # -> "$2b$12$....." stored in DB
  verify_password("secret1", hash)  # -> True / False at login
  ```
- **JWT tokens** for the API door — a signed string that proves "I am user 5"
  without a server-side session.
  ```python
  create_access_token(user.id)   # login hands this to the client
  decode_access_token(token)     # every later request: who is this?
  ```

Each feature's `schemas.py` defines the **shape of incoming API JSON** with
Pydantic (e.g. `auth/schemas.py` holds `RegisterRequest`). If the input doesn't
match, FastAPI auto-rejects it with a 422 before your code runs.
```python
class RegisterRequest(BaseModel):
    email: EmailStr                       # must be a valid email
    password: str = Field(min_length=6)   # at least 6 chars
    confirm_password: str
    @field_validator("confirm_password")  # custom rule: must match password
    ...
```
**Schema vs Model — don't confuse them:**
- **Model** = a database table (SQLAlchemy).
- **Schema** = the validation shape of a request/response (Pydantic).

### ⑤ `auth/dependencies.py` — the guards
"Dependencies" are reusable checks you attach to endpoints. This file answers
*"who are you and are you allowed here?"* — once, in one place. It lives in the
`auth` package because auth is the foundation every other feature builds on;
they all import their guards from here.

API door (token-based):
```python
def get_current_api_user(credentials=Depends(bearer_scheme), db=Depends(get_db)):
    sub = decode_access_token(credentials.credentials)   # read the token
    return db.get(User, int(sub))                        # load that user

def require_api_role(role):          # factory: returns a guard for a given role
    def checker(user=Depends(get_current_api_user)):
        if user.role != role:
            raise HTTPException(403, f"Only {role}s are allowed")
        return user
    return checker
```
Web door (cookie/session-based):
```python
def require_web_user(request, db=Depends(get_db)):
    user_id = request.session.get("user_id")     # set at login
    if not user_id:
        raise RedirectException("/login", error="Please sign in.")  # bounce to login
    return db.get(User, int(user_id))
```
**The payoff:** an admin-only endpoint just adds
`admin: User = Depends(require_api_role("admin"))` — no auth code repeated inside.

### ⑥ `<feature>/api.py` + `web.py` — the endpoints (the heart)
Now you write the actual URLs. Each feature exposes its routes through an
`APIRouter` in `api.py` (the JSON door) and another in `web.py` (the HTML door).
**This is where the layers come together.** Read this API example slowly:

```python
@router.post("/addingBook", status_code=201)
def adding_book(
    payload: BookCreate,                              # ④ schema validates the body
    admin: User = Depends(require_api_role("admin")), # ⑤ guard: must be admin
    db: Session = Depends(get_db),                    # ② a DB session, auto-closed
):
    book = Book(user_id=admin.id, name=payload.name, ...)  # ③ build a model row
    db.add(book); db.commit(); db.refresh(book)            # save it
    return {"status": 201, "message": "Book created", "book": _serialize(book)}
```
Every line ties back to a layer you already built. That single function *is* the
whole architecture in miniature.

The **web** version of the same idea returns a redirect + flash message instead
of JSON, and reads form fields instead of a JSON schema:
```python
@router.post("")
def store(request: Request, name: str = Form(...), image: UploadFile = File(...),
          user: User = Depends(require_web_role("admin")), db=Depends(get_db)):
    # ...save the file, insert the Book...
    flash(request, f'Book "{name}" created successfully.')   # one-time message
    return RedirectResponse("/books", status_code=303)       # Post/Redirect/Get
```
**Why redirect after a POST (the PRG pattern)?** So a browser refresh doesn't
resubmit the form. The success message survives the redirect via a one-time
"flash" stored in the session cookie.

### ⑦ `core/templating.py` + `templates/` — the HTML (web door only)
`core/templating.py` configures Jinja2 and gives you a `render()` helper that
always injects the current user + any flash messages, so templates stay simple.

`templates/base.html` is the **skeleton** (header, nav, all the CSS). Every other
page does `{% extends "base.html" %}` and fills in just its `content` block:
```html
{% extends "base.html" %}
{% block content %}
  {% for book in books %}
     <div class="card">{{ book.name }} — ₹{{ book.price }}</div>
  {% endfor %}
{% endblock %}
```
The router passes `books` into `render(...)`, Jinja loops over them, and the user
gets a finished HTML page.

### ② (again) `main.py` — wire everything together
Built last because it imports everything else. It:
1. Creates the `FastAPI()` app.
2. Adds the **SessionMiddleware** (enables the cookie the web door needs).
3. Mounts `/static` for images.
4. On startup, creates all tables (`Base.metadata.create_all`).
5. Registers **exception handlers** (turn a `RedirectException` into a real
   redirect; turn validation errors into friendly flashes for web forms).
6. **Includes every router** — API ones under `/api`, web ones at `/`.

```python
from app.auth import api as auth_api, web as auth_web
from app.books import api as books_api, web as books_web
# ...one import per feature...

for module in (auth_api, books_api, cart_api, ...):
    app.include_router(module.router, prefix="/api")   # API door
for module in (auth_web, dashboard_web, books_web, ...):
    app.include_router(module.router)                  # web door
```

### `run.py` — the button
```python
uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
```
`reload=True` restarts the server whenever you save a file — great for learning.

---

## 7. Follow one full request (the "aha" moment)

**Scenario: a logged-in admin adds a book through the API.**

1. Client sends `POST /api/addingBook` with a JSON body and an
   `Authorization: Bearer <token>` header.
2. `main.py` routed `/api/*` to the books API router → matches `adding_book`.
3. FastAPI sees `payload: BookCreate` → **validates the JSON** (schemas, ④). Bad
   data? Auto-422, your code never runs.
4. FastAPI sees `Depends(require_api_role("admin"))` → runs the **guard** (⑤):
   decodes the token, loads the user, checks `role == "admin"`. Not admin? 403.
5. FastAPI sees `Depends(get_db)` → opens a **DB session** (②).
6. Your function builds a `Book` **model** (③), `db.add` + `db.commit` → SQLAlchemy
   emits the `INSERT` via PyMySQL → MySQL stores the row.
7. You return a dict → FastAPI serializes it to JSON → client gets `201 Created`.
8. The session from step 5 is **automatically closed** (`get_db`'s `finally`).

Every numbered layer from Section 6 appeared exactly once. That is the whole app.

---

## 8. How to study this repo effectively

1. **Run it first** (Section 4) and click around `/docs` and the web UI. Seeing it
   work makes the code concrete.
2. **Read in build order:** `core/config → core/database → a feature's models →
   schemas → auth/dependencies → its api/web → its template → main`. Don't start
   in `main.py`.
3. **Pick ONE feature and trace it end-to-end.** Books is the best — open the
   `app/books/` package and read `api.py` and `web.py` side by side, plus the
   template. Same data, two doors.
4. **Then change something small — this repo already did it, so read it as a
   worked example first:** `books.genre` was added exactly the way you'd add
   any new column:
   - The field in `app/books/models.py`.
   - `BookCreate`/`BookUpdate` in `app/books/schemas.py`.
   - Read/written in `app/books/api.py` and `app/books/web.py`, passed to `Book(...)`.
   - Shown in `templates/books/index.html` and `templates/books/edit.html`.
   - **Applied with a migration, not a dropped table** — `alembic/versions/0002_add_genre_and_order_totals.py`.
     Section 11 walks through exactly how that file was generated.
   Now do the same for a field of your own (e.g. an `isbn` on `Book`) — that's
   the exercise. Doing this once teaches you more than reading ten times.

---

## 9. Common gotchas for beginners

- **"Table doesn't have my new column."** `create_all` only *creates missing
  tables*; it does **not** alter existing ones. While learning with
  `CREATE_TABLES=true`, dropping the table and restarting is the fast path.
  For a database you actually care about (or one already holding data), use
  a **migration** instead — Section 11 does exactly this for real, adding
  `books.genre` and `orders.quantity`/`total_price` without dropping anything.
- **Can't connect to MySQL.** Is MySQL actually running? Do the credentials in
  `.env` match? Does the `book_store_product` database exist?
- **401 on API calls.** You must log in (`POST /api/login`), copy the
  `access_token`, and send it as `Authorization: Bearer <token>`. In `/docs`
  click the **Authorize** button.
- **Web pages bounce me to /login.** The web door uses the session cookie, not
  the JWT. Log in through the web form, not the API.
- **Never commit `.env`** — it holds secrets. `.env.example` is the safe template.

---

## 10. Want zero setup? Use SQLite instead of MySQL

To learn without installing MySQL, you can point the app at a local file DB.
In `app/core/config.py`, change `database_url` to:
```python
@property
def database_url(self) -> str:
    return "sqlite:///./book_store.db"
```
and in `app/core/database.py` add the SQLite-only arg:
```python
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
```
Now `python run.py` creates a `book_store.db` file — no server needed. (The repo
ships configured for MySQL to match the original Laravel app; SQLite is purely a
convenience for learning.)

---

## 11. Alembic — schema migrations

### The problem it solves
`Base.metadata.create_all()` (Section 6, step ②) only **creates missing
tables**. It never touches a table that already exists — so the day you add a
column to a model that's already live, nothing happens. This app actually hit
that exact wall already: `app/core/database.py`'s `ensure_ai_columns()` is a
hand-rolled `ALTER TABLE ... ADD COLUMN` hack, written specifically because
`create_all` couldn't add the AI columns (`tags`, `embedding`, `sentiment`) to
a database that predated them. Alembic is the general, versioned way to do
what that hack does one-off: describe a schema *change*, apply it, and be able
to undo it.

### Where it lives
```
alembic.ini            # Alembic's config — script location, logging
alembic/env.py         # wired to import every feature's models + app settings
alembic/versions/
    0001_initial_schema.py                  # the 7 tables, as create_all makes them
    0002_add_genre_and_order_totals.py      # books.genre + orders.quantity/total_price
```
`alembic/env.py` does two non-default things (read the comments in the file):
1. Imports every feature's `models.py` before comparing anything, so
   `Base.metadata` actually contains every table — autogenerate can only see
   a model that has been imported somewhere.
2. Reads the DB URL from `app.core.config.settings` (your `.env`) instead of
   a second, easy-to-forget copy in `alembic.ini`.

### The workflow (how migration 0002 was actually made)
This is the same four commands you'll run every time a model changes:
```powershell
# 1. Change the model(s) — e.g. add a field in app/books/models.py
# 2. Ask Alembic to diff "what the models say" vs "what the DB has":
alembic revision --autogenerate -m "add genre to books, quantity and total_price to orders"

# 3. OPEN the generated file in alembic/versions/ and read it — autogenerate
#    is a draft, not gospel. This repo's 0002 hand-adds a `server_default='1'`
#    to the new NOT NULL `orders.quantity` column, because without one, adding
#    a NOT NULL column to a table that already has rows fails outright.

# 4. Apply it:
alembic upgrade head
```
Other commands you'll reach for:
```powershell
alembic current          # which revision is the DB actually on?
alembic history           # the full chain, oldest -> newest
alembic downgrade -1      # undo the last migration (runs downgrade())
alembic upgrade head      # (re)apply everything up to the latest
```

### How this repo's two migrations were verified
There's no MySQL server in a fresh checkout to test against, so both
migrations were validated against a **throwaway SQLite database** instead —
proof the upgrade/downgrade logic itself is correct, independent of which
database eventually runs it:
```powershell
$env:ALEMBIC_SQLALCHEMY_URL = "sqlite:///./_alembic_test.db"
alembic upgrade head        # 0001 -> 0002, from empty
alembic downgrade -1        # back to 0001
alembic upgrade head        # forward again
alembic check                # "No new upgrade operations detected" = models == DB
Remove-Item _alembic_test.db
```
`ALEMBIC_SQLALCHEMY_URL` (read in `alembic/env.py`) is a hook made for exactly
this — pointing migrations at a disposable database without touching `.env`.
Against your real MySQL, skip that variable and Alembic just uses `.env` as
normal.

### Alembic vs. `CREATE_TABLES=true`
Both still work, but they answer different questions:
- `CREATE_TABLES=true` (`.env`) → "give me a schema with zero setup" (Section 4).
  Fine for a scratch database you'll happily drop.
- Alembic → "evolve a schema I already have data in, and be able to undo it."

Once you're using Alembic for real changes, set `CREATE_TABLES=false` so the
two mechanisms never race each other — `docker-compose.yml` (Section 17)
already does this and runs `alembic upgrade head` before every start instead.

---

## 12. Redis — caching the book catalogue

### Why here
`GET /api/displayAllBooks` (and the web `/books` page) is read constantly and
changes rarely — the textbook case for a cache. This is the **cache-aside**
pattern: check the cache first; on a miss, hit the database and *then* fill
the cache; on any write, delete the cached copy so the next read is forced
back to the database.

### Where it lives
- `app/core/redis_client.py` — one shared `redis.Redis` client, exactly like
  `engine`/`SessionLocal` in `core/database.py`.
- `app/books/cache.py` — `get_cached_books()`, `set_cached_books()`,
  `invalidate_books_cache()`. Every function wraps its Redis call in a
  `try/except`: **a Redis outage degrades the app to "slower", never "broken"**.
- Wired in:
  - `app/books/api.py::display_all_books` — reads the cache first.
  - `app/books/api.py` (`adding_book`, `update_book`, `delete_book`, `add_quantity`)
    and `app/books/web.py` (`store`, `update`, `destroy`, `add_quantity`) —
    every mutation calls `invalidate_books_cache()`.
  - `app/orders/api.py::place_order` and `app/orders/web.py::store` — placing
    an order changes a book's stock count, so it invalidates too.

### Try it
```powershell
# Run Redis locally (Docker):
docker run -p 6379:6379 redis:7-alpine
# or via this repo's compose file:
docker compose up redis
```
Then call `GET /api/displayAllBooks` twice (with a valid token) — the response
body includes `"cached": false` the first time (database) and `"cached": true`
the second (Redis), until `REDIS_CACHE_SECONDS` (default 60s, in `.env`)
expires or a write invalidates it. Stop Redis and call it again: same data,
`"cached"` always `false` now — the fallback path.

---

## 13. Celery — background jobs

### Why here
A request handler should answer fast. Building an Excel report by querying
every order and writing a spreadsheet is exactly the kind of work that
*shouldn't* happen inside that handler — it could take seconds, and the admin
would just be staring at a spinner. Celery moves that work to a **separate
process** (the worker): FastAPI *enqueues* a task and returns immediately; the
worker picks it up whenever it's free; the client **polls** for the result.

Redis plays two unrelated roles here, on two different logical DB numbers so
they never collide with each other or with the Section 12 cache:
- **Broker** (`CELERY_BROKER_DB`) — where FastAPI drops off "please run this task".
- **Result backend** (`CELERY_RESULT_DB`) — where the worker writes the answer.

### Where it lives
- `app/core/celery_app.py` — the shared `Celery` app (broker + backend URLs,
  from `app.core.config.settings`).
- `app/reports/tasks.py` — `generate_orders_report`, the actual task. Runs in
  the **worker's** process, so it can't use `Depends(get_db)` (that's a
  FastAPI-request-scoped thing) — it opens its own `SessionLocal()` directly.
- `app/reports/api.py` / `app/reports/web.py` — enqueue (`.delay()`) and poll
  (`AsyncResult(task_id, app=celery_app)`) endpoints, JWT and session flavours.
- `app/templates/reports/index.html` — a button + `fetch()` polling loop.

### Run it
```powershell
# Terminal 1 — Redis (broker + backend)
docker run -p 6379:6379 redis:7-alpine

# Terminal 2 — the Celery worker (a SEPARATE process from the web server)
celery -A app.core.celery_app worker --loglevel=info --pool=solo
# --pool=solo: Celery's default "prefork" pool needs fork(), which Windows
# doesn't have. --pool=solo runs one task at a time in-process instead.

# Terminal 3 — the app, as always
python run.py
```
Log in as an admin, open `/reports`, click **Generate report**. The page
`POST`s to `/reports/orders/export` (→ `task.delay()`, returns a `task_id`
immediately), then polls `GET /reports/orders/export/{task_id}` every 1.5s
until the worker (Terminal 2) finishes and the state flips to `SUCCESS` with a
download link.

**No worker running?** The task just sits in Redis's queue forever and the
page polls `PENDING` indefinitely — a good way to *feel* why the worker is a
separate, must-be-running process, not optional plumbing.

---

## 14. HTTPX — calling other services

Already in this codebase before this guide's later sections were added —
worth calling out explicitly since it's the "make an HTTP request *from* the
server" tool the stack diagram asks about.

- `app/core/ai.py` — talks to the Anthropic/Groq **Messages** APIs directly
  over HTTPS with `httpx`, instead of pulling in a heavier SDK.
- `app/bc/client.py` — Business Central's Azure AD OAuth2 client-credentials
  flow (fetch a token, then call the BC REST/OData API) — all `httpx`.

Every route handler in this app is a plain `def` (not `async def`), so
FastAPI runs it in Starlette's thread pool — a blocking `httpx.get(...)` call
there does **not** freeze the server for other requests. That's why these
files use the plain synchronous `httpx.Client`/`httpx.get` API rather than
`httpx.AsyncClient` — there's no event loop here to block.

---

## 15. Pandas + OpenPyXL — the sales report

Two libraries, two different jobs, chained in `app/reports/tasks.py`:
- **Pandas** — turns a list of SQLAlchemy result rows into a `DataFrame` (a
  table with named columns). `_orders_dataframe()` joins `Order` with `Book`,
  `User` and `Address` and hands the rows straight to
  `pd.DataFrame(rows)` — no manual dict-building.
- **OpenPyXL** — the *engine* that knows how to write that DataFrame out as a
  real `.xlsx` file (Excel's zipped-XML format). Pandas doesn't know that
  format itself; `df.to_excel(path, engine="openpyxl")` is Pandas handing the
  actual byte-level writing off to OpenPyXL.

The report columns: order id, when it was placed, customer name/email, book
name/author/genre, quantity, unit price, the order's stored `total_price`,
and delivery city — see Section 11 for where `orders.quantity`/`total_price`
came from (they didn't exist until migration 0002).

The file is written to `app/static/reports/<task-id>.xlsx`, which is why it's
downloadable straight from `/static/reports/...` — same static mount Section
6 already set up for book covers.

---

## 16. Pytest — the test suite

### Why it matters here specifically
Up to now, "does it work" meant clicking through `/docs` or the web UI by
hand. That doesn't scale, and it definitely doesn't run before every commit.
`tests/` exercises the real API (register → login → create a book → place an
order → export a report) without needing MySQL, Redis, or a Celery worker
actually running.

### Where it lives
```
pytest.ini            # testpaths = tests
tests/conftest.py     # the 3 swaps that make this possible (see below)
tests/test_auth.py    # register/login/duplicate-email/401-without-token
tests/test_books.py   # admin-only writes, the cached read path
tests/test_orders.py  # stock checks, address ownership, the full order flow
tests/test_reports.py # the Celery + Pandas/OpenPyXL pipeline, end-to-end
```

### The three swaps (`tests/conftest.py`)
1. **Database** — `app.core.database.engine`/`SessionLocal` are replaced with
   an in-memory SQLite database *before* `app.main` is imported. This works
   because `get_db()` looks up `SessionLocal` **by name, at call time** — see
   the comment in `core/database.py` — so every router that already does
   `from app.core.database import get_db` transparently starts talking to
   the test database too, with zero changes to application code.
2. **Celery** — `task_always_eager=True` makes `.delay()` run the task
   synchronously, in the test process, instead of needing a real worker.
   `result_backend="cache+memory://"` means `AsyncResult(task_id)` can still
   be polled afterwards, purely in memory — this is what makes
   `test_reports.py` able to test the *entire* enqueue → run → poll → download
   flow with no Redis and no worker process.
3. **Redis cache** — deliberately left alone. Because `books/cache.py`
   already treats a connection failure as a cache miss, running tests with no
   Redis server simply exercises that fallback path for free.

### Run it
```powershell
pip install -r requirements.txt   # pytest is already listed
pytest                             # from the project root
```
Every test registers its own user with a unique email — no shared fixtures to
reset between tests, no test ordering to worry about.

### Adding your own test
Follow `test_books.py`: use the `client`, `admin_headers`/`user_headers`
fixtures from `conftest.py`, call the real endpoint, assert on the response —
the same request/response contract Postman or the browser would see.

---

## 17. Docker — one command for the whole stack

### Why here
By this point the app needs **four** things running together: the API
server, a Celery worker, MySQL, and Redis. Docker Compose starts all four
with one command, wired to talk to each other, instead of you juggling four
terminals (and a XAMPP panel) every time you sit down to work.

### Where it lives
- `Dockerfile` — one image. Installs `requirements.txt`, copies the code.
  The **same image** runs both the web server and the worker (Section 13
  already showed they're just two different commands over identical code).
- `docker-compose.yml` — four services:
  | Service | Image/build | Role |
  |---|---|---|
  | `db` | `mysql:8.0` | the database (Section 4/10) |
  | `redis` | `redis:7-alpine` | cache (Section 12) + Celery broker/backend (Section 13) |
  | `app` | built from `Dockerfile` | runs `alembic upgrade head` (Section 11), then `uvicorn` |
  | `worker` | built from `Dockerfile` | `celery -A app.core.celery_app worker` |
- `.dockerignore` — keeps `.venv/`, `.git/`, `.env`, and generated files out
  of the image (never bake secrets into an image layer).

### Run it
```powershell
docker compose up --build
```
Then the same URLs as always: http://127.0.0.1:8000/ and .../docs. Notice
`app`'s command in `docker-compose.yml` runs `alembic upgrade head` **before**
`uvicorn` starts — every container start brings the schema up to date
automatically (a no-op once it already is), which is why that service also
sets `CREATE_TABLES=false` (Section 11) — Alembic is now the only thing
allowed to change the schema.

One-off commands run *inside* the already-built image via `exec`:
```powershell
docker compose exec app alembic revision --autogenerate -m "..."
docker compose exec app pytest
```
Stop everything with `docker compose down` (add `-v` to also delete the MySQL
data volume and start completely fresh).

> This guide's step-by-step assumes Docker Desktop is installed and running
> (Settings → Resources shows it using CPU/memory) — if `docker compose up`
> hangs or errors immediately, that's almost always why.

---

## 18. AWS — deploying it for real

Everything above runs great on one machine. AWS is where the same pieces
become independently-scalable managed services instead of containers on your
laptop. This repo's build stayed **documentation-only** here (no AWS account
required to work through Sections 1–17) — see **`AWS_DEPLOYMENT_GUIDE.md`**
in the project root for the full, step-by-step walkthrough.

The short version — where each local piece goes:

| Runs locally as… | Becomes, on AWS | Why |
|---|---|---|
| `db` (MySQL container) | **RDS for MySQL** | managed backups, patching, failover |
| `redis` container | **ElastiCache for Redis** | managed, same cache + Celery broker role |
| `app` container | **EC2** (simple) or **ECS/Fargate** (scales) | runs the exact same Docker image |
| `worker` container | a second EC2/ECS service, same image | Celery worker scales independently of the API |
| `app/static/book-covers`, `app/static/reports` | **S3** | container disks aren't durable/shared across instances |
| `.env` | **SSM Parameter Store** / **Secrets Manager** | secrets shouldn't live in an image or a repo |

`AWS_DEPLOYMENT_GUIDE.md` walks through provisioning each of these, wiring
the security groups between them, and pointing this same `docker-compose.yml`
image at them via environment variables — no code changes, only configuration.

---

## 19. AI features — a switchable LLM, RAG, and agents

### Why it matters here specifically
Every feature so far reads/writes rows you typed. AI features add a *new*
kind of data source — a language model — and the whole game is making it
**reason over your real rows** instead of inventing answers. This repo builds
that up in the order you'd actually reach for each piece: first a plain LLM
call, then grounding it in real data (RAG), then letting it *act* (agents),
then baking knowledge into a small model instead of re-sending it every call
(fine-tuning). The AI hub page (`/ai`, `app/templates/ai/hub.html`) has the
full concept-by-concept walkthrough with live code; this section is the
"build it from scratch" version.

### Where it lives
```
app/core/ai.py          # ClaudeService — one client, 3 switchable LLM backends + local embeddings
app/ai/service.py       # feature logic: sentiment, search, recommendations, forecast, RAG chat, ...
app/ai/agent.py         # LangChain tool-calling agent (Feature 5a)
app/ai/graph_agent.py   # LangGraph explicit graph — same tools, adds a confirm branch (Feature 5c)
app/ai/finetune.py      # local classifier trained on this store's own reviews (Feature 11)
app/ai/schemas.py, api.py, web.py   # the same request-shape / JWT-API / session-UI split every feature uses
```
Same shape as every other feature package (`schemas` → `api`/`web`) — `ai/`
just has extra logic modules (`service.py`, `agent.py`, `graph_agent.py`,
`finetune.py`) instead of one flat `service.py`, because there's more than one
kind of "feature logic" here.

### Step 1 — one LLM call, switchable backend
`ClaudeService.ask(prompt, system)` is the one function every text feature
calls. It dispatches on `settings.ai_provider`:
```python
# app/core/ai.py
def ask(self, prompt, system=None, model=None, max_tokens=1024) -> str:
    if self._provider == "groq":   return self._ask_groq(prompt, system, model, max_tokens)
    if self._provider == "ollama": return self._ask_ollama(prompt, system, model, max_tokens)
    return self._ask_anthropic(prompt, system, model, max_tokens)
```
Three backends, one call site — `groq` (free, hosted), `ollama` (free, fully
local, no key, no network), `anthropic` (paid). Every feature (sentiment,
moderation, description generator, summarization, NL search, recommendations,
forecast, auto-tagging, classic RAG chat) is built on this one function and
`ask_json` (same thing, parses the reply as JSON) — see `app/ai/service.py`
for all of them; they're all the shape `prompt in → ask()/ask_json() → one
string or dict out`, no tools, no memory. This is **generative AI**: nothing
more than a function call that happens to be answered by a language model.

### Step 2 — RAG: ground it in real rows
A plain LLM call above knows nothing about *this* store's books or *your*
orders. RAG (Retrieval-Augmented Generation) fixes that in three steps —
**retrieve** real rows, **paste them into the prompt**, **generate** with an
instruction to answer only from that context:
```python
# app/ai/service.py — rag_chat_reply() (Feature 5b, the classic RAG chatbot)
books = db.scalars(select(Book).where(Book.name.like(like) | ...)).all()
catalog = "\n".join(f"- {b.name} by {b.author} (Rs.{b.price})" for b in books)
system = f"Answer using ONLY the CATALOG below.\nCATALOG:\n{catalog}"
claude.ask(message, system)
```
The model can't invent a book that isn't in `catalog` — it never had the
chance to see anything else. This is the same idea the Business Central
chatbot uses in Section 20, just with Qdrant doing the "retrieve" step
instead of a SQL `LIKE`.

### Step 3 — agents: let the model choose the action
RAG still only produces *text*. An agent gives the model a list of **tools**
(plain Python functions) and a loop that runs whichever one the model picks:
```python
# app/ai/agent.py (Feature 5a — LangChain)
tools = [weather, search_catalog, my_orders, add_to_cart, place_order]
executor = AgentExecutor(agent=create_tool_calling_agent(llm, tools, prompt), tools=tools)
executor.invoke({"input": "add Clean Code to my cart"})
# -> the model picks add_to_cart, it actually RUNS, then the model replies
```
`add_to_cart`/`place_order` are the two tools that *write* — every tool is
scoped to the signed-in `user_id`, exactly like the ordinary `cart/web.py`
and `orders/web.py` forms, so the agent can never touch another customer's
data. `app/ai/graph_agent.py` (Feature 5c) wires the identical tools as an
explicit **LangGraph** graph instead of a fixed loop, so it can *branch*: a
`place_order` over ₹2,000 routes to a `confirm` node that pauses for an
explicit yes/no instead of buying immediately, and it keeps a short per-user
message history across turns — something a one-shot agent call can't do.

### Step 4 — embeddings, semantic search, and fine-tuning
`ClaudeService.embed(text)` turns text into a 384-number vector **locally**
(`fastembed`/ONNX, falling back to `sentence-transformers`) — no API key,
because Anthropic has no embeddings endpoint. Semantic Search (Feature 10)
compares a query's vector to every book's stored vector with cosine
similarity; Fine-Tuning (Feature 11) goes one step further and trains a tiny
`LogisticRegression` classifier on those same vectors, labelled by this
store's real star ratings, so sentiment prediction stops needing an LLM call
at all once trained:
```python
# app/ai/finetune.py
vectors = claude.embed_many(review_texts)
clf = LogisticRegression().fit(vectors, ratings_as_labels)
clf.predict([claude.embed(new_review_text)])   # no LLM call, no network
```

### Every feature explains itself
Each AI page doesn't just show the output — it shows **how** that output was
produced, grounded in the real call/data behind it: which tool the chatbot
picked (`🔧 how it answered`), how many real reviews a summary came from, the
actual retrieved-row count a RAG answer used, the real order/wishlist counts
fed into a recommendation. Look at `app/ai/service.py`'s return types
(`(reply, trace)`, `(summary, count)`, `(recs, basis)`) and the matching
"How this worked" card in each `app/templates/ai/*.html` page.

### Run it
```powershell
pip install -r requirements.txt     # langchain, langchain-groq/-anthropic/-ollama, langgraph, fastembed, scikit-learn
copy .env.example .env
```
Set one provider in `.env` (`AI_PROVIDER=groq` + a free key from
<https://console.groq.com/keys> is the fastest path to everything working;
`AI_PROVIDER=ollama` needs no key at all once `ollama pull qwen2.5` is done).
Then `python run.py` and open **`/ai`** — every feature is one click away.
Embeddings (Semantic Search, Fine-Tuning) need no extra setup beyond
`requirements.txt` — `fastembed`/`sentence-transformers` are already listed —
and simply stay hidden if neither package can be loaded, the same
degrade-gracefully pattern Section 9 describes for a missing table.

---

## 20. Business Central chatbot — RAG over a real vector database (Qdrant)

### Why it matters here specifically
Section 19's RAG chatbot retrieves with a SQL `LIKE` over a few dozen rows —
fine at catalogue scale, but it doesn't demonstrate an actual **vector
database**. This second, independent chatbot answers questions over
Microsoft Dynamics 365 Business Central data (items, customers, sales
orders) and retrieves with **Qdrant** instead, the same RAG shape at a scale
where a real vector index matters.

### Where it lives
```
app/bc/client.py        # fetches BC records (Azure AD OAuth2) or falls back to sample_data.py
app/bc/sample_data.py   # bundled fake records — the pipeline works with zero BC credentials
app/bc/vectorstore.py   # Qdrant client — embedded mode (a local folder) by default
app/bc/service.py       # ingest (embed + upsert) and retrieve (search + ask) logic
app/bc/schemas.py, api.py, web.py
```

### The pipeline
1. **Sync** (admin, manual button) — fetch BC records (real API, or
   `sample_data.py` if `BC_TENANT_ID` etc. are blank), flatten each record's
   fields to text, embed with the *same* local model Section 19's Semantic
   Search uses, and upsert into Qdrant with a deterministic id
   (`uuid5("entity:key")`) so re-syncing updates in place instead of
   duplicating.
2. **Chat** (every request) — embed the question, `qdrant.search(...)` for
   the closest-matching records, paste them into the prompt, and ask the
   active `AI_PROVIDER` LLM to answer only from that context — identical
   shape to `rag_chat_reply` in Section 19, different retrieval backend.

### Qdrant, embedded (no server to run)
```
QDRANT_PATH=./qdrant_storage   # a local folder — no Docker, no server process
# QDRANT_URL=http://localhost:6333   # set this instead (and blank QDRANT_PATH) to use a real server
```
Embedded mode holds an exclusive lock on that folder — only one app process
can have it open at a time.

### Run it
```powershell
python run.py
```
Open **`/bc/chat`**, click **"Sync now"** (admin) to ingest the bundled
sample data, then ask something like *"what items do we have low stock on?"*
— no Business Central subscription or Qdrant server required to see the
whole pipeline work end to end.

---

### One-paragraph summary
You configure settings (`core/config`), open a database (`core/database`),
describe tables as classes (each feature's `models`), validate inputs (each
feature's `schemas`), hash passwords and mint tokens (`core/security`), guard
endpoints (`auth/dependencies`), write the URLs (each feature's `api`/`web`),
render HTML for humans (`templates` + `core/templating`), and bolt it all
together (`main`). A request falls **down** through router → schema → guard →
model → DB, and the response climbs back **up**. Master one feature's path and
you've mastered them all. Everything after Section 10 is the same idea applied
outward: **Alembic** versions the DB itself, **Redis** and **Celery** make the
app fast and non-blocking, **Pandas/OpenPyXL** turn rows into a real
spreadsheet, **Pytest** proves it all still works, **Docker**/**AWS** are just
increasingly realistic places to run the exact same code, and **Sections
19–20** apply the identical request → logic → data shape to a language model
instead of a database — grounding it in real rows (RAG), letting it act
(agents), and giving it a second, real vector database (Qdrant) to retrieve
from.
