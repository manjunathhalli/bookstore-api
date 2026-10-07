"""Generate a Google-Docs-ready .docx of the learning guide.

Upload the resulting .docx to Google Drive, then right-click -> Open with
Google Docs to get a fully editable Google Doc.
"""

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

DARK = RGBColor(0x1E, 0x29, 0x3B)
INDIGO = RGBColor(0x4F, 0x46, 0xE5)
GREY = RGBColor(0x55, 0x5F, 0x70)
CODE_BG = "F2F3F7"


def shade(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def code_block(doc, lines):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    shade(cell, CODE_BG)
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run("\n".join(lines))
    run.font.name = "Consolas"
    run.font.size = Pt(9)
    # ensure monospace applies to complex/east-asian too
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), "Consolas")
    rfonts.set(qn("w:hAnsi"), "Consolas")
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def body(doc, text, *, italic=False, bold=False):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.italic = italic
    run.bold = bold
    run.font.size = Pt(11)
    p.paragraph_format.space_after = Pt(8)
    return p


def bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    p.add_run(text).font.size = Pt(11)
    p.paragraph_format.space_after = Pt(4)


def numbered(doc, text):
    p = doc.add_paragraph(style="List Number")
    p.add_run(text).font.size = Pt(11)
    p.paragraph_format.space_after = Pt(4)


def make_table(doc, headers, rows):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].paragraphs[0].add_run(h).bold = True
        for r in hdr[i].paragraphs[0].runs:
            r.font.size = Pt(10)
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].paragraphs[0].add_run(val).font.size = Pt(10)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


doc = Document()

# Base styling
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(11)

# ---- Title ----
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = title.add_run("Book Store (FastAPI)")
r.bold = True
r.font.size = Pt(26)
r.font.color.rgb = DARK
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
rs = sub.add_run("Build It From Scratch — A Simple Learning Guide")
rs.font.size = Pt(14)
rs.font.color.rgb = INDIGO
intro = doc.add_paragraph()
intro.alignment = WD_ALIGN_PARAGRAPH.CENTER
ri = intro.add_run("The full stack, end-to-end: FastAPI/Pydantic/SQLAlchemy/Alembic/MySQL/JWT "
                    "through Redis/Celery/Pandas/Pytest/Docker/AWS — explained in build order.")
ri.italic = True
ri.font.size = Pt(10.5)
ri.font.color.rgb = GREY
doc.add_paragraph()


def h1(text):
    h = doc.add_heading(text, level=1)
    for run in h.runs:
        run.font.color.rgb = DARK


def h2(text):
    h = doc.add_heading(text, level=2)
    for run in h.runs:
        run.font.color.rgb = INDIGO


# ===== Stack overview =====
body(doc, "Sections 1-10 build the core app (the original guide). Sections 11-18 then add "
          "the rest of a production-style Python stack on top of it, in the order you'd "
          "naturally reach for them once the basics work:", bold=True)
code_block(doc, [
    "Python -> FastAPI -> Pydantic -> SQLAlchemy -> Alembic -> MySQL -> JWT/OAuth2",
    "       -> Dependency Injection -> Redis -> Celery -> HTTPX -> Pandas/OpenPyXL",
    "       -> Pytest -> Docker -> AWS",
])
make_table(
    doc,
    ["Layer", "What it does here", "Where", "Section"],
    [
        ["Python", "The language everything below is written in.", "everywhere", "-"],
        ["FastAPI", "Routes URLs to functions, validates request/response shapes.", "every api.py/web.py", "6"],
        ["Pydantic", "Validates JSON bodies + typed settings from .env.", "every schemas.py, core/config.py", "4, 5"],
        ["SQLAlchemy", "The ORM - Python classes <-> database tables.", "every models.py, core/database.py", "2, 3"],
        ["Alembic", "Versioned, incremental schema changes.", "alembic/", "11"],
        ["MySQL", "Where the rows actually live.", "core/config.database_url", "4"],
        ["JWT / OAuth2", "Proves 'who is this?' on the stateless API door.", "core/security.py, auth/", "4, 5"],
        ["Dependency Injection", "Depends(...) wires DB sessions + auth guards into routes.", "auth/dependencies.py", "5"],
        ["Redis", "Caches the book catalogue so repeat reads skip the DB.", "core/redis_client.py, books/cache.py", "12"],
        ["Celery", "Runs slow work (building a report) off the request thread.", "core/celery_app.py, reports/tasks.py", "13"],
        ["HTTPX", "Calls external HTTP APIs (Claude/Groq, Business Central) server-side.", "core/ai.py, bc/client.py", "14"],
        ["Pandas / OpenPyXL", "Turns SQL rows into a downloadable Excel sales report.", "reports/tasks.py", "15"],
        ["Pytest", "Automated tests - no manual clicking through /docs.", "tests/", "16"],
        ["Docker", "One command runs the whole stack.", "Dockerfile, docker-compose.yml", "17"],
        ["AWS", "Where it actually runs for real users.", "AWS_DEPLOYMENT_GUIDE.md", "18"],
    ],
)

