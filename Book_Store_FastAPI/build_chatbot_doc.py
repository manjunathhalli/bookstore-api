"""Generate a Google-Docs-ready .docx documenting the AI Chatbot upgrade:
from manual RAG to a LangChain tool-calling agent, with a free live-weather
tool (Open-Meteo) and a switchable, free-by-default LLM backend (Groq).

Run:  python build_chatbot_doc.py
Output: Book_Store_FastAPI_Chatbot_LangChain.docx
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
rs = sub.add_run("AI Chatbot Upgrade — LangChain Agent + Free Live-Weather Tool")
rs.font.size = Pt(14)
rs.font.color.rgb = INDIGO
intro = doc.add_paragraph()
intro.alignment = WD_ALIGN_PARAGRAPH.CENTER
ri = intro.add_run("How Feature 5 went from manual RAG to a tool-calling agent — free to run, "
                   "with step-by-step setup and the actual code.")
ri.italic = True
ri.font.size = Pt(10.5)
ri.font.color.rgb = GREY
doc.add_paragraph()


# ===== 1 =====
h1("1. Overview — What Changed and Why")
body(doc, "The AI chatbot (Feature 5) originally used manual Retrieval-Augmented Generation (RAG): "
          "the code searched the catalogue, pasted results into a prompt, and called the model. To "
          "answer weather questions we added a hardcoded keyword check. That 'if weather-word else "
          "RAG' branch was brittle — phrasings like 'is it sunny in Paris?' slipped through.")
body(doc, "This upgrade ADDS a LangChain tool-calling AGENT as a new, separate chatbot. We register "
          "our functions as tools; the LLM itself decides which tool to call for each message, and "
          "can even chain several in one turn. Two design goals shaped it:")
body(doc, "The original RAG chatbot is KEPT as its own feature (5b) — nothing was removed. So the "
          "store now offers two independent bots from the AI hub: the classic RAG bot at "
          "/ai/rag-chat (service.rag_chat_reply, Claude over retrieved context) and the LangChain "
          "agent at /ai/chat (service.chat_reply). This document covers the agent (5a); the RAG bot "
          "is the same implementation described in the main AI Features guide.")
bullet(doc, "Free to run for testing — the weather tool uses a key-less public API (Open-Meteo), "
            "and the default LLM backend is Groq's free tool-calling tier.")
bullet(doc, "Switchable — one setting (AI_PROVIDER) flips the agent's LLM between free Groq and "
            "paid Anthropic Claude, with no code changes.")
make_table(
    doc,
    ["Concern", "Before (manual RAG)", "After (LangChain agent)"],
    [
        ["Intent routing", "hardcoded is_weather_query() if/else", "the LLM picks the tool"],
        ["Weather", "keyword branch -> weather_answer()", "`weather` tool (live, key-less)"],
        ["Book search", "inline SQL in chat_reply", "`search_catalog` tool"],
        ["Orders", "_order_context() string", "`my_orders` tool (own orders only)"],
        ["Multi-step", "not possible", "agent can call several tools per turn"],
        ["LLM backend", "Anthropic only", "switchable: Groq (free) / Anthropic"],
        ["Availability", "the only chatbot", "added alongside; RAG kept as feature 5b"],
    ],
)
make_table(
    doc,
    ["Chatbot", "Web page", "JWT API", "Backend"],
    [
        ["5a — LangChain agent", "/ai/chat", "POST /api/ai/chat", "Groq (free) / Anthropic"],
        ["5b — Classic RAG", "/ai/rag-chat", "POST /api/ai/chat-rag", "Anthropic Claude"],
    ],
)


# ===== 2 =====
h1("2. The Free APIs Used")
h2("Open-Meteo (weather) — no API key")
body(doc, "Open-Meteo is free for non-commercial use and needs NO key, so the weather tool works "
          "out of the box. Two public endpoints are used: a Geocoding API (city name -> "
          "latitude/longitude) and a Forecast API (current conditions at those coordinates).")
h2("Groq (LLM) — free tool-calling")
body(doc, "A LangChain agent needs an LLM that supports tool-calling, so it cannot run fully "
          "key-less like the weather tool. Groq offers a free API key and an OpenAI-compatible, "
          "tool-calling endpoint (llama-3.3-70b). It is the default backend; Anthropic Claude is an "
          "optional paid alternative.")


# ===== 3 =====
h1("3. Step-by-Step Setup")
h2("Step 3.1 — Install dependencies")
body(doc, "The upgrade adds three packages to requirements.txt (LangChain plus the two LLM "
          "bindings). Install them into your virtual environment:")
code_block(doc, [
    "# requirements.txt (added)",
    "langchain==0.3.14",
    "langchain-groq==0.2.3          # free tool-calling backend (default)",
    "langchain-anthropic==0.3.1     # optional paid backend",
    "",
    "pip install -r requirements.txt",
])
h2("Step 3.2 — Get a free Groq API key")
numbered(doc, "Go to https://console.groq.com and sign up (free).")
numbered(doc, "Open https://console.groq.com/keys and click 'Create API Key'.")
numbered(doc, "Copy the key (starts with gsk_). It is shown once.")
h2("Step 3.3 — Configure .env")
body(doc, "Copy from .env.example and set the chatbot block. AI_PROVIDER selects the LLM; leave it "
          "as 'groq' for the free path:")
code_block(doc, [
    "# ---- Chatbot agent (LangChain, Feature 5) ----",
    "AI_PROVIDER=groq",
    "GROQ_API_KEY=gsk_your_key_here",
    "GROQ_MODEL=llama-3.3-70b-versatile",
])
body(doc, "To use Claude instead, set AI_PROVIDER=anthropic and fill ANTHROPIC_API_KEY (the agent "
          "reuses ANTHROPIC_MODEL). No code change needed.", italic=True)
h2("Step 3.4 — Settings registered in config")
body(doc, "app/core/config.py reads the new keys with safe defaults, so the app still boots with "
          "the chatbot simply disabled if no key is set:")
code_block(doc, [
    "# app/core/config.py (Settings)",
    "ai_provider: str = 'groq'          # 'groq' | 'anthropic'",
    "groq_api_key: str = ''",
    "groq_model: str = 'llama-3.3-70b-versatile'",
])
h2("Step 3.5 — Run and try it")
code_block(doc, [
    "python run.py            # or: uvicorn app.main:app --reload",
    "# open http://127.0.0.1:8000/ai/chat  and ask BookBot:",
    "#   'recommend a cheap thriller'                 -> search_catalog",
    "#   'what did I order?'                           -> my_orders",
    "#   'is it raining in Delhi?'                     -> weather",
    "#   'find a mystery and the weather in Tokyo'     -> two tools, one turn",
])


# ===== 4 =====
h1("4. The Weather Tool (app/core/weather.py)")
body(doc, "A self-contained, key-less integration with Open-Meteo. Everything is defensive: any "
          "network/parse problem returns None so the caller degrades gracefully. Four pieces:")
h2("4.1 — Intent detection & city extraction")
body(doc, "A word-boundary regex over common weather words decides if a message is a weather "
          "question; a second regex pulls the city after in/at/for/of.")
code_block(doc, [
    "_WEATHER_HINTS = ('weather','temperature','temp','forecast','climate','degrees',",
    "                  'celsius','fahrenheit','rain','raining','rainy','snow','snowing',",
    "                  'sunny','cloudy','windy','wind','humid','humidity','hot','cold')",
    "_WEATHER_RE = re.compile(r'\\b(' + '|'.join(_WEATHER_HINTS) + r')\\b', re.IGNORECASE)",
    "",
    "def is_weather_query(message: str) -> bool:",
    "    return bool(_WEATHER_RE.search(message))",
    "",
    "def extract_city(message: str) -> str | None:",
    "    m = re.search(r\"\\b(?:in|at|for|of)\\s+([A-Za-z][A-Za-z .'-]+)\", message)",
    "    ...  # strip trailing 'today'/'now'/'please'; return None if no city",
])
h2("4.2 — Geocoding: population ranking + city aliases")
body(doc, "Open-Meteo matches names literally, so 'Bangalore' can return a tiny town in Pakistan, "
          "and it lists some Indian cities only under their official spelling. We ask for several "
          "candidates and keep the most populous, and map common aliases/misspellings first.")
code_block(doc, [
    "_CITY_ALIASES = {'bangalore':'Bengaluru','banglore':'Bengaluru','bombay':'Mumbai',",
    "                 'calcutta':'Kolkata','madras':'Chennai','poona':'Pune',",
    "                 'mysore':'Mysuru','gurgaon':'Gurugram', ...}",
    "",
    "def _geocode(city: str) -> dict | None:",
    "    city = _CITY_ALIASES.get(city.strip().lower(), city)",
    "    resp = httpx.get(_GEOCODE_URL, params={'name': city, 'count': 5,",
    "                     'language': 'en', 'format': 'json'}, timeout=15)",
    "    results = (resp.json() or {}).get('results') or []",
    "    if not results: return None",
    "    return max(results, key=lambda r: r.get('population') or 0)",
])
h2("4.3 — Current conditions -> one-line summary")
code_block(doc, [
    "def get_weather(city: str) -> str | None:",
    "    place = _geocode(city)",
    "    if not place: return None",
    "    resp = httpx.get(_FORECAST_URL, params={'latitude': place['latitude'],",
    "        'longitude': place['longitude'],",
    "        'current': 'temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code'},",
    "        timeout=15)",
    "    cur = (resp.json() or {}).get('current') or {}",
    "    ...  # map WMO weather_code -> text; return one friendly line",
    "    # 'Current weather in Bengaluru, India: partly cloudy, 23.1C, humidity 79%, ...'",
])
h2("4.4 — weather_answer(): the chatbot helper")
body(doc, "Ties it together for the key-less fallback path: returns None for non-weather messages, "
          "a prompt when no city is given, live conditions otherwise, or a friendly not-found line.")


# ===== 5 =====
h1("5. The LangChain Agent (app/ai/agent.py)")
body(doc, "The heart of the upgrade. Your data helpers become tools; a factory builds the LLM from "
          "settings; agent_enabled() reports whether the active backend has a key. All LangChain "
          "imports are LAZY (inside functions) so the module imports fine even before the packages "
          "are installed — callers degrade gracefully.")
h2("5.1 — Switchable LLM factory + capability flag")
code_block(doc, [
    "def agent_enabled() -> bool:",
    "    if settings.ai_provider == 'anthropic':",
    "        return bool(settings.anthropic_api_key)",
    "    return bool(settings.groq_api_key)",
    "",
    "def _make_llm():",
    "    if settings.ai_provider == 'anthropic':",
    "        from langchain_anthropic import ChatAnthropic",
    "        return ChatAnthropic(api_key=settings.anthropic_api_key,",
    "                             model=settings.anthropic_model, temperature=0.3)",
    "    from langchain_groq import ChatGroq        # default: free tool-calling",
    "    return ChatGroq(api_key=settings.groq_api_key,",
    "                    model=settings.groq_model, temperature=0.3)",
])
h2("5.2 — Tools bound to the request")
body(doc, "The tools close over db and user_id; the model only supplies string arguments, never "
          "SQL. my_orders is scoped to the signed-in user, so the agent can never read another "
          "customer's purchases — the same safety model as the original code.")
code_block(doc, [
    "def _build_tools(db, user_id) -> list:",
    "    from langchain_core.tools import tool",
    "",
    "    @tool",
    "    def weather(city: str) -> str:",
    "        '''Get the current live weather for a city. Input: a city name.'''",
    "        return get_weather(city) or f\"Sorry, I couldn't find the weather for '{city}'.\"",
    "",
    "    @tool",
    "    def search_catalog(query: str) -> str:",
    "        '''Search the catalog by title, author, or description keywords.'''",
    "        like = f'%{query}%'",
    "        books = db.scalars(select(Book).where(",
    "            Book.name.like(like) | Book.author.like(like) |",
    "            Book.description.like(like)).limit(15)).all()",
    "        return '\\n'.join(f'- {b.name} by {b.author} (Rs.{b.price})' for b in books) \\",
    "               or 'No matching books found in the catalog.'",
    "",
    "    @tool",
    "    def my_orders(query: str = '') -> str:",
    "        '''List the signed-in customer's own past orders.'''",
    "        from app.ai.service import _order_context   # lazy: avoid circular import",
    "        return _order_context(db, user_id)",
    "",
    "    return [weather, search_catalog, my_orders]",
])
h2("5.3 — Assembling and running the agent")
code_block(doc, [
    "def run_agent(db, user_id, message: str) -> str:",
    "    from langchain.agents import AgentExecutor, create_tool_calling_agent",
    "    from langchain_core.prompts import ChatPromptTemplate",
    "    tools = _build_tools(db, user_id)",
    "    prompt = ChatPromptTemplate.from_messages([",
    "        ('system', _SYSTEM),          # tells the agent when to use each tool",
    "        ('human', '{input}'),",
    "        ('placeholder', '{agent_scratchpad}'),   # the tool-call loop lives here",
    "    ])",
    "    agent = create_tool_calling_agent(_make_llm(), tools, prompt)",
    "    ex = AgentExecutor(agent=agent, tools=tools, max_iterations=4)",
    "    return (ex.invoke({'input': message}).get('output') or '').strip()",
])


# ===== 6 =====
h1("6. Wiring: chat_reply and the Routes")
body(doc, "chat_reply (app/ai/service.py) now delegates to the agent, and keeps the key-less "
          "weather fallback so the integration is testable with no credentials. The web and API "
          "routes just call chat_reply — gating is centralised.")
code_block(doc, [
    "# app/ai/service.py",
    "def chat_reply(claude, db, message, user_id) -> str:",
    "    from app.ai.agent import agent_enabled, run_agent",
    "    if not agent_enabled():",
    "        # no LLM key: still answer weather from the free key-less API",
    "        return weather_answer(message) or 'The AI assistant is not configured yet.'",
    "    try:",
    "        return run_agent(db, user_id, message)",
    "    except Exception:",
    "        return weather_answer(message) or (",
    "            \"Sorry, I'm having trouble reaching the assistant right now.\")",
    "",
    "# app/ai/web.py  (POST /ai/chat) and app/ai/api.py (POST /api/ai/chat)",
    "reply = service.chat_reply(claude, db, payload.message, user.id)",
])
body(doc, "Note: the chatbot's 'enabled' check is agent_enabled() (the active provider's key), "
          "independent of ClaudeService.enabled — the other nine AI features still call Anthropic "
          "directly, so the chatbot can run on Groq while they stay on Claude (or off).", italic=True)


# ===== 7 =====
h1("7. Graceful Degradation")
make_table(
    doc,
    ["Situation", "Chatbot behaviour"],
    [
        ["No key; weather question", "Live Open-Meteo answer (key-less tool)"],
        ["No key; book/order question", "'The AI assistant is not configured yet.'"],
        ["Groq key set", "Full agent: weather + catalog + orders, multi-tool"],
        ["LangChain not installed", "Modules still import; agent path degrades to fallback"],
        ["LLM/network error mid-call", "Weather fallback if relevant, else friendly error"],
    ],
)


# ===== 8 =====
h1("8. Verification")
body(doc, "The implementation was verified end to end short of a live billed call:")
bullet(doc, "Modules import cleanly both before and after installing LangChain (lazy imports).")
bullet(doc, "Agent constructs: ChatGroq(llama-3.3-70b) + 3 tools (weather, search_catalog, "
            "my_orders) + AgentExecutor.")
bullet(doc, "Key-less weather tool returns live data (Tokyo, Paris, Delhi, Bengaluru).")
bullet(doc, "City aliases resolve correctly (Bangalore/Banglore -> Bengaluru; Bombay -> Mumbai; "
            "Calcutta -> Kolkata; Madras -> Chennai).")
bullet(doc, "chat_reply falls back to weather with no key set; full app (app.main) imports.")
code_block(doc, [
    "# quick manual check of the key-less weather path",
    "python -c \"from app.core.weather import weather_answer; \\",
    "  print(weather_answer('weather in Tokyo'))\"",
])


# ===== 9 =====
h1("9. Security & Notes")
bullet(doc, "Keys stay server-side and out of git — only in .env; .env.example is the template.")
bullet(doc, "The model never sees SQL: tools take plain strings and run parameterised SQLAlchemy "
            "queries. my_orders is scoped to the signed-in user_id.")
bullet(doc, "Groq's free tier is rate-limited (~30 req/min) — fine for testing; watch it in a demo.")
bullet(doc, "The REST endpoint now returns a friendly reply (HTTP 200) instead of 503 when the "
            "chatbot is unconfigured, matching the web UI.")
bullet(doc, "Semantic search (Feature 10) is untouched; it could later be added as a retriever "
            "tool, but is not required.")


# ===== Summary =====
h1("One-Paragraph Summary")
body(doc, "The chatbot moved from manual RAG to a LangChain tool-calling agent (app/ai/agent.py): "
          "the LLM chooses among three tools — a free, key-less live-weather tool (Open-Meteo, in "
          "app/core/weather.py), a catalog search, and the user's own orders. The LLM backend is "
          "switchable via AI_PROVIDER between free Groq (default) and paid Anthropic Claude. "
          "chat_reply delegates to the agent and falls back to the key-less weather tool when no "
          "key is set, so the whole thing is testable for free. Setup is: pip install, grab a free "
          "Groq key, set AI_PROVIDER=groq and GROQ_API_KEY in .env, restart — done.", italic=True)

out = "Book_Store_FastAPI_Chatbot_LangChain.docx"
doc.save(out)
print("Saved:", out)
