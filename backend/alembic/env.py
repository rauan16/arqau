from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app import models
from app.config import get_settings
from app.core.database import Base, normalize_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = normalize_database_url(get_settings().database_url)
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(run_migrations)

    await connectable.dispose()


def run_migrations_offline() -> None:
    raise RuntimeError("Legacy baseline detection requires online Alembic mode")


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
