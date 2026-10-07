"""Generate a Google-Docs-ready .docx documenting the Business Central RAG
chatbot from scratch: what it is, everything you need, how to set it up, and the
actual code module by module (client -> vector store -> service -> routes).

This is the second chatbot in the app (independent of the LangChain "BookBot").
It ingests Microsoft Dynamics 365 Business Central records into a Qdrant vector
database and answers questions grounded in those vectors (classic RAG).

Run:  python build_bc_doc.py
Output: Book_Store_FastAPI_BC_Chatbot_From_Scratch.docx
"""

from docx import Document
from docx.shared import Pt, RGBColor
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
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(11)


def h1(text):
    h = doc.add_heading(text, level=1)
    for run in h.runs:
        run.font.color.rgb = DARK


def h2(text):
    h = doc.add_heading(text, level=2)
    for run in h.runs:
        run.font.color.rgb = INDIGO


# ---- Title ----
title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = title.add_run("Book Store (FastAPI)")
r.bold = True
r.font.size = Pt(26)
r.font.color.rgb = DARK
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
rs = sub.add_run("Business Central RAG Chatbot — Build From Scratch")
rs.font.size = Pt(14)
rs.font.color.rgb = INDIGO
intro = doc.add_paragraph()
intro.alignment = WD_ALIGN_PARAGRAPH.CENTER
ri = intro.add_run("A second, self-contained chatbot: ingest Microsoft Dynamics 365 Business "
                   "Central records into a Qdrant vector DB and answer questions grounded in "
                   "those vectors. What you need, how to set it up, and the actual code.")
ri.italic = True
ri.font.size = Pt(10.5)
ri.font.color.rgb = GREY
doc.add_paragraph()


# ===== 1 =====
h1("1. What This Is")
body(doc, "The app already ships one chatbot (BookBot, a LangChain agent over the book catalogue). "
          "This is a completely separate, second chatbot that answers questions about your Microsoft "
          "Dynamics 365 Business Central (BC) data — items, customers, sales orders, ledger entries, "
          "or any published entity — using Retrieval-Augmented Generation (RAG).")
body(doc, "RAG means the bot never guesses. It first retrieves the records most similar to your "
          "question from a vector database, then asks the LLM to answer using ONLY those records. So "
          "figures come from your real BC data, not the model's imagination.")
body(doc, "It lives entirely under app/bc/ and is independent of BookBot: its own client, its own "
          "vector store, its own routes. It reuses only two shared services — the local embedding "
          "model and the switchable LLM (Groq/Anthropic) — so it needs no new AI keys beyond what the "
          "rest of the app already uses.")
make_table(
    doc,
    ["Surface", "Web page / API", "Who", "What it does"],
    [
        ["Chat (web)", "GET/POST /bc/chat", "any signed-in user", "ask a question, get a grounded answer"],
        ["Chat (API)", "POST /api/bc/chat", "any signed-in user", "same, as JSON (JWT)"],
        ["Sync (web)", "POST /bc/sync", "admin only", "'Sync now' button — ingest BC into Qdrant"],
        ["Sync (API)", "POST /api/bc/sync", "admin only", "ingest, as JSON (JWT)"],
        ["Status", "GET /api/bc/status", "any signed-in user", "config + how many vectors indexed"],
        ["Suggestions", "GET /bc/suggestions", "any signed-in user", "content-aware example questions"],
    ],
)


# ===== 2 =====
h1("2. How It Works (Two Phases)")
body(doc, "The chatbot has exactly two operations, mirroring the two things a RAG system does:")
h2("Phase A — Sync (ingest), the 'Sync now' button")
numbered(doc, "Fetch records from Business Central (or bundled sample data if unconfigured).")
numbered(doc, "Flatten EVERY field of each record into a 'Field: value' text blob.")
numbered(doc, "Embed each blob into a 384-dimension vector with the local model.")
numbered(doc, "Upsert (id, vector, payload) into the Qdrant collection. Deterministic ids mean "
              "re-syncing updates records in place instead of duplicating.")
