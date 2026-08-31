import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic import context

# Load app config
from app.config import settings

# Import all models so Alembic can detect them
from app.database import Base
import app.owners.models  # noqa
import app.shops.models  # noqa
import app.workers.models  # noqa
import app.categories.models  # noqa
import app.products.models  # noqa
import app.inventory.models  # noqa
import app.sales.models  # noqa

# Alembic Config object
config = context.config

# Override sqlalchemy.url from app settings
# psycopg2 uses `sslmode=require` — replace the `ssl=true` Neon uses for asyncpg
_sync_url = (
    settings.DATABASE_URL
    .replace("+asyncpg", "+psycopg2")
    .replace("?ssl=true", "?sslmode=require")
    .replace("&ssl=true", "")
    .replace("?ssl=require", "?sslmode=require")
    .replace("&ssl=require", "")
)
config.set_main_option("sqlalchemy.url", _sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