# ===== 1 =====
h1("1. What Are We Building?")
body(doc, "A small online book store with two front doors over the same data:")
make_table(
    doc,
    ["Door", "What it is", "Who uses it", "Lives in"],
    [
        ["REST API", "Returns JSON, uses a JWT token", "Mobile apps, Postman, programs", "app/<feature>/api.py"],
        ["Web UI", "Returns HTML pages, uses a login cookie", "A human in a browser", "app/<feature>/web.py"],
    ],
)
body(doc, "Both doors talk to the same database tables through the same models. "
          "That is the central idea: write the data layer once, expose it two ways.")
body(doc, "Features: register/login, browse & search books, admin manages the catalogue, "
          "users add to cart/wishlist, save addresses, place orders, and leave 1–5 star feedback.")

# ===== 2 =====
h1("2. The Mental Model (read this before any code)")
body(doc, "Think of the app as layers. A request falls down through them and a response climbs back up:")
code_block(doc, [
    "        Browser / Postman",
    "              |",
    "              v",
    "   +-----------------------+",
    "   |  Router  (the URL)    |  app/<feature>/api.py web.py  'hit /books, run this'",
    "   +-----------------------+",
    "   |  Schema  (the shape)  |  app/<feature>/schemas.py     'input must look like this'",
    "   +-----------------------+",
    "   |  Deps    (the guard)  |  app/auth/dependencies.py     'logged in? are you admin?'",
    "   +-----------------------+",
    "   |  Model   (the table)  |  app/<feature>/models.py      'this maps to a DB table'",
    "   +-----------------------+",
    "   |  Database (the engine)|  app/core/database.py         'open/close the DB connection'",
    "   +-----------------------+",
    "              |",
    "              v",
    "            MySQL",
])
body(doc, "The code is organised feature-first: each domain (auth, books, cart, ...) is a "
          "self-contained package holding its own models.py, schemas.py, api.py and web.py. "
          "Cross-cutting infrastructure lives under app/core:")
bullet(doc, "core/config.py — settings (DB password, secret key) read from a .env file.")
bullet(doc, "core/database.py — the engine/session + the Base/TimestampMixin models share.")
bullet(doc, "core/security.py — password hashing + JWT token creation.")
bullet(doc, "core/templating.py — turns data into HTML pages (web door only).")
bullet(doc, "auth/dependencies.py — the auth/role guards every feature reuses.")
bullet(doc, "main.py — the wiring that bolts all of the above together.")
body(doc, "Golden rule: when confused, follow one request from the URL (router) downward. "
          "Everything else is support.", bold=True)

# ===== 3 =====
h1("3. Folder Structure Explained")
code_block(doc, [
    "Book_Store_FastAPI/",
    "|",
    "|-- run.py               (1) START HERE - the 'go' button: python run.py",
    "|-- requirements.txt     the list of libraries to install",
    "|-- .env                 YOUR secret settings (DB password) - never commit",
    "|-- .env.example         a template of .env to copy from",
    "|-- README.md            quick reference",
    "|",
    "|-- app/                 ALL the application code lives here",
    "    |-- main.py          (2) the wiring - builds the app, attaches everything",
    "    |",
    "    |-- core/            cross-cutting infrastructure (shared by every feature)",
    "    |   |-- config.py        settings loaded from .env",
    "    |   |-- database.py      engine + session helper + Base/TimestampMixin",
    "    |   |-- security.py      (4) password hashing + JWT tokens",
    "    |   |-- templating.py    (7) Jinja2 setup + flash messages + render() helper",
    "    |",
    "    |-- auth/            (6) a FEATURE package - one self-contained domain",
    "    |   |-- models.py        (3) the User table, as a Python class",
    "    |   |-- schemas.py       (4) the shape of this feature's API request bodies",
    "    |   |-- dependencies.py  (5) guards: 'must be logged in / must be admin'",
    "    |   |-- api.py           JSON API  -> mounted under /api",
    "    |   |-- web.py           HTML pages -> mounted at /",
    "    |",
    "    |-- books/ cart/ wishlist/ address/ orders/ feedback/",
    "    |                    each repeats the shape: models / schemas / api / web",
    "    |-- dashboard/ users/ password/",
    "    |                    web.py only (screens that reuse other features' tables)",
    "    |",
    "    |-- templates/       (7) the HTML files (Jinja2), web door only",
    "    |   |-- base.html         shared layout (header, nav, CSS) - others extend it",
    "    |   |-- auth/  books/  cart/  ... etc.",
    "    |",
    "    |-- static/          files served as-is (uploaded book cover images)",
    "        |-- book-covers/",
])
body(doc, "The numbered items (1–7) are the order we build them in Section 6 — they now map "
          "to roles, not single files: infrastructure in core/, and every feature package "
          "repeats the same models -> schemas -> dependencies -> api/web shape.", italic=True)

# ===== 4 =====
h1("4. Setup From Scratch (do this first)")
h2("Prerequisites")
bullet(doc, "Python 3.11+  — check with: python --version")
bullet(doc, "MySQL running — XAMPP's MySQL panel is fine. (You can swap to SQLite, see Section 10.)")
h2("Step-by-step (PowerShell on Windows)")
code_block(doc, [
    "# 1. Go to the project folder",
    "cd C:\\Users\\manju\\OneDrive\\Desktop\\python\\Book_Store_FastAPI",
    "",
    "# 2. Create an isolated virtual environment",
    "python -m venv .venv",
    "",
    "# 3. Activate it (you'll see (.venv) in your prompt)",
    ".\\.venv\\Scripts\\Activate.ps1",
    "",
    "# 4. Install all libraries from requirements.txt",
    "pip install -r requirements.txt",
    "",
    "# 5. Create your settings file from the template, then edit DB credentials",
    "copy .env.example .env",
    "notepad .env",
])
h2("Create the database (one time)")
body(doc, "Open phpMyAdmin (or the MySQL shell) and run:")
code_block(doc, ["CREATE DATABASE book_store_product;"])
body(doc, "You do NOT create tables by hand — the app does that automatically on startup "
          "(because CREATE_TABLES=true). See main.py's on_startup.")
