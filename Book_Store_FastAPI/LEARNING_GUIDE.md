# Book Store (FastAPI) — Build It From Scratch (Learning Guide)

This guide teaches you how this project is built, step by step, in the **order you
would actually write it**. By the end you will understand every file, why it
exists, and how a request flows from the browser to the database and back.

It is written for learning, so it explains the *why*, not just the *what*.

---

## 1. What are we building?

A small **online book store** with **two front doors** over the *same* data:

| Door | What it is | Who uses it | Lives in |
|------|------------|-------------|----------|
| **REST API** | Returns JSON, uses a JWT token | Mobile apps, Postman, other programs | `app/routers/api/` |
| **Web UI** | Returns HTML pages, uses a login cookie | A human in a browser | `app/routers/web/` |

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
   │  Router  (the URL)     │  app/routers/...   "when someone hits /books, run this"
   ├───────────────────────┤
   │  Schema  (the shape)   │  app/schemas.py    "the input must look like this"
   ├───────────────────────┤
   │  Deps    (the guard)   │  app/deps.py       "are you logged in? are you admin?"
   ├───────────────────────┤
   │  Model   (the table)   │  app/models.py     "this maps to a database table"
   ├───────────────────────┤
   │  Database (the engine) │  app/database.py   "open/close the DB connection"
   └───────────────────────┘
              │
              ▼
            MySQL
```

Supporting pieces that every layer leans on:
- `config.py` — settings (DB password, secret key) read from a `.env` file.
- `security.py` — password hashing + JWT token creation.
- `templating.py` — turns data into HTML pages (web door only).
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
    ├── config.py        # settings loaded from .env
    ├── database.py      # SQLAlchemy engine + "give me a DB session" helper
    ├── models.py        # ③ the database tables, described as Python classes
    ├── schemas.py       # ④ the shape of API request bodies (validation)
    ├── security.py      # password hashing + JWT tokens
    ├── deps.py          # ⑤ reusable guards: "must be logged in / must be admin"
    ├── templating.py    # Jinja2 setup + flash messages + render() helper
    │
    ├── routers/         # ⑥ the actual endpoints (the URLs)
    │   ├── api/         #     JSON API  → mounted under /api
    │   │   ├── auth.py        # register, login, logout, password reset
    │   │   ├── books.py       # add/update/delete/list/search books
    │   │   ├── cart.py        # cart operations
    │   │   ├── wishlist.py    # wishlist operations
    │   │   ├── address.py     # address CRUD
    │   │   ├── orders.py      # place order
    │   │   └── feedback.py    # ratings
    │   └── web/         #     HTML pages → mounted at /
    │       ├── auth.py        # login/register/logout pages
    │       ├── dashboard.py   # the home screen after login
    │       ├── books.py       # browse/manage books (pages + form posts)
    │       ├── cart.py, wishlist.py, address.py, orders.py,
    │       ├── feedback.py, users.py, password.py
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

The numbered files (①–⑦) are the order we will build them in Section 6.

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

---

## 6. Build it from scratch — the correct order

Here is the order to *write* the files so each one only depends on things that
already exist. This is exactly how you would build it yourself.

### ① `config.py` — settings first
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

### ② `database.py` — the connection
Create the SQLAlchemy `engine` (the pool of DB connections), a `SessionLocal`
factory (each request gets its own short-lived session), and the `Base` class
that all models inherit from.

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

### ③ `models.py` — the tables
Each class = one table. Each `mapped_column` = one column. `relationship()`
links tables (e.g. a User *has many* Books).

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

### ④ `security.py` + `schemas.py` — protect and validate

`security.py` does two jobs:
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

`schemas.py` defines the **shape of incoming API JSON** with Pydantic. If the
input doesn't match, FastAPI auto-rejects it with a 422 before your code runs.
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

### ⑤ `deps.py` — the guards
"Dependencies" are reusable checks you attach to endpoints. This file answers
*"who are you and are you allowed here?"* — once, in one place.

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

### ⑥ `routers/` — the endpoints (the heart)
Now you write the actual URLs. Each file is an `APIRouter` grouping related
routes. **This is where the layers come together.** Read this API example slowly:

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

### ⑦ `templating.py` + `templates/` — the HTML (web door only)
`templating.py` configures Jinja2 and gives you a `render()` helper that always
injects the current user + any flash messages, so templates stay simple.

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
for r in (api_auth, api_books, api_cart, ...):
    app.include_router(r.router, prefix="/api")   # API door
for r in (web_auth, web_dashboard, web_books, ...):
    app.include_router(r.router)                  # web door
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
2. **Read in build order:** `config → database → models → schemas → security →
   deps → one router → its template → main`. Don't start in `main.py`.
3. **Pick ONE feature and trace it end-to-end.** Books is the best — it has both
   API (`routers/api/books.py`) and web (`routers/web/books.py`) versions plus a
   template. Compare the two: same data, two doors.
4. **Then change something small:** add a `genre` column.
   - Add the field in `models.py`.
   - Add it to `BookCreate` in `schemas.py`.
   - Read it in the router and pass it to the `Book(...)`.
   - Show it in `templates/books/index.html`.
   - Drop the table (or the DB) so `create_all` rebuilds it, and rerun.
   Doing this once teaches you more than reading ten times.

---

## 9. Common gotchas for beginners

- **"Table doesn't have my new column."** `create_all` only *creates missing
  tables*; it does **not** alter existing ones. While learning, drop the table
  and restart so it's recreated. (Real apps use migrations — e.g. Alembic.)
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
In `config.py`, change `database_url` to:
```python
@property
def database_url(self) -> str:
    return "sqlite:///./book_store.db"
```
and in `database.py` add the SQLite-only arg:
```python
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
```
Now `python run.py` creates a `book_store.db` file — no server needed. (The repo
ships configured for MySQL to match the original Laravel app; SQLite is purely a
convenience for learning.)

---

### One-paragraph summary
You configure settings (`config`), open a database (`database`), describe tables
as classes (`models`), validate inputs (`schemas`), hash passwords and mint
tokens (`security`), guard endpoints (`deps`), write the URLs (`routers`), render
HTML for humans (`templates`/`templating`), and bolt it all together (`main`).
A request falls **down** through router → schema → guard → model → DB, and the
response climbs back **up**. Master one feature's path and you've mastered them all.
```