h2("Phase B — Chat (query), every question")
numbered(doc, "Embed the user's question into a vector with the same local model.")
numbered(doc, "Search Qdrant for the top-K most similar record vectors (cosine distance).")
numbered(doc, "Build a CONTEXT block from those records and ask the LLM to answer using ONLY it.")
numbered(doc, "If no LLM key is set, return the retrieved records directly (still useful).")
code_block(doc, [
    "  SYNC:  BC API ──▶ flatten fields ──▶ embed (local) ──▶ Qdrant upsert",
    "",
    "  CHAT:  question ──▶ embed (local) ──▶ Qdrant search ──▶ top-K records",
    "                                                    │",
    "                             LLM answers using ONLY those records ◀─┘",
])


# ===== 3 =====
h1("3. What You Need")
make_table(
    doc,
    ["Component", "Purpose", "Cost / key"],
    [
        ["Python packages", "qdrant-client, fastembed, httpx (+ the app's stack)", "free"],
        ["Embedding model", "all-MiniLM-L6-v2, runs locally (ONNX via fastembed)", "free, no key, offline"],
        ["Qdrant", "vector database (embedded folder OR Docker server)", "free"],
        ["LLM provider", "Groq (default, free) or Anthropic Claude (paid)", "Groq free key"],
        ["Business Central", "the data source (Azure AD app, client-credentials)", "optional — sample fallback"],
    ],
)
body(doc, "Key point: you can build and test the ENTIRE pipeline for free and without a Business "
          "Central subscription. Leave the BC_* keys blank and the ingest uses bundled sample data "
          "(items / customers / sales orders). Add real BC credentials later and nothing else "
          "changes.", italic=True)


# ===== 4 =====
h1("4. Step-by-Step Setup")

h2("Step 4.1 — Install dependencies")
body(doc, "Three packages power this feature (on top of the app's existing FastAPI stack). fastembed "
          "is preferred over sentence-transformers because its ONNX runtime works under Windows Smart "
          "App Control, which blocks the PyTorch DLLs sentence-transformers needs.")
code_block(doc, [
    "# requirements.txt (relevant lines)",
    "httpx==0.28.1                  # BC REST/OData calls + LLM calls",
    "fastembed==0.8.0               # local embeddings via ONNX (preferred)",
    "sentence-transformers==3.3.1   # fallback embedding backend (PyTorch)",
    "qdrant-client==1.12.1          # vector DB client (embedded or server)",
    "",
    "pip install -r requirements.txt",
])

h2("Step 4.2 — Choose how to run Qdrant")
body(doc, "There are two modes. The app picks EMBEDDED when QDRANT_PATH is set (the default), else it "
          "connects to the QDRANT_URL server.")
make_table(
    doc,
    ["Mode", "When", "Setup", "Trade-off"],
    [
        ["Embedded", "single-process dev (default)", "just set QDRANT_PATH to a writable folder",
         "ONE process only — exclusive folder lock"],
        ["Server", "reload / multiple workers / prod", "blank QDRANT_PATH; run Docker; set QDRANT_URL",
         "needs Docker, allows concurrent clients"],
    ],
)
body(doc, "Embedded is zero-setup and the default. Its one rule: only a single process may open the "
          "folder at a time (it takes an exclusive .lock). If a second process opens the same path you "
          "get 'Storage folder ... is already accessed by another instance'. For a server instead:")
code_block(doc, [
    "# Option A — embedded (default): nothing to run, just a writable folder",
    "QDRANT_PATH=./qdrant_storage",
    "",
    "# Option B — server: blank the path, run Docker, point at the URL",
    "docker run -p 6333:6333 -v \"%cd%/qdrant_storage:/qdrant/storage\" qdrant/qdrant",
    "#   .env:  QDRANT_PATH=            (blank)",
    "#          QDRANT_URL=http://localhost:6333",
])

h2("Step 4.3 — Pick the LLM backend (free by default)")
body(doc, "The chatbot reuses the app's switchable LLM. AI_PROVIDER=groq (default) is free — get a key "
          "at console.groq.com/keys (starts with gsk_). Set AI_PROVIDER=anthropic to use Claude "
          "instead. With NO key, chat still works: it returns the retrieved BC records directly "
          "without an LLM summary.")