h2("Run it")
code_block(doc, ["python run.py"])
body(doc, "Then open:")
bullet(doc, "Web UI  -> http://127.0.0.1:8000/")
bullet(doc, "API docs (Swagger, try endpoints live) -> http://127.0.0.1:8000/docs")
body(doc, "What just happened: run.py told uvicorn (the server) to load app.main:app. "
          "On startup the app created all tables. Now it listens for requests.")

# ===== 5 =====
h1("5. Understand the Key Libraries (1 line each)")
make_table(
    doc,
    ["Library", "Job"],
    [
        ["FastAPI", "The web framework — routes URLs to functions, validates input."],
        ["uvicorn", "The server that runs FastAPI and listens on a port."],
        ["SQLAlchemy", "The ORM — use Python objects instead of raw SQL."],
        ["PyMySQL", "The driver SQLAlchemy uses to talk to MySQL."],
        ["Pydantic", "Validates request data and reads settings (schemas + config)."],
        ["passlib + bcrypt", "Hashes passwords safely (never store plain passwords)."],
        ["PyJWT", "Creates/reads the JWT token used by the API door."],
        ["Jinja2", "Templating engine — fills {{ values }} into HTML for the web door."],
        ["itsdangerous", "Signs the session cookie so users can't tamper with it."],
        ["Alembic", "Generates/runs versioned schema migrations. -> Section 11"],
        ["redis", "Python client for the Redis cache. -> Section 12"],
        ["celery", "Runs background jobs on a separate worker process. -> Section 13"],
        ["pandas", "Shapes SQL rows into a table for export. -> Section 15"],
        ["openpyxl", "The engine Pandas uses to write real .xlsx files. -> Section 15"],
        ["pytest", "Runs the automated test suite. -> Section 16"],
    ],
)

# ===== 6 =====
h1("6. Build It From Scratch — The Correct Order")
body(doc, "Write the files so each one only depends on things that already exist. "
          "This is exactly how you would build it yourself.")

h2("(1) core/config.py — settings first")
body(doc, "Everything needs settings (the DB URL, the secret key). Read them from .env "
          "using Pydantic so they're typed and validated.")
code_block(doc, [
    "class Settings(BaseSettings):",
    "    app_name: str = 'Book Store'",
    "    secret_key: str = 'insecure-dev-secret-change-me'",
    "    db_host: str = '127.0.0.1'",
    "    db_database: str = 'book_store_product'",
    "    db_username: str = 'root'",
    "    db_password: str = ''",
    "    @property",
    "    def database_url(self) -> str:        # builds the connection string",
    "        return f'mysql+pymysql://{self.db_username}:{self.db_password}@...'",
    "",
    "settings = get_settings()   # one shared instance everyone imports",
])
body(doc, "Why a property for database_url? So the rest of the app never has to know how to "
          "assemble the connection string — it just asks settings.database_url.", italic=True)

h2("(2) core/database.py — the connection")
body(doc, "Create the engine (pool of DB connections), a SessionLocal factory (each request "
          "gets its own short-lived session), and the Base class all models inherit from. "
          "The shared TimestampMixin lives here too, so every feature's models import both "
          "from one place.")
code_block(doc, [
    "engine = create_engine(settings.database_url, pool_pre_ping=True)",
    "SessionLocal = sessionmaker(bind=engine)",
    "",
    "class Base(DeclarativeBase):   # models inherit from this",
    "    pass",
    "",
    "def get_db():                  # dependency: open a session, always close it",
    "    db = SessionLocal()",
    "    try:",
    "        yield db",
    "    finally:",
    "        db.close()",
])
body(doc, "Key idea — get_db: Any endpoint that needs the DB writes db: Session = Depends(get_db). "
          "FastAPI runs get_db, hands you a session, and guarantees it gets closed (the finally). "
          "You never leak connections.", bold=True)

h2("(3) <feature>/models.py — the tables")
body(doc, "Each class = one table, and it lives in its own feature package (User in "
          "auth/models.py, Book in books/models.py, ...). Each mapped_column = one column. "
          "relationship() links tables across features (e.g. a User has many Books) using "
          "string class names, so the packages don't import each other at module load.")
code_block(doc, [
    "class User(Base, TimestampMixin):",
    "    __tablename__ = 'users'",
    "    id: Mapped[int] = mapped_column(primary_key=True)",
    "    role: Mapped[str] = mapped_column(String(255), default='user')",
    "    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)",
    "    password: Mapped[str] = mapped_column(String(255))      # stores the HASH",
    "    books: Mapped[list['Book']] = relationship(back_populates='user')",
])
body(doc, "Tables here: User, Book, Cart, WishList, Address, Order, Feedback. The TimestampMixin "
          "adds created_at / updated_at to all of them for free.")
