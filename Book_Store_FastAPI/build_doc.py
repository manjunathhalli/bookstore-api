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
ri = intro.add_run("Setup, folder structure, and end-to-end coding explained in build order.")
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


# ===== 1 =====
h1("1. What Are We Building?")
body(doc, "A small online book store with two front doors over the same data:")
make_table(
    doc,
    ["Door", "What it is", "Who uses it", "Lives in"],
    [
        ["REST API", "Returns JSON, uses a JWT token", "Mobile apps, Postman, programs", "app/routers/api/"],
        ["Web UI", "Returns HTML pages, uses a login cookie", "A human in a browser", "app/routers/web/"],
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
    "   |  Router  (the URL)    |  app/routers/...   'when someone hits /books, run this'",
    "   +-----------------------+",
    "   |  Schema  (the shape)  |  app/schemas.py    'the input must look like this'",
    "   +-----------------------+",
    "   |  Deps    (the guard)  |  app/deps.py       'are you logged in? are you admin?'",
    "   +-----------------------+",
    "   |  Model   (the table)  |  app/models.py     'this maps to a database table'",
    "   +-----------------------+",
    "   |  Database (the engine)|  app/database.py   'open/close the DB connection'",
    "   +-----------------------+",
    "              |",
    "              v",
    "            MySQL",
])
body(doc, "Supporting pieces every layer leans on:")
bullet(doc, "config.py — settings (DB password, secret key) read from a .env file.")
bullet(doc, "security.py — password hashing + JWT token creation.")
bullet(doc, "templating.py — turns data into HTML pages (web door only).")
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
    "    |-- config.py        settings loaded from .env",
    "    |-- database.py      SQLAlchemy engine + 'give me a DB session' helper",
    "    |-- models.py        (3) the database tables, as Python classes",
    "    |-- schemas.py       (4) the shape of API request bodies (validation)",
    "    |-- security.py      password hashing + JWT tokens",
    "    |-- deps.py          (5) guards: 'must be logged in / must be admin'",
    "    |-- templating.py    Jinja2 setup + flash messages + render() helper",
    "    |",
    "    |-- routers/         (6) the actual endpoints (the URLs)",
    "    |   |-- api/         JSON API  -> mounted under /api",
    "    |   |   |-- auth.py books.py cart.py wishlist.py",
    "    |   |   |-- address.py orders.py feedback.py",
    "    |   |-- web/         HTML pages -> mounted at /",
    "    |       |-- auth.py dashboard.py books.py cart.py wishlist.py",
    "    |       |-- address.py orders.py feedback.py users.py password.py",
    "    |",
    "    |-- templates/       (7) the HTML files (Jinja2), web door only",
    "    |   |-- base.html         shared layout (header, nav, CSS) - others extend it",
    "    |   |-- auth/  books/  cart/  ... etc.",
    "    |",
    "    |-- static/          files served as-is (uploaded book cover images)",
    "        |-- book-covers/",
])
body(doc, "The numbered files (1–7) are the order we build them in Section 6.", italic=True)

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
    ],
)

# ===== 6 =====
h1("6. Build It From Scratch — The Correct Order")
body(doc, "Write the files so each one only depends on things that already exist. "
          "This is exactly how you would build it yourself.")

h2("(1) config.py — settings first")
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

h2("(2) database.py — the connection")
body(doc, "Create the engine (pool of DB connections), a SessionLocal factory (each request "
          "gets its own short-lived session), and the Base class all models inherit from.")
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

h2("(3) models.py — the tables")
body(doc, "Each class = one table. Each mapped_column = one column. relationship() links tables "
          "(e.g. a User has many Books).")
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

h2("(4) security.py + schemas.py — protect and validate")
body(doc, "security.py does two jobs — hash passwords, and mint/read JWT tokens:")
code_block(doc, [
    "hash_password('secret1')          # -> '$2b$12$.....' stored in DB",
    "verify_password('secret1', hash)  # -> True / False at login",
    "",
    "create_access_token(user.id)   # login hands this to the client",
    "decode_access_token(token)     # every later request: who is this?",
])
body(doc, "schemas.py defines the shape of incoming API JSON with Pydantic. If the input doesn't "
          "match, FastAPI auto-rejects it with a 422 before your code runs.")
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