code_block(doc, [
    "AI_PROVIDER=groq",
    "GROQ_API_KEY=gsk_your_key_here",
    "GROQ_MODEL=llama-3.3-70b-versatile",
])

h2("Step 4.4 — (Optional) Register an Azure AD app for live BC data")
body(doc, "Skip this to test with sample data. For real BC data, Business Central uses Azure AD OAuth2 "
          "client-credentials (app-to-app, no user login):")
numbered(doc, "In the Azure portal -> Microsoft Entra ID -> App registrations -> New registration.")
numbered(doc, "Copy the Application (client) ID and the Directory (tenant) ID.")
numbered(doc, "Certificates & secrets -> New client secret -> copy the secret VALUE.")
numbered(doc, "API permissions -> add Dynamics 365 Business Central (Application permission, e.g. "
              "API.ReadWrite.All) -> Grant admin consent.")
numbered(doc, "In Business Central, under Azure AD Applications, add the client id and set its state "
              "to Enabled with the needed permission set.")

h2("Step 4.5 — Configure .env")
body(doc, "Fill the BC + Qdrant block. Two data-access styles are supported — choose one with "
          "BC_API_STYLE:")
bullet(doc, "api   -> standard REST API. BC_COMPANY is a display name (blank = first company); "
            "BC_ENTITIES are standard entities: items, customers, salesOrders, ...")
bullet(doc, "odata -> OData V4 published web services / pages. BC_COMPANY is the exact company name "
            "(required); BC_ENTITIES are your published service names, e.g. Item_Ledger_Entries_Excel.")
code_block(doc, [
    "# ---- Business Central ----",
    "BC_TENANT_ID=<azure-tenant-guid>",
    "BC_CLIENT_ID=<azure-app-client-id>",
    "BC_CLIENT_SECRET=<client-secret-value>",
    "BC_ENVIRONMENT=Production            # your BC environment name",
    "BC_MAX_RECORDS=50000                 # cap pulled per entity (paged internally)",
    "BC_API_STYLE=odata                   # 'api' | 'odata'",
    "BC_COMPANY=KisanKraft Limited        # display name (api) or exact name (odata)",
    "BC_ENTITIES=Item_Ledger_Entries_Excel",
    "BC_ODATA_FILTER=Posting_Date ge 2026-01-01   # optional raw OData $filter",
    "",
    "# ---- Qdrant ----",
    "QDRANT_PATH=./qdrant_storage         # embedded; blank to use a server",
    "QDRANT_URL=http://localhost:6333",
    "QDRANT_API_KEY=",
    "QDRANT_COLLECTION=business_central",
])
body(doc, "Leave BC_TENANT_ID / BC_CLIENT_ID / BC_CLIENT_SECRET blank to run against sample data "
          "(the pipeline is identical; only the source changes).", italic=True)

h2("Step 4.6 — Run, then sync")
code_block(doc, [
    "python run.py                 # http://127.0.0.1:8000",
    "# 1) log in as an ADMIN user",
    "# 2) open /bc/chat  and click 'Sync now'  (ingests BC -> Qdrant)",
    "# 3) ask a question, e.g. 'How many item ledger entries this year?'",
])


# ===== 5 =====
h1("5. Build From Scratch — The Code")
body(doc, "The feature is five modules under app/bc/, plus a settings block and route registration. "
          "Build them in this order: config -> client (+ sample_data) -> vector store -> service -> "
          "routes.")

h2("5.1 — Settings (app/core/config.py)")
body(doc, "Add the BC and Qdrant fields with safe defaults, plus two helper properties. Defaults mean "
          "the app still boots with the feature simply idle if nothing is configured.")