body(doc, "Why this matters: once a table is a class, you write db.get(User, 5) instead of "
          "SELECT * FROM users WHERE id=5. The ORM converts.", italic=True)

h2("(4) core/security.py + <feature>/schemas.py — protect and validate")
body(doc, "core/security.py does two jobs — hash passwords, and mint/read JWT tokens:")
code_block(doc, [
    "hash_password('secret1')          # -> '$2b$12$.....' stored in DB",
    "verify_password('secret1', hash)  # -> True / False at login",
    "",
    "create_access_token(user.id)   # login hands this to the client",
    "decode_access_token(token)     # every later request: who is this?",
])
body(doc, "Each feature's schemas.py defines the shape of incoming API JSON with Pydantic (e.g. "
          "auth/schemas.py holds RegisterRequest). If the input doesn't match, FastAPI "
          "auto-rejects it with a 422 before your code runs.")
code_block(doc, [
    "class RegisterRequest(BaseModel):",
    "    email: EmailStr                       # must be a valid email",
    "    password: str = Field(min_length=6)   # at least 6 chars",
    "    confirm_password: str",
    "    @field_validator('confirm_password')  # custom rule: must match password",
    "    ...",
])
body(doc, "Schema vs Model — don't confuse them:", bold=True)
bullet(doc, "Model = a database table (SQLAlchemy).")
bullet(doc, "Schema = the validation shape of a request/response (Pydantic).")

h2("(5) auth/dependencies.py — the guards")
body(doc, "Dependencies are reusable checks you attach to endpoints. This file answers "
          "'who are you and are you allowed here?' — once, in one place. It lives in the auth "
          "package because auth is the foundation every other feature imports its guards from.")
body(doc, "API door (token-based):")
code_block(doc, [
    "def get_current_api_user(credentials=Depends(bearer_scheme), db=Depends(get_db)):",
    "    sub = decode_access_token(credentials.credentials)   # read the token",
    "    return db.get(User, int(sub))                        # load that user",
    "",
    "def require_api_role(role):          # factory: returns a guard for a role",
    "    def checker(user=Depends(get_current_api_user)):",
    "        if user.role != role:",
    "            raise HTTPException(403, f'Only {role}s are allowed')",
    "        return user",
    "    return checker",
])
body(doc, "Web door (cookie/session-based):")
code_block(doc, [
    "def require_web_user(request, db=Depends(get_db)):",
    "    user_id = request.session.get('user_id')     # set at login",
    "    if not user_id:",
    "        raise RedirectException('/login', error='Please sign in.')  # bounce",
    "    return db.get(User, int(user_id))",
])
body(doc, "The payoff: an admin-only endpoint just adds "
          "admin: User = Depends(require_api_role('admin')) — no auth code repeated inside.", bold=True)

h2("(6) <feature>/api.py + web.py — the endpoints (the heart)")
body(doc, "Now you write the actual URLs. Each feature exposes its routes through an APIRouter "
          "in api.py (the JSON door) and another in web.py (the HTML door). Read this API "
          "example slowly — every line ties back to a layer you already built:")
code_block(doc, [
    "@router.post('/addingBook', status_code=201)",
    "def adding_book(",
    "    payload: BookCreate,                              # (4) schema validates body",
    "    admin: User = Depends(require_api_role('admin')), # (5) guard: must be admin",
    "    db: Session = Depends(get_db),                    # (2) DB session, auto-closed",
    "):",
    "    book = Book(user_id=admin.id, name=payload.name, ...)  # (3) build a model row",
    "    db.add(book); db.commit(); db.refresh(book)            # save it",
    "    return {'status': 201, 'message': 'Book created', 'book': _serialize(book)}",
])
body(doc, "That single function IS the whole architecture in miniature.", italic=True)
body(doc, "The web version returns a redirect + flash message instead of JSON, and reads form "
          "fields instead of a JSON schema:")
code_block(doc, [
    "@router.post('')",
    "def store(request: Request, name: str = Form(...), image: UploadFile = File(...),",
    "          user: User = Depends(require_web_role('admin')), db=Depends(get_db)):",
    "    # ...save the file, insert the Book...",
    "    flash(request, f'Book \"{name}\" created successfully.')   # one-time message",
    "    return RedirectResponse('/books', status_code=303)       # Post/Redirect/Get",
])
body(doc, "Why redirect after a POST (the PRG pattern)? So a browser refresh doesn't resubmit "
          "the form. The success message survives the redirect via a one-time 'flash' stored in "
          "the session cookie.", bold=True)

h2("(7) core/templating.py + templates/ — the HTML (web door only)")
body(doc, "core/templating.py configures Jinja2 and gives you a render() helper that always "
          "injects the current user + any flash messages, so templates stay simple.")
body(doc, "templates/base.html is the skeleton (header, nav, all the CSS). Every other page does "
          "{% extends 'base.html' %} and fills in just its content block:")
code_block(doc, [
    "{% extends 'base.html' %}",
    "{% block content %}",
    "  {% for book in books %}",
    "     <div class='card'>{{ book.name }} - Rs {{ book.price }}</div>",
    "  {% endfor %}",
    "{% endblock %}",
])
body(doc, "The router passes books into render(...), Jinja loops over them, and the user gets a "
          "finished HTML page.")

