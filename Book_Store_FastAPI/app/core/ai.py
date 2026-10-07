"""Core AI service — the FastAPI port of the Laravel ``ClaudeService``.

One reusable client that every AI feature calls. It wraps the Anthropic Claude
*Messages* API (text generation / classification / JSON extraction) for the
text features, and produces embeddings for semantic search with a **local**
``sentence-transformers`` model.

.. note::
   Anthropic does not offer an embeddings API — their guidance points to
   third-party providers such as Voyage AI. To keep semantic search working
   without any external embeddings key, we run a small model locally instead.
   The original Voyage AI implementation is preserved (commented out) below
   for reference — see :meth:`ClaudeService.embed`.

Design notes
------------
* No third-party SDK — we talk to the REST APIs directly with ``httpx`` (which
  FastAPI already ships), mirroring the guide's use of Laravel's ``Http`` client.
* All calls are synchronous. The web/API route handlers are plain ``def`` and
  therefore run in Starlette's threadpool, so a blocking HTTP call here does not
  stall the event loop.
* The API key lives only in the environment / ``.env`` (see ``app.core.config``)
  and never reaches the browser — every AI call happens server-side.

Callers should wrap invocations in ``try/except AIError`` and degrade
gracefully; the individual feature helpers in :mod:`app.ai.service` already do.
"""

from __future__ import annotations

import json
import re

import httpx

from .config import settings


class AIError(RuntimeError):
    """Raised when an AI request cannot be completed (missing key, API error)."""