code_block(doc, [
    "class Settings(BaseSettings):",
    "    # Business Central (Azure AD client-credentials)",
    "    bc_tenant_id: str = ''",
    "    bc_client_id: str = ''",
    "    bc_client_secret: str = ''",
    "    bc_environment: str = 'Production'",
    "    bc_company: str = ''",
    "    bc_login_base: str = 'https://login.microsoftonline.com'",
    "    bc_api_base: str = 'https://api.businesscentral.dynamics.com/v2.0'",
    "    bc_scope: str = 'https://api.businesscentral.dynamics.com/.default'",
    "    bc_max_records: int = 500",
    "    bc_api_style: str = 'api'        # 'api' | 'odata'",
    "    bc_entities: str = 'items,customers,salesOrders'",
    "    bc_odata_filter: str = ''",
    "    # Qdrant",
    "    qdrant_path: str = './qdrant_storage'   # embedded; blank -> use server",
    "    qdrant_url: str = 'http://localhost:6333'",
    "    qdrant_api_key: str = ''",
    "    qdrant_collection: str = 'business_central'",
    "",
    "    @property",
    "    def bc_configured(self) -> bool:      # real creds present?",
    "        return bool(self.bc_tenant_id and self.bc_client_id and self.bc_client_secret)",
    "",
    "    @property",
    "    def bc_entity_list(self) -> list[str]:",
    "        return [e.strip() for e in self.bc_entities.split(',') if e.strip()]",
])

h2("5.2 — BC client (app/bc/client.py): auth, fetch, paging, retry")
body(doc, "Talks to Business Central with plain httpx (no SDK). Three responsibilities: get an OAuth2 "
          "token, build the right URL for the chosen API style, and fetch records resiliently. When "
          "creds are absent OR a live call fails, it falls back to sample data so the pipeline still "
          "runs.")
body(doc, "Auth — Azure AD client-credentials, token cached until shortly before expiry:")
code_block(doc, [
    "def _access_token(self) -> str:",
    "    now = time.time()",
    "    if self._token and now < self._token_expiry - 60:",
    "        return self._token",
    "    url = f'{settings.bc_login_base}/{settings.bc_tenant_id}/oauth2/v2.0/token'",
    "    resp = httpx.post(url, data={",
    "        'grant_type': 'client_credentials',",
    "        'client_id': settings.bc_client_id,",
    "        'client_secret': settings.bc_client_secret,",
    "        'scope': settings.bc_scope}, timeout=60)",
    "    data = resp.json()",
    "    self._token = data['access_token']",
    "    self._token_expiry = now + float(data.get('expires_in', 3600))",
    "    return self._token",
])
body(doc, "URL building — the two API styles differ in how the company and entity are addressed:")
code_block(doc, [
    "def _entity_url(self, entity: str) -> str:",
    "    if settings.bc_api_style.lower() == 'odata':",
    "        # OData V4 web services: company by NAME, entity = web service name",
    "        company = quote(settings.bc_company.replace(\"'\", \"''\"), safe='')",
    "        return f\"{self._odata_root}/Company('{company}')/{entity}\"",
    "    # standard REST API: company by GUID, entity = standard entity",
    "    return f'{self._api_root}/companies({self._company_guid()})/{entity}'",
])
body(doc, "Fetch with retry + windowed paging — this is what makes a large pull reliable. A single "
          "50,000-row OData response is a big, slow chunked stream that BC often cuts off mid-body "
          "('peer closed connection without sending complete message body'). Two defences:")
bullet(doc, "Retry: transient network errors (RemoteProtocolError / timeouts / resets) are retried a "
            "few times with backoff before giving up.")
bullet(doc, "Windowed paging: fetch in bounded $top + $skip windows (e.g. 5000 rows) instead of asking "
            "for everything at once, so each response is small enough to complete. The max-records cap "
            "also bounds the loop, so it always terminates.")