h2("(2 again) main.py — wire everything together")
body(doc, "Built last because it imports everything else. It:")
numbered(doc, "Creates the FastAPI() app.")
numbered(doc, "Adds the SessionMiddleware (enables the cookie the web door needs).")
numbered(doc, "Mounts /static for images.")
numbered(doc, "On startup, creates all tables (Base.metadata.create_all).")
numbered(doc, "Registers exception handlers (RedirectException -> real redirect; validation "
              "errors -> friendly flashes for web forms).")
numbered(doc, "Includes every router — API ones under /api, web ones at /.")
code_block(doc, [
    "from app.auth import api as auth_api, web as auth_web",
    "from app.books import api as books_api, web as books_web",
    "# ...one import per feature...",
    "",
    "for module in (auth_api, books_api, cart_api, ...):",
    "    app.include_router(module.router, prefix='/api')   # API door",
    "for module in (auth_web, dashboard_web, books_web, ...):",
    "    app.include_router(module.router)                  # web door",
])

h2("run.py — the button")
code_block(doc, ["uvicorn.run('app.main:app', host='127.0.0.1', port=8000, reload=True)"])
body(doc, "reload=True restarts the server whenever you save a file — great for learning.")

# ===== 7 =====
h1("7. Follow One Full Request (the 'aha' moment)")
body(doc, "Scenario: a logged-in admin adds a book through the API.", bold=True)
numbered(doc, "Client sends POST /api/addingBook with a JSON body and an Authorization: Bearer <token> header.")
numbered(doc, "main.py routed /api/* to the books API router -> matches adding_book.")
numbered(doc, "FastAPI sees payload: BookCreate -> validates the JSON (schemas, 4). Bad data? Auto-422; your code never runs.")
numbered(doc, "FastAPI sees Depends(require_api_role('admin')) -> runs the guard (5): decode token, load user, check role. Not admin? 403.")
numbered(doc, "FastAPI sees Depends(get_db) -> opens a DB session (2).")
numbered(doc, "Your function builds a Book model (3), db.add + db.commit -> SQLAlchemy emits the INSERT via PyMySQL -> MySQL stores the row.")
numbered(doc, "You return a dict -> FastAPI serializes it to JSON -> client gets 201 Created.")
numbered(doc, "The session from step 5 is automatically closed (get_db's finally).")
body(doc, "Every numbered layer from Section 6 appeared exactly once. That is the whole app.", italic=True)

# ===== 8 =====
h1("8. How to Study This Repo Effectively")
numbered(doc, "Run it first (Section 4) and click around /docs and the web UI. Seeing it work makes the code concrete.")
numbered(doc, "Read in build order: core/config -> core/database -> a feature's models -> schemas -> auth/dependencies -> its api/web -> its template -> main. Don't start in main.py.")
numbered(doc, "Pick ONE feature and trace it end-to-end. Books is best — open app/books/ and read api.py and web.py side by side, plus the template. Same data, two doors.")
numbered(doc, "Then change something small — this repo already did it, so read it as a worked example: books.genre (see below). Doing it once teaches more than reading ten times.")
body(doc, "Worked example — books.genre was added exactly the way you'd add any new column:", bold=True)
bullet(doc, "The field in app/books/models.py.")
bullet(doc, "BookCreate/BookUpdate in app/books/schemas.py.")
bullet(doc, "Read/written in app/books/api.py and app/books/web.py, passed to Book(...).")
bullet(doc, "Shown in templates/books/index.html and templates/books/edit.html.")
bullet(doc, "Applied with a migration, not a dropped table — alembic/versions/0002_add_genre_and_order_totals.py (Section 11).")
body(doc, "Now do the same for a field of your own (e.g. an isbn on Book) — that's the exercise.", italic=True)

# ===== 9 =====
h1("9. Common Gotchas for Beginners")
bullet(doc, "'Table doesn't have my new column.' create_all only CREATES missing tables; it does NOT alter existing ones. While learning with CREATE_TABLES=true, dropping the table and restarting is the fast path. For a database you actually care about, use a migration instead — Section 11 does exactly this for real.")
bullet(doc, "Can't connect to MySQL. Is MySQL actually running? Do .env credentials match? Does book_store_product exist?")
bullet(doc, "401 on API calls. Log in (POST /api/login), copy access_token, send it as Authorization: Bearer <token>. In /docs click the Authorize button.")
bullet(doc, "Web pages bounce me to /login. The web door uses the session cookie, not the JWT. Log in through the web form.")
bullet(doc, "Never commit .env — it holds secrets. .env.example is the safe template.")

# ===== 10 =====
h1("10. Want Zero Setup? Use SQLite Instead of MySQL")
body(doc, "To learn without installing MySQL, point the app at a local file DB. In app/core/config.py change database_url to:")
code_block(doc, [
    "@property",
    "def database_url(self) -> str:",
    "    return 'sqlite:///./book_store.db'",
])
body(doc, "and in app/core/database.py add the SQLite-only arg:")
code_block(doc, [
    "engine = create_engine(settings.database_url,",
    "                       connect_args={'check_same_thread': False})",
])
body(doc, "Now python run.py creates a book_store.db file — no server needed. (The repo ships "
          "configured for MySQL to match the original Laravel app; SQLite is purely a learning convenience.)")

