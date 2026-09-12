from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return database_url


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_database(database_url: str | None = None):
    resolved_url = normalize_database_url(database_url or get_settings().database_url)
    database_engine = create_async_engine(
        resolved_url,
        echo=False,
        pool_pre_ping=True,
    )
    if resolved_url.startswith("sqlite"):
        event.listen(database_engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    session_factory = async_sessionmaker(
        database_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return database_engine, session_factory


engine, async_session = create_database()


async def configure_database(database_url: str | None = None) -> None:
    global engine, async_session
    resolved_url = normalize_database_url(database_url or get_settings().database_url)
    new_engine, new_session = create_database(resolved_url)
    await engine.dispose()
    engine = new_engine
    async_session = new_session


async def dispose_engine() -> None:
    await engine.dispose()


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