code_block(doc, [
    "_RETRY_ATTEMPTS = 3",
    "_RETRY_BACKOFF = 1.5   # seconds, * attempt number",
    "_PAGE_SIZE = 5000      # rows per request window",
    "",
    "def _get_with_retry(self, url, params, entity) -> httpx.Response:",
    "    last_exc = None",
    "    for attempt in range(_RETRY_ATTEMPTS):",
    "        try:",
    "            return httpx.get(url, headers=self._headers(), params=params, timeout=90)",
    "        except (httpx.TransportError, httpx.RemoteProtocolError) as exc:",
    "            last_exc = exc                       # transient -> back off & retry",
    "            if attempt < _RETRY_ATTEMPTS - 1:",
    "                time.sleep(_RETRY_BACKOFF * (attempt + 1)); continue",
    "        except httpx.HTTPError as exc:",
    "            raise BusinessCentralError(f'BC {entity} request failed: {exc}')",
    "    raise BusinessCentralError(",
    "        f'BC {entity} request failed after {_RETRY_ATTEMPTS} attempts: {last_exc}')",
    "",
    "def _fetch_live(self, entity, max_records) -> list[dict]:",
    "    base_url = self._entity_url(entity)",
    "    is_odata = settings.bc_api_style.lower() == 'odata'",
    "    records = []",
    "    while len(records) < max_records:",
    "        top = min(_PAGE_SIZE, max_records - len(records))",
    "        params = {'$top': top, '$skip': len(records)}",
    "        if is_odata and settings.bc_odata_filter:",
    "            params['$filter'] = settings.bc_odata_filter",
    "        resp = self._get_with_retry(base_url, params, entity)",
    "        batch = resp.json().get('value') or []",
    "        if not batch: break                      # no more rows",
    "        records.extend(batch)",
    "        if len(batch) < top: break               # short page -> end of data",
    "    return records[:max_records]",
])
body(doc, "The public fetch() wraps this and decides source vs fallback:")
code_block(doc, [
    "def fetch(self, entity, max_records=None) -> tuple[list[dict], str, str | None]:",
    "    limit = max_records or settings.bc_max_records",
    "    error = None",
    "    if self.configured:",
    "        try:",
    "            recs = self._fetch_live(entity, limit)",
    "            return [_clean(r) for r in recs], 'live', None",
    "        except BusinessCentralError as exc:",
    "            error = str(exc)          # keep the reason, fall back to sample",
    "    return [_clean(r) for r in sample_records(entity)][:limit], 'sample', error",
])

h2("5.3 — Sample data (app/bc/sample_data.py)")
body(doc, "A dict of bundled records keyed by BC entity name, so the whole pipeline is testable with no "
          "subscription. Mimics the JSON shape the real API returns.")
code_block(doc, [
    "SAMPLE_DATA = {",
    "    'items':      _ITEMS,       # number, displayName, unitPrice, inventory, ...",
    "    'customers':  _CUSTOMERS,   # number, displayName, city, balanceDue, ...",
    "    'salesOrders':_SALES_ORDERS,# number, customerName, quantity, status, ...",
    "}",
    "",
    "def sample_records(entity: str) -> list[dict]:",
    "    return SAMPLE_DATA.get(entity, [])   # empty list if no sample for this entity",
])

h2("5.4 — Vector store (app/bc/vectorstore.py): the Qdrant wrapper")
body(doc, "A thin layer over qdrant-client so the rest of the app never imports Qdrant directly, and "
          "everything degrades gracefully when it's missing. The client is created lazily: embedded "
          "when QDRANT_PATH is set, else a server connection. Cosine distance matches the normalised "
          "vectors from the embedding model.")
code_block(doc, [
    "def _connect(self):",
    "    from qdrant_client import QdrantClient",
    "    if settings.qdrant_path:",
    "        return QdrantClient(path=settings.qdrant_path)      # embedded",
    "    return QdrantClient(url=settings.qdrant_url,",
    "                        api_key=settings.qdrant_api_key or None, timeout=30)",
    "",
    "@property",
    "def available(self) -> bool:        # importable AND server/folder responds",
    "    client = self._connect()",
    "    if client is None: return False",
    "    try: client.get_collections(); return True",
    "    except Exception: return False",
    "",
    "def ensure_collection(self, dim: int) -> None:",
    "    from qdrant_client.models import Distance, VectorParams",
    "    if not self._require().collection_exists(settings.qdrant_collection):",
    "        self._require().create_collection(settings.qdrant_collection,",
    "            vectors_config=VectorParams(size=dim, distance=Distance.COSINE))",
    "",
    "def upsert(self, points) -> int:    # (id, vector, payload) tuples",
    "    structs = [PointStruct(id=i, vector=v, payload=p) for i, v, p in points]",
    "    self._require().upsert(settings.qdrant_collection, points=structs)",
    "    return len(structs)",
    "",
    "def search(self, vector, top_k=8) -> list[dict]:   # nearest payloads + score",
    "    hits = self._require().search(settings.qdrant_collection,",
    "        query_vector=vector, limit=top_k, with_payload=True)",
    "    return [ {**h.payload, '_score': round(h.score, 4)} for h in hits ]",
])
body(doc, "Deterministic point ids make re-syncing idempotent (update in place, no duplicates):")
code_block(doc, [
    "_NAMESPACE = uuid.UUID('6f9619ff-8b86-d011-b42d-00c04fc964ff')",
    "def point_id(entity: str, key: str) -> str:",
    "    return str(uuid.uuid5(_NAMESPACE, f'{entity}:{key}'))",
])