# ===== 11 =====
h1("11. Alembic — Schema Migrations")
h2("The problem it solves")
body(doc, "Base.metadata.create_all() (Section 6, step 2) only CREATES missing tables. It never "
          "touches a table that already exists — so the day you add a column to a model that's "
          "already live, nothing happens. This app actually hit that exact wall already: "
          "app/core/database.py's ensure_ai_columns() is a hand-rolled ALTER TABLE ADD COLUMN "
          "hack, written specifically because create_all couldn't add the AI columns (tags, "
          "embedding, sentiment) to a database that predated them. Alembic is the general, "
          "versioned way to do what that hack does one-off: describe a schema change, apply it, "
          "and be able to undo it.")
h2("Where it lives")
code_block(doc, [
    "alembic.ini            # Alembic's config - script location, logging",
    "alembic/env.py         # wired to import every feature's models + app settings",
    "alembic/versions/",
    "    0001_initial_schema.py                  # the 7 tables, as create_all makes them",
    "    0002_add_genre_and_order_totals.py      # books.genre + orders.quantity/total_price",
])
body(doc, "alembic/env.py does two non-default things: (1) imports every feature's models.py "
          "before comparing anything, so Base.metadata actually contains every table — "
          "autogenerate can only see a model that has been imported somewhere; (2) reads the DB "
          "URL from app.core.config.settings (your .env) instead of a second, easy-to-forget "
          "copy in alembic.ini.")
h2("The workflow (how migration 0002 was actually made)")
code_block(doc, [
    "# 1. Change the model(s) - e.g. add a field in app/books/models.py",
    "# 2. Ask Alembic to diff 'what the models say' vs 'what the DB has':",
    "alembic revision --autogenerate -m \"add genre to books, quantity/total_price to orders\"",
    "",
    "# 3. OPEN the generated file in alembic/versions/ and read it - autogenerate is a",
    "#    draft, not gospel. This repo's 0002 hand-adds server_default='1' to the new",
    "#    NOT NULL orders.quantity column, because adding a NOT NULL column to a table",
    "#    that already has rows fails outright without one.",
    "",
    "# 4. Apply it:",
    "alembic upgrade head",
])
bullet(doc, "alembic current    — which revision is the DB actually on?")
bullet(doc, "alembic history    — the full chain, oldest -> newest")
bullet(doc, "alembic downgrade -1  — undo the last migration (runs downgrade())")
bullet(doc, "alembic upgrade head  — (re)apply everything up to the latest")
h2("How this repo's two migrations were verified")
body(doc, "There's no MySQL server in a fresh checkout to test against, so both migrations were "
          "validated against a throwaway SQLite database instead:")
code_block(doc, [
    "$env:ALEMBIC_SQLALCHEMY_URL = \"sqlite:///./_alembic_test.db\"",
    "alembic upgrade head        # 0001 -> 0002, from empty",
    "alembic downgrade -1        # back to 0001",
    "alembic upgrade head        # forward again",
    "alembic check                # \"No new upgrade operations detected\" = models == DB",
    "Remove-Item _alembic_test.db",
])
body(doc, "ALEMBIC_SQLALCHEMY_URL (read in alembic/env.py) is a hook made for exactly this — "
          "pointing migrations at a disposable database without touching .env. Against your real "
          "MySQL, skip that variable and Alembic just uses .env as normal.", italic=True)
h2("Alembic vs. CREATE_TABLES=true")
bullet(doc, "CREATE_TABLES=true (.env) -> 'give me a schema with zero setup' (Section 4). Fine for a scratch database you'll happily drop.")
bullet(doc, "Alembic -> 'evolve a schema I already have data in, and be able to undo it.'")
body(doc, "Once you're using Alembic for real changes, set CREATE_TABLES=false so the two "
          "mechanisms never race each other — docker-compose.yml (Section 17) already does this "
          "and runs alembic upgrade head before every start instead.", bold=True)

# ===== 12 =====
h1("12. Redis — Caching the Book Catalogue")
h2("Why here")
body(doc, "GET /api/displayAllBooks (and the web /books page) is read constantly and changes "
          "rarely — the textbook case for a cache. This is the cache-aside pattern: check the "
          "cache first; on a miss, hit the database and then fill the cache; on any write, "
          "delete the cached copy so the next read is forced back to the database.")
h2("Where it lives")
bullet(doc, "app/core/redis_client.py — one shared redis.Redis client, exactly like engine/SessionLocal in core/database.py.")
bullet(doc, "app/books/cache.py — get_cached_books(), set_cached_books(), invalidate_books_cache(). Every function wraps its Redis call in try/except: a Redis outage degrades the app to 'slower', never 'broken'.")
bullet(doc, "Wired into app/books/api.py::display_all_books (reads the cache first); every mutation in books/api.py + books/web.py calls invalidate_books_cache(); orders/api.py::place_order and orders/web.py::store invalidate too (placing an order changes a book's stock count).")
h2("Try it")
code_block(doc, [
    "# Run Redis locally (Docker):",
    "docker run -p 6379:6379 redis:7-alpine",
    "# or via this repo's compose file:",
    "docker compose up redis",
])
body(doc, "Then call GET /api/displayAllBooks twice (with a valid token) — the response body "
          "includes \"cached\": false the first time (database) and \"cached\": true the second "
          "(Redis), until REDIS_CACHE_SECONDS (default 60s, in .env) expires or a write "
          "invalidates it. Stop Redis and call it again: same data, \"cached\" always false — the "
          "fallback path.")