class ClaudeService:
    """Thin wrapper over the Anthropic Messages API + a local embedding model."""

    # Lazily-loaded shared embedding model (see ``_get_embed_model``). The
    # ``all-MiniLM-L6-v2`` model is small (~80 MB), fast on CPU, and produces
    # 384-dimensional normalised vectors — a good fit for cosine similarity.
    #
    # Two interchangeable backends produce the SAME model / vectors:
    #   * "fastembed"            -> ONNX runtime (Microsoft-signed DLLs). Works
    #                               even when Windows Smart App Control blocks
    #                               PyTorch's unsigned DLLs. Preferred.
    #   * "sentence-transformers"-> PyTorch backend. Fallback when fastembed is
    #                               absent (and torch is loadable).
    _EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
    _EMBED_MODEL_NAME_FASTEMBED = "sentence-transformers/all-MiniLM-L6-v2"
    _embed_model = None  # class-level cache: load once, reuse everywhere
    _embed_backend = None  # "fastembed" | "sentence-transformers"
    _embed_load_failed = False  # sticky flag: don't retry a failed/blocked load

    def __init__(self) -> None:
        self._provider = (settings.ai_provider or "anthropic").lower()
        # Anthropic (Messages API)
        self._key = settings.anthropic_api_key
        self._base_url = settings.anthropic_base_url.rstrip("/")
        self._version = settings.anthropic_version
        self._model = settings.anthropic_model
        self._model_fast = settings.anthropic_model_fast
        # Groq (OpenAI-compatible Chat Completions API)
        self._groq_key = settings.groq_api_key
        self._groq_base = settings.groq_base_url.rstrip("/")
        self._groq_model = settings.groq_model
        self._groq_model_fast = settings.groq_model_fast
        # Ollama (local, key-less)
        self._ollama_base = settings.ollama_base_url.rstrip("/")
        self._ollama_model = settings.ollama_model
        self._ollama_model_fast = settings.ollama_model_fast
        # --- Voyage AI embeddings config (retired — kept for reference) ---
        # self._voyage_key = settings.voyage_api_key
        # self._voyage_model = settings.voyage_model

    # --------------------------------------------------------------------- #
    # Capability flags (used by the UI to show/hide AI affordances)
    # --------------------------------------------------------------------- #

    @property
    def provider(self) -> str:
        """The active LLM backend: ``"groq"``, ``"anthropic"``, or ``"ollama"``."""
        return self._provider

    @property
    def key_env_name(self) -> str:
        """The .env variable the active provider needs (for UI hints)."""
        if self._provider == "groq":
            return "GROQ_API_KEY"
        if self._provider == "ollama":
            return "OLLAMA_BASE_URL"
        return "ANTHROPIC_API_KEY"

    @property
    def enabled(self) -> bool:
        """True when the active provider is usable (key configured, or local for Ollama)."""
        if self._provider == "groq":
            return bool(self._groq_key)
        if self._provider == "ollama":
            return True  # local, no key — assumed reachable; calls fail gracefully otherwise
        return bool(self._key)

    @property
    def embeddings_enabled(self) -> bool:
        """True when the local embedding model can be loaded (semantic search).

        Voyage AI required an API key; the local model only needs the
        ``sentence-transformers`` package installed, so semantic search works
        out of the box with no external key.
        """
        return self._get_embed_model() is not None

    @property
    def fast_model(self) -> str:
        """The cheaper/faster model id for the active provider."""
        if self._provider == "groq":
            return self._groq_model_fast
        if self._provider == "ollama":
            return self._ollama_model_fast
        return self._model_fast

    # --------------------------------------------------------------------- #
    # Core: chat / completion
    # --------------------------------------------------------------------- #

    def ask(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
    ) -> str:
        """Send a single user message and return the model's plain-text reply.

        Dispatches to the active provider (``settings.ai_provider``): Anthropic's
        Messages API or Groq's OpenAI-compatible Chat Completions API.
        """
        if self._provider == "groq":
            return self._ask_groq(prompt, system, model, max_tokens)
        if self._provider == "ollama":
            return self._ask_ollama(prompt, system, model, max_tokens)
        return self._ask_anthropic(prompt, system, model, max_tokens)

    def _ask_anthropic(
        self, prompt: str, system: str | None, model: str | None, max_tokens: int
    ) -> str:
        if not self._key:
            raise AIError("ANTHROPIC_API_KEY is not configured.")

        payload: dict = {
            "model": model or self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        try:
            response = httpx.post(
                f"{self._base_url}/messages",
                headers={
                    "x-api-key": self._key,
                    "anthropic-version": self._version,
                    "content-type": "application/json",
                },
                json=payload,
                timeout=60,
            )
        except httpx.HTTPError as exc:  # network / timeout
            raise AIError(f"AI request failed: {exc}") from exc

        if response.status_code >= 400:
            raise AIError(f"AI request failed: {response.status_code} {response.text}")

        data = response.json()
        blocks = data.get("content") or []
        if blocks and isinstance(blocks, list):
            return blocks[0].get("text", "")
        return ""

    def _ask_groq(
        self, prompt: str, system: str | None, model: str | None, max_tokens: int
    ) -> str:
        """Groq / OpenAI-compatible Chat Completions call (system+user messages)."""
        if not self._groq_key:
            raise AIError("GROQ_API_KEY is not configured.")

        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": model or self._groq_model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        try:
            response = httpx.post(
                f"{self._groq_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._groq_key}",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=60,
            )
        except httpx.HTTPError as exc:  # network / timeout
            raise AIError(f"AI request failed: {exc}") from exc

        if response.status_code >= 400:
            raise AIError(f"AI request failed: {response.status_code} {response.text}")

        data = response.json()
        choices = data.get("choices") or []
        if choices and isinstance(choices, list):
            return (choices[0].get("message") or {}).get("content", "") or ""
        return ""

    def _ask_ollama(
        self, prompt: str, system: str | None, model: str | None, max_tokens: int
    ) -> str:
        """Local Ollama call (native ``/api/chat`` endpoint, no API key)."""
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model": model or self._ollama_model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }

        try:
            response = httpx.post(
                f"{self._ollama_base}/api/chat",
                json=payload,
                timeout=120,
            )
        except httpx.HTTPError as exc:  # network / timeout / Ollama not running
            raise AIError(f"AI request failed: {exc}") from exc

        if response.status_code >= 400:
            raise AIError(f"AI request failed: {response.status_code} {response.text}")

        data = response.json()
        return (data.get("message") or {}).get("content", "") or ""

    def ask_json(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
    ):
        """Ask for JSON and return the parsed value (``{}`` on parse failure).

        Strips Markdown code fences the model sometimes wraps JSON in, mirroring
        the guide's ``askJson`` regex clean-up.
        """
        raw = self.ask(prompt, system, model, max_tokens).strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return {}

    # --------------------------------------------------------------------- #
    # Embeddings (local sentence-transformers model — no external API)
    # --------------------------------------------------------------------- #

    @classmethod
    def _get_embed_model(cls):
        """Load (once) and return the shared embedding model, or ``None``.

        Prefers the ``fastembed`` (ONNX) backend, whose runtime DLLs are
        Microsoft-signed and therefore allowed by Windows Smart App Control;
        falls back to ``sentence-transformers`` (PyTorch). Returns ``None`` when
        neither can be loaded — package missing, or a backend DLL blocked/absent
        — so the UI degrades gracefully (semantic search hidden) exactly as it
        did when a Voyage key was absent. The failure is cached so the
        slow/failing import isn't retried on every request.
        """
        if cls._embed_model is None and not cls._embed_load_failed:
            # 1) fastembed / ONNX — works under Smart App Control.
            try:
                from fastembed import TextEmbedding

                cls._embed_model = TextEmbedding(model_name=cls._EMBED_MODEL_NAME_FASTEMBED)
                cls._embed_backend = "fastembed"
                return cls._embed_model
            except Exception:
                pass
            # 2) sentence-transformers / PyTorch — fallback.
            try:
                from sentence_transformers import SentenceTransformer

                cls._embed_model = SentenceTransformer(cls._EMBED_MODEL_NAME)
                cls._embed_backend = "sentence-transformers"
                return cls._embed_model
            except Exception:
                # ImportError (package missing), OSError (blocked/missing DLL),
                # or any model-load error — semantic search is simply unavailable.
                cls._embed_load_failed = True
                return None
        return cls._embed_model

    def embed(self, text: str) -> list[float]:
        """Return a (unit-normalised) embedding vector for ``text`` locally."""
        model = self._get_embed_model()
        if model is None:
            raise AIError(
                "No local embedding backend available — run "
                "'pip install fastembed' (recommended) or 'pip install "
                "sentence-transformers' to enable semantic search."
            )
        # Both backends yield 384-dim unit vectors, so cosine similarity is a
        # plain dot product; ``.tolist()`` makes it JSON-serialisable for storage.
        if self._embed_backend == "fastembed":
            # fastembed.embed() takes an iterable and yields numpy arrays,
            # already L2-normalised for all-MiniLM-L6-v2.
            vector = next(iter(model.embed([text])))
        else:
            vector = model.encode(text, normalize_embeddings=True)
        return vector.tolist()

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts at once — far faster than looping ``embed``.

        Both backends process a whole list per call (fastembed streams numpy
        arrays for the iterable; sentence-transformers encodes the list in one
        vectorised pass), so a large ingest embeds in a handful of batched calls
        instead of thousands of single-text calls. Order is preserved. Raises the
        same :class:`AIError` as :meth:`embed` when no backend is available.
        """
        if not texts:
            return []
        model = self._get_embed_model()
        if model is None:
            raise AIError(
                "No local embedding backend available — run "
                "'pip install fastembed' (recommended) or 'pip install "
                "sentence-transformers' to enable semantic search."
            )
        if self._embed_backend == "fastembed":
            return [vec.tolist() for vec in model.embed(texts)]
        return [vec.tolist() for vec in model.encode(texts, normalize_embeddings=True)]

    # --- Retired: Voyage AI embeddings (kept for reference, do not delete) --- #
    # Anthropic has no embeddings API; this called Voyage AI, which required a
    # VOYAGE_API_KEY. Replaced by the local model above.
    #
    # def embed(self, text: str) -> list[float]:
    #     """Return an embedding vector for ``text`` via Voyage AI."""
    #     if not self._voyage_key:
    #         raise AIError("VOYAGE_API_KEY is not configured.")
    #
    #     try:
    #         response = httpx.post(
    #             "https://api.voyageai.com/v1/embeddings",
    #             headers={
    #                 "Authorization": f"Bearer {self._voyage_key}",
    #                 "content-type": "application/json",
    #             },
    #             json={"model": self._voyage_model, "input": text},
    #             timeout=60,
    #         )
    #     except httpx.HTTPError as exc:
    #         raise AIError(f"Embedding request failed: {exc}") from exc
    #
    #     if response.status_code >= 400:
    #         raise AIError(f"Embedding request failed: {response.status_code} {response.text}")
    #
    #     data = response.json().get("data") or []
    #     if data and isinstance(data, list):
    #         return data[0].get("embedding", [])
    #     return []


# A single shared instance — cheap to construct, holds no open connections.
claude = ClaudeService()


def get_claude() -> ClaudeService:
    """FastAPI dependency / accessor for the shared :class:`ClaudeService`."""
    return claude