h2("5.5 — Service (app/bc/service.py): sync + rag_chat")
body(doc, "The reasoning layer. sync() runs the ingest pipeline; rag_chat() runs the query pipeline. "
          "Both guard on prerequisites (embeddings + Qdrant reachable) and return friendly messages "
          "instead of crashing.")
body(doc, "Flatten every field to embeddable text — the entity name is included as a header so a query "
          "like 'sales order' retrieves the right kind of record:")
code_block(doc, [
    "def record_to_text(entity: str, record: dict) -> str:",
    "    lines = [f'Business Central {entity} record:']",
    "    for field, value in record.items():",
    "        if value in (None, ''): continue",
    "        if isinstance(value, (dict, list)): value = str(value)",
    "        lines.append(f'{field[0].upper()+field[1:]}: {value}')",
    "    return '\\n'.join(lines)",
])
body(doc, "sync() — fetch, embed, upsert; report source and any live-fetch error per entity. Note the "
          "honest fallback: if live fails AND there's no sample for that entity, it skips the upsert "
          "and says so, rather than reporting a misleading '0 records (sample)':")
code_block(doc, [
    "def sync(claude, client, store) -> dict:",
    "    if not claude.embeddings_enabled: return {'ok': False, 'error': 'Embeddings unavailable.'}",
    "    if not store.available:           return {'ok': False, 'error': 'Qdrant not reachable.'}",
    "    dim = len(claude.embed('dimension probe'))   # 384",
    "    store.ensure_collection(dim)",
    "    per_entity, errors, total = [], [], 0",
    "    for entity in settings.bc_entity_list:",
    "        records, source, error = client.fetch(entity)",
    "        if error:",
    "            errors.append(f'{entity}: {error}')",
    "            if not records:            # no sample for this entity -> don't fake it",
    "                per_entity.append({'entity': entity, 'records': 0,",
    "                                   'source': source, 'error': error}); continue",
    "        points = []",
    "        for i, record in enumerate(records):",
    "            text = record_to_text(entity, record)",
    "            vector = claude.embed(text)",
    "            key = _record_key(entity, record, i)",
    "            payload = {'entity': entity, 'key': key, 'text': text, 'source': source, **record}",
    "            points.append((point_id(entity, key), vector, payload))",
    "        total += store.upsert(points)",
    "        per_entity.append({'entity': entity, 'records': len(points), 'source': source})",
    "    return {'ok': True, 'total': total, 'entities': per_entity,",
    "            'collection': settings.qdrant_collection}",
])
body(doc, "rag_chat() — embed the question, retrieve top-K, answer using ONLY that context:")
code_block(doc, [
    "def rag_chat(claude, store, message, top_k=8) -> str:",
    "    if not store.available: return 'The vector database is not reachable...'",
    "    query_vec = claude.embed(message)",
    "    matches = store.search(query_vec, top_k=top_k)",
    "    if not matches: return \"I don't have any BC data indexed yet. Click 'Sync now'.\"",
    "    context = '\\n\\n'.join(f'[{i+1}] {m.get(\"text\", \"\")}' for i, m in enumerate(matches))",
    "    system = _SYSTEM + '\\n\\nCONTEXT:\\n' + context   # 'answer using ONLY these records'",
    "    if not claude.enabled:            # no LLM key -> return the records themselves",
    "        return 'No LLM configured; here are the most relevant records:\\n\\n' + context",
    "    return claude.ask(message, system, max_tokens=700).strip()",
])
body(doc, "The system prompt is the guardrail: 'Answer using ONLY the CONTEXT records... quote concrete "
          "values... if the context does not contain the answer, say so plainly — never invent "
          "figures.' That is what stops the bot hallucinating numbers.", italic=True)