# ===== 13 =====
h1("13. Celery — Background Jobs")
h2("Why here")
body(doc, "A request handler should answer fast. Building an Excel report by querying every "
          "order and writing a spreadsheet is exactly the kind of work that shouldn't happen "
          "inside that handler. Celery moves that work to a separate process (the worker): "
          "FastAPI enqueues a task and returns immediately; the worker picks it up whenever "
          "it's free; the client polls for the result.")
body(doc, "Redis plays two unrelated roles here, on two different logical DB numbers so they "
          "never collide with each other or with the Section 12 cache: broker "
          "(CELERY_BROKER_DB) — where FastAPI drops off 'please run this task'; result backend "
          "(CELERY_RESULT_DB) — where the worker writes the answer.")
h2("Where it lives")
bullet(doc, "app/core/celery_app.py — the shared Celery app (broker + backend URLs, from settings).")
bullet(doc, "app/reports/tasks.py — generate_orders_report, the actual task. Runs in the worker's process, so it can't use Depends(get_db) — it opens its own SessionLocal() directly.")
bullet(doc, "app/reports/api.py / app/reports/web.py — enqueue (.delay()) and poll (AsyncResult) endpoints, JWT and session flavours.")
bullet(doc, "app/templates/reports/index.html — a button + fetch() polling loop.")
h2("Run it")
code_block(doc, [
    "# Terminal 1 - Redis (broker + backend)",
    "docker run -p 6379:6379 redis:7-alpine",
    "",
    "# Terminal 2 - the Celery worker (a SEPARATE process from the web server)",
    "celery -A app.core.celery_app worker --loglevel=info --pool=solo",
    "# --pool=solo: Celery's default 'prefork' pool needs fork(), which Windows",
    "# doesn't have. --pool=solo runs one task at a time in-process instead.",
    "",
    "# Terminal 3 - the app, as always",
    "python run.py",
])
body(doc, "Log in as an admin, open /reports, click Generate report. The page POSTs to "
          "/reports/orders/export (-> task.delay(), returns a task_id immediately), then polls "
          "GET /reports/orders/export/{task_id} every 1.5s until the worker finishes and the "
          "state flips to SUCCESS with a download link.")
body(doc, "No worker running? The task just sits in Redis's queue forever and the page polls "
          "PENDING indefinitely — a good way to feel why the worker is a separate, "
          "must-be-running process, not optional plumbing.", italic=True)

# ===== 14 =====
h1("14. HTTPX — Calling Other Services")
body(doc, "Already in this codebase before this guide's later sections were added — worth "
          "calling out explicitly since it's the 'make an HTTP request from the server' tool "
          "the stack diagram asks about.")
bullet(doc, "app/core/ai.py — talks to the Anthropic/Groq Messages APIs directly over HTTPS with httpx, instead of pulling in a heavier SDK.")
bullet(doc, "app/bc/client.py — Business Central's Azure AD OAuth2 client-credentials flow (fetch a token, then call the BC REST/OData API) — all httpx.")
body(doc, "Every route handler in this app is a plain def (not async def), so FastAPI runs it in "
          "Starlette's thread pool — a blocking httpx call there does NOT freeze the server for "
          "other requests. That's why these files use the plain synchronous httpx.Client/httpx.get "
          "API rather than httpx.AsyncClient — there's no event loop here to block.")

# ===== 15 =====
h1("15. Pandas + OpenPyXL — The Sales Report")
body(doc, "Two libraries, two different jobs, chained in app/reports/tasks.py:")
bullet(doc, "Pandas — turns a list of SQLAlchemy result rows into a DataFrame (a table with named columns). _orders_dataframe() joins Order with Book, User and Address and hands the rows straight to pd.DataFrame(rows) — no manual dict-building.")
bullet(doc, "OpenPyXL — the engine that knows how to write that DataFrame out as a real .xlsx file (Excel's zipped-XML format). df.to_excel(path, engine='openpyxl') is Pandas handing the actual byte-level writing off to OpenPyXL.")
body(doc, "The report columns: order id, when it was placed, customer name/email, book "
          "name/author/genre, quantity, unit price, the order's stored total_price, and delivery "
          "city — see Section 11 for where orders.quantity/total_price came from (they didn't "
          "exist until migration 0002).")
body(doc, "The file is written to app/static/reports/<task-id>.xlsx, which is why it's "
          "downloadable straight from /static/reports/... — the same static mount Section 6 "
          "already set up for book covers.")

# ===== 16 =====
h1("16. Pytest — The Test Suite")
h2("Why it matters here specifically")
body(doc, "Up to now, 'does it work' meant clicking through /docs or the web UI by hand. That "
          "doesn't scale. tests/ exercises the real API (register -> login -> create a book -> "
          "place an order -> export a report) without needing MySQL, Redis, or a Celery worker "
          "actually running.")
