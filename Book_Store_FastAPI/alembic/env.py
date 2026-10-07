import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Make ``app`` importable when Alembic is invoked from the project root.
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Import every feature's models so they register themselves on Base.metadata
# before autogenerate compares "what the models say" against "what the DB has".
# Forgetting an import here is the #1 cause of autogenerate silently missing a
# table — SQLAlchemy only knows about a model once it has been imported.
from app.address import models as _address_models  # noqa: F401,E402
from app.auth import models as _auth_models  # noqa: F401,E402
from app.books import models as _books_models  # noqa: F401,E402
from app.cart import models as _cart_models  # noqa: F401,E402
from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.feedback import models as _feedback_models  # noqa: F401,E402
from app.orders import models as _orders_models  # noqa: F401,E402
from app.wishlist import models as _wishlist_models  # noqa: F401,E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Read the DB connection from the app's own settings (.env) instead of
# duplicating it in alembic.ini, so there is exactly one place to change it.
# ``ALEMBIC_SQLALCHEMY_URL`` lets CI/tests point migrations at a throwaway
# database (e.g. SQLite) without touching the real .env.
config.set_main_option(
    "sqlalchemy.url", os.environ.get("ALEMBIC_SQLALCHEMY_URL", settings.database_url)
)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