h2("5.6 — Routes (app/bc/api.py + app/bc/web.py) and schema")
body(doc, "Thin controllers — all logic is in the service. Chat/status/suggestions are open to any "
          "signed-in user; sync is admin-only. The API uses JWT bearer auth; the web UI uses the "
          "session. Both call the exact same service functions.")
code_block(doc, [
    "# app/bc/schemas.py",
    "class BCChatRequest(BaseModel):",
    "    message: str = Field(min_length=1, max_length=1000)",
    "",
    "# app/bc/api.py   (JWT, mounted under /api)",
    "router = APIRouter(prefix='/bc', tags=['business-central'])",
    "",
    "@router.post('/sync')",
    "def bc_sync(_: User = Depends(require_api_role('admin')), claude=..., client=..., store=...):",
    "    return {'status': 200, 'result': service.sync(claude, client, store)}",
    "",
    "@router.post('/chat')",
    "def bc_chat(payload: BCChatRequest, _: User = Depends(get_current_api_user), ...):",
    "    return {'status': 200, 'reply': service.rag_chat(claude, store, payload.message)}",
    "",
    "# app/bc/web.py   (session, mounted at root)",
    "router = APIRouter(prefix='/bc', tags=['web-business-central'])",
    "admin_role = require_web_role('admin')",
    "",
    "@router.post('/sync')",
    "def sync_now(user: User = Depends(admin_role), ...):",
    "    return JSONResponse({'result': service.sync(claude, client, store)})",
])
body(doc, "Register both routers in app/main.py: API routers get the '/api' prefix, web routers are "
          "mounted at the root.")
code_block(doc, [
    "# app/main.py",
    "from app.bc import api as bc_api, web as bc_web",
    "app.include_router(bc_api.router, prefix='/api')   # -> /api/bc/*",
    "app.include_router(bc_web.router)                  # -> /bc/*",
])


# ===== 6 =====
h1("6. The Shared Embedding Model")
body(doc, "Both phases embed text with a local model — no API, no key, runs offline. It's shared with "
          "the app's semantic-search feature via ClaudeService. all-MiniLM-L6-v2 produces 384-D "
          "normalised vectors (hence cosine distance in Qdrant).")
body(doc, "Two backends, tried in order, so it works across environments:")
bullet(doc, "fastembed (ONNX runtime) — preferred. Microsoft-signed DLLs, so it runs under Windows "
            "Smart App Control, which blocks PyTorch.")
bullet(doc, "sentence-transformers (PyTorch) — fallback when fastembed isn't available and torch DLLs "
            "can load.")
code_block(doc, [
    "# app/core/ai.py (embedding, simplified)",
    "_EMBED_MODEL_NAME_FASTEMBED = 'sentence-transformers/all-MiniLM-L6-v2'",
    "def embed(self, text: str) -> list[float]:",
    "    # lazily load fastembed; else sentence-transformers; else raise AIError",
    "    if self._embed_backend == 'fastembed':",
    "        return list(next(iter(self._embed_model.embed([text]))))   # 384 floats",
])


# ===== 7 =====
h1("7. Graceful Degradation & Troubleshooting")
make_table(
    doc,
    ["Situation", "Behaviour / fix"],
    [
        ["No BC credentials", "Ingest uses bundled sample data (source='sample')"],
        ["qdrant-client not installed", "available=False; UI shows a 'pip install qdrant-client' hint"],
        ["No LLM key set", "Chat returns the retrieved records directly (no summary)"],
        ["Embeddings package missing", "Sync/chat report 'install fastembed'; app still runs"],
        ["Live fetch drops mid-stream", "Retried up to 3x with backoff; then per-entity error surfaced"],
        ["Big pull ('incomplete chunked read')", "Fixed by 5000-row windowed paging (Sec 5.2)"],
    ],
)
h2("Common Qdrant errors")
body(doc, "'Storage folder ... is already accessed by another instance' — embedded mode allows only "
          "ONE process. This happens if you run uvicorn with --reload spawning extra workers, or a "
          "second script opens the same folder, or a crashed process left a stale .lock. Fix: run a "
          "single process, delete a stale qdrant_storage/.lock, or switch to server mode.")