h2("(5) deps.py — the guards")
body(doc, "Dependencies are reusable checks you attach to endpoints. This file answers "
          "'who are you and are you allowed here?' — once, in one place.")
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

h2("(6) routers/ — the endpoints (the heart)")
body(doc, "Now you write the actual URLs. Each file is an APIRouter grouping related routes. "
          "Read this API example slowly — every line ties back to a layer you already built:")
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

h2("(7) templating.py + templates/ — the HTML (web door only)")
body(doc, "templating.py configures Jinja2 and gives you a render() helper that always injects "
          "the current user + any flash messages, so templates stay simple.")
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
    "for r in (api_auth, api_books, api_cart, ...):",
    "    app.include_router(r.router, prefix='/api')   # API door",
    "for r in (web_auth, web_dashboard, web_books, ...):",
    "    app.include_router(r.router)                  # web door",
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
numbered(doc, "Read in build order: config -> database -> models -> schemas -> security -> deps -> one router -> its template -> main. Don't start in main.py.")
numbered(doc, "Pick ONE feature and trace it end-to-end. Books is best — it has both API and web versions plus a template. Compare them: same data, two doors.")
numbered(doc, "Then change something small: add a 'genre' column (see below). Doing it once teaches more than reading ten times.")
body(doc, "Mini-exercise — add a genre to books:", bold=True)
bullet(doc, "Add the field in models.py.")
bullet(doc, "Add it to BookCreate in schemas.py.")
bullet(doc, "Read it in the router and pass it to Book(...).")
bullet(doc, "Show it in templates/books/index.html.")
bullet(doc, "Drop the table (or the DB) so create_all rebuilds it, and rerun.")

# ===== 9 =====
h1("9. Common Gotchas for Beginners")
bullet(doc, "'Table doesn't have my new column.' create_all only CREATES missing tables; it does NOT alter existing ones. While learning, drop the table and restart. (Real apps use migrations — e.g. Alembic.)")
bullet(doc, "Can't connect to MySQL. Is MySQL actually running? Do .env credentials match? Does book_store_product exist?")
bullet(doc, "401 on API calls. Log in (POST /api/login), copy access_token, send it as Authorization: Bearer <token>. In /docs click the Authorize button.")
bullet(doc, "Web pages bounce me to /login. The web door uses the session cookie, not the JWT. Log in through the web form.")
bullet(doc, "Never commit .env — it holds secrets. .env.example is the safe template.")

# ===== 10 =====
h1("10. Want Zero Setup? Use SQLite Instead of MySQL")
body(doc, "To learn without installing MySQL, point the app at a local file DB. In config.py change database_url to:")
code_block(doc, [
    "@property",
    "def database_url(self) -> str:",
    "    return 'sqlite:///./book_store.db'",
])
body(doc, "and in database.py add the SQLite-only arg:")
code_block(doc, [
    "engine = create_engine(settings.database_url,",
    "                       connect_args={'check_same_thread': False})",
])
body(doc, "Now python run.py creates a book_store.db file — no server needed. (The repo ships "
          "configured for MySQL to match the original Laravel app; SQLite is purely a learning convenience.)")

# ===== Summary =====
h1("One-Paragraph Summary")
body(doc, "You configure settings (config), open a database (database), describe tables as classes "
          "(models), validate inputs (schemas), hash passwords and mint tokens (security), guard "
          "endpoints (deps), write the URLs (routers), render HTML for humans "
          "(templates/templating), and bolt it all together (main). A request falls DOWN through "
          "router -> schema -> guard -> model -> DB, and the response climbs back UP. Master one "
          "feature's path and you've mastered them all.", italic=True)

out = "Book_Store_FastAPI_Learning_Guide.docx"
doc.save(out)
print("Saved:", out)