h2("Where it lives")
code_block(doc, [
    "pytest.ini            # testpaths = tests",
    "tests/conftest.py     # the 3 swaps that make this possible",
    "tests/test_auth.py    # register/login/duplicate-email/401-without-token",
    "tests/test_books.py   # admin-only writes, the cached read path",
    "tests/test_orders.py  # stock checks, address ownership, the full order flow",
    "tests/test_reports.py # the Celery + Pandas/OpenPyXL pipeline, end-to-end",
])
h2("The three swaps (tests/conftest.py)")
numbered(doc, "Database — app.core.database.engine/SessionLocal are replaced with an in-memory SQLite database before app.main is imported. This works because get_db() looks up SessionLocal by name at call time, so every router already using get_db transparently starts talking to the test database too, with zero application-code changes.")
numbered(doc, "Celery — task_always_eager=True makes .delay() run the task synchronously in the test process instead of needing a real worker. result_backend='cache+memory://' means AsyncResult(task_id) can still be polled afterwards, purely in memory — this is what lets test_reports.py test the entire enqueue -> run -> poll -> download flow with no Redis and no worker process.")
numbered(doc, "Redis cache — deliberately left alone. Because books/cache.py already treats a connection failure as a cache miss, running tests with no Redis server simply exercises that fallback path for free.")
h2("Run it")
code_block(doc, [
    "pip install -r requirements.txt   # pytest is already listed",
    "pytest                             # from the project root",
])
body(doc, "Every test registers its own user with a unique email — no shared fixtures to reset "
          "between tests, no test ordering to worry about.")

# ===== 17 =====
h1("17. Docker — One Command for the Whole Stack")
h2("Why here")
body(doc, "By this point the app needs four things running together: the API server, a Celery "
          "worker, MySQL, and Redis. Docker Compose starts all four with one command, wired to "
          "talk to each other, instead of you juggling four terminals every time you sit down to work.")
h2("Where it lives")
make_table(
    doc,
    ["Service", "Image/build", "Role"],
    [
        ["db", "mysql:8.0", "the database (Section 4/10)"],
        ["redis", "redis:7-alpine", "cache (Section 12) + Celery broker/backend (Section 13)"],
        ["app", "built from Dockerfile", "runs alembic upgrade head (Section 11), then uvicorn"],
        ["worker", "built from Dockerfile", "celery -A app.core.celery_app worker"],
    ],
)
body(doc, "Dockerfile builds one image; the SAME image runs both the web server and the worker "
          "(Section 13 already showed they're just two different commands over identical code). "
          ".dockerignore keeps .venv/, .git/, .env, and generated files out of the image.")
h2("Run it")
code_block(doc, ["docker compose up --build"])
body(doc, "Then the same URLs as always: http://127.0.0.1:8000/ and .../docs. The app service's "
          "command runs alembic upgrade head BEFORE uvicorn starts — every container start brings "
          "the schema up to date automatically (a no-op once it already is), which is why that "
          "service also sets CREATE_TABLES=false — Alembic is now the only thing allowed to "
          "change the schema.")
code_block(doc, [
    "docker compose exec app alembic revision --autogenerate -m \"...\"",
    "docker compose exec app pytest",
])
body(doc, "Stop everything with docker compose down (add -v to also delete the MySQL data volume "
          "and start completely fresh).")

# ===== 18 =====
h1("18. AWS — Deploying It for Real")
body(doc, "Everything above runs great on one machine. AWS is where the same pieces become "
          "independently-scalable managed services instead of containers on your laptop. This "
          "repo's build stayed documentation-only here (no AWS account required to work through "
          "Sections 1-17) — see AWS_DEPLOYMENT_GUIDE.md in the project root for the full, "
          "step-by-step walkthrough (networking, RDS, ElastiCache, S3, EC2 vs. ECS/Fargate, "
          "secrets, and a go-live checklist).")
make_table(
    doc,
    ["Runs locally as...", "Becomes, on AWS", "Why"],
    [
        ["db (MySQL container)", "RDS for MySQL", "managed backups, patching, failover"],
        ["redis container", "ElastiCache for Redis", "managed, same cache + Celery broker role"],
        ["app container", "EC2 (simple) or ECS/Fargate (scales)", "runs the exact same Docker image"],
        ["worker container", "a second EC2/ECS service, same image", "Celery worker scales independently of the API"],
        ["app/static/* folders", "S3", "container disks aren't durable/shared across instances"],
        [".env", "SSM Parameter Store / Secrets Manager", "secrets shouldn't live in an image or a repo"],
    ],
)

# ===== Summary =====
h1("One-Paragraph Summary")
body(doc, "You configure settings (core/config), open a database (core/database), describe tables "
          "as classes (each feature's models), validate inputs (each feature's schemas), hash "
          "passwords and mint tokens (core/security), guard endpoints (auth/dependencies), write "
          "the URLs (each feature's api/web), render HTML for humans (templates + core/templating), "
          "and bolt it all together (main). A request falls DOWN through router -> schema -> guard "
          "-> model -> DB, and the response climbs back UP. Master one feature's path and you've "
          "mastered them all. Everything after Section 10 is the same idea applied outward: "
          "Alembic versions the DB itself, Redis and Celery make the app fast and non-blocking, "
          "Pandas/OpenPyXL turn rows into a real spreadsheet, Pytest proves it all still works, "
          "and Docker/AWS are just increasingly realistic places to run the exact same code.",
     italic=True)

out = "Book_Store_FastAPI_Learning_Guide.docx"
doc.save(out)
print("Saved:", out)