body(doc, "'Qdrant is not reachable' on sync — in embedded mode ensure QDRANT_PATH is set and the "
          "folder is writable; in server mode make sure Docker is running and QDRANT_URL is correct.")


# ===== 8 =====
h1("8. Security & Operational Notes")
bullet(doc, "Secrets (BC client secret, Groq/Anthropic keys, Qdrant API key) live only in .env, never "
            "in git. .env.example is the template.")
bullet(doc, "BC auth is app-to-app (client-credentials) — no user passwords involved. The token is "
            "cached in memory and refreshed before expiry.")
bullet(doc, "Sync is admin-only (require_api_role('admin') / require_web_role('admin')); chat is open "
            "to any signed-in user.")
bullet(doc, "The LLM only ever sees retrieved record text, never a database connection — and it is "
            "instructed to answer strictly from that context, so it cannot invent figures.")
bullet(doc, "Re-syncing is safe and idempotent: deterministic point ids update records in place. A "
            "failed live fetch upserts nothing, so a previous good index is never wiped.")
bullet(doc, "Embedding a large pull is CPU-bound (local ONNX). Tens of thousands of rows can take "
            "minutes; sync embeds everything, then upserts once, so the indexed count jumps at the end.")


# ===== 9 =====
h1("9. Verification Checklist")
bullet(doc, "GET /api/bc/status returns qdrant_available=true, embeddings_enabled=true, and an "
            "'indexed' count.")
bullet(doc, "Sample path: with BC_* blank, 'Sync now' indexes the bundled items/customers/salesOrders.")
bullet(doc, "Live path: with real creds, sync reports source='live' and the fetched record count.")
bullet(doc, "Chat grounds answers: ask about a value you know is in the data and confirm the figure "
            "matches; ask about something absent and confirm it says it doesn't have that.")
code_block(doc, [
    "# mint an admin token and drive the API directly (no browser)",
    "TOKEN=$(python -c \"from app.core.security import create_access_token; print(create_access_token(<admin_id>))\")",
    "curl -H \"Authorization: Bearer $TOKEN\" http://localhost:8000/api/bc/status",
    "curl -X POST -H \"Authorization: Bearer $TOKEN\" http://localhost:8000/api/bc/sync",
    "curl -X POST -H \"Authorization: Bearer $TOKEN\" -H 'Content-Type: application/json' \\",
    "     -d '{\"message\":\"how many item ledger entries?\"}' http://localhost:8000/api/bc/chat",
])


# ===== Summary =====
h1("One-Paragraph Summary")
body(doc, "The Business Central chatbot (app/bc/) is a RAG system in five modules. sync() pulls BC "
          "records via OAuth2 client-credentials (client.py, with retry + 5000-row windowed paging for "
          "reliability), flattens every field to text, embeds it with a local 384-D model, and upserts "
          "the vectors into Qdrant (vectorstore.py). rag_chat() embeds the question, retrieves the "
          "top-K nearest records, and asks the switchable LLM (Groq free / Anthropic) to answer using "
          "ONLY those records. Qdrant runs embedded (a writable folder, single-process) or as a Docker "
          "server (for reload/multi-worker). Everything degrades gracefully: no BC creds -> sample "
          "data, no LLM key -> raw records, no Qdrant -> a clear message. Setup: pip install, choose "
          "Qdrant mode, set an LLM key, (optionally) register an Azure AD app and fill BC_*/QDRANT_* in "
          ".env, run, log in as admin, click 'Sync now', ask.", italic=True)

out = "Book_Store_FastAPI_BC_Chatbot_From_Scratch.docx"
doc.save(out)
print("Saved:", out)
