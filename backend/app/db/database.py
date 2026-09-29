from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine_kwargs(database_url: str) -> dict:
    if database_url.startswith("sqlite"):
        return {}
    return {"pool_pre_ping": True}


_settings = get_settings()
engine = create_async_engine(_settings.database_url, **_make_engine_kwargs(_settings.database_url))
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
