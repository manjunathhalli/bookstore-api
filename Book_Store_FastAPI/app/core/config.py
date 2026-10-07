"""Application configuration, loaded from environment / .env file.

Mirrors the relevant pieces of the Laravel app's .env (DB connection, app
name, token lifetime).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Book Store"
    secret_key: str = "insecure-dev-secret-change-me"
    access_token_expire_minutes: int = 1440
    algorithm: str = "HS256"

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_database: str = "book_store_product"
    db_username: str = "root"
    db_password: str = ""

    create_tables: bool = True

    # --- AI features (Anthropic Claude API + Voyage embeddings) -------------- #
    # Mirrors the Laravel guide's config/services.php 'anthropic' + 'voyage'.
    # All keys are optional: with no API key the AI features degrade gracefully.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_model_fast: str = "claude-haiku-4-5-20251001"
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    anthropic_version: str = "2023-06-01"
    voyage_api_key: str = ""
    voyage_model: str = "voyage-3"

    # --- AI provider (all text features + chatbot) --------------------------- #
    # ``ai_provider`` selects the LLM backend for EVERY text feature (sentiment,
    # moderation, descriptions, summaries, search, recommendations, tagging,
    # forecast, and both chatbots):
    #   "groq"      -> free, OpenAI-compatible backend (key at console.groq.com)
    #   "anthropic" -> Anthropic Claude (uses the anthropic_* keys above)
    #   "ollama"    -> local model via Ollama (no API key, no network — runs on
    #                  this machine at ollama_base_url).
    # Embeddings (semantic search) always run locally and ignore this setting.
    ai_provider: str = "groq"
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.3-70b-versatile"
    groq_model_fast: str = "llama-3.1-8b-instant"

    # --- Ollama (local, key-less) --------------------------------------------- #
    # Requires the Ollama app running locally (https://ollama.com) with the model
    # pulled, e.g. `ollama pull qwen2.5`. No API key needed.
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5"
    ollama_model_fast: str = "qwen2.5"

    # --- Microsoft Business Central RAG chatbot (separate from BookBot) ------ #
    # A second, independent chatbot that ingests Business Central records into a
    # Qdrant vector DB and answers questions grounded in those vectors. All keys
    # are optional: with no BC credentials the ingest falls back to bundled
    # sample data so the full pipeline can be tested key-lessly.
    #
    # Business Central uses Azure AD OAuth2 *client-credentials*. Register an app
    # in Azure AD, grant it the Business Central API permission, and put the
    # tenant id + client id/secret here.
    bc_tenant_id: str = ""
    bc_client_id: str = ""
    bc_client_secret: str = ""
    bc_environment: str = "KK_DEV1"
    bc_company: str = ""
    bc_login_base: str = "https://login.microsoftonline.com"
    bc_api_base: str = "https://api.businesscentral.dynamics.com/v2.0"
    bc_scope: str = "https://api.businesscentral.dynamics.com/.default"
    # Cap records pulled per entity so a first sync stays quick; raise as needed.
    bc_max_records: int = 500

    # ``bc_api_style`` selects the BC API surface:
    #   "api"   -> standard REST API   .../api/v2.0/companies({guid})/{entity}
    #              ``bc_company`` is the company display name (blank -> first).
    #   "odata" -> OData V4 web services  .../ODataV4/Company('{name}')/{service}
    #              ``bc_company`` MUST be the company name, and ``bc_entities`` are
    #              the *published web service / page names*, e.g.
    #              "Item_Ledger_Entries_Excel".
    bc_api_style: str = "api"
    bc_entities: str = "items,customers,salesOrders"
    # Optional OData $filter applied to every OData fetch (raw OData syntax), e.g.
    #   "Posting_Date gt 2026-01-01". Leave blank for no filter.
    bc_odata_filter: str = ""

    # --- Qdrant vector database --------------------------------------------- #
    # Two ways to run it:
    #  * EMBEDDED (default): no server needed — qdrant-client stores the vectors
    #    in a local folder (``qdrant_path``). Great for a single-process dev app.
    #  * SERVER: leave ``qdrant_path`` blank and set ``qdrant_url`` to a running
    #    Qdrant (local Docker: docker run -p 6333:6333 qdrant/qdrant, or Qdrant
    #    Cloud with ``qdrant_api_key``).
    # ``qdrant_path`` wins when set, so embedded mode works with zero setup.
    qdrant_path: str = "./qdrant_storage"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "business_central"

    # --- Redis (cache) --------------------------------------------------------- #
    # Used to cache read-heavy, rarely-changing responses (the book catalogue)
    # so repeat requests skip the database. See app/books/cache.py.
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_cache_seconds: int = 60

    # --- Celery (background jobs) ---------------------------------------------- #
    # Long-running work (building an Excel sales report with Pandas) is handed
    # off to a Celery worker instead of blocking the request. Celery uses Redis
    # as both the task queue (broker) and the result store (backend), so no
    # extra infrastructure is needed beyond the Redis above.
    celery_broker_db: int = 1
    celery_result_db: int = 2

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_username}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_database}?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def celery_broker_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.celery_broker_db}"

    @property
    def celery_result_backend(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.celery_result_db}"

    @property
    def bc_configured(self) -> bool:
        """True when real Business Central credentials are present."""
        return bool(self.bc_tenant_id and self.bc_client_id and self.bc_client_secret)

    @property
    def bc_entity_list(self) -> list[str]:
        """Parsed, cleaned list of BC entities to ingest."""
        return [e.strip() for e in self.bc_entities.split(",") if e.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
