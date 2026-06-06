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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_username}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_database}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
