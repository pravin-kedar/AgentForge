import os
import tempfile
from collections.abc import AsyncGenerator

_DB_FD, _DB_PATH = tempfile.mkstemp(suffix=".db")
os.close(_DB_FD)

# Must be set before any `app.*` module is imported, since app.core.config
# reads them eagerly (and fails fast if missing) and app.db.database builds
# its engine at import time from DATABASE_URL.
#
# DATABASE_URL is force-overridden, never setdefault: the reset fixture below
# drops every table, so inheriting an ambient DATABASE_URL (e.g. inside the
# api container, where it points at the dev Postgres) would wipe a real DB.
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB_PATH}"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
# setdefault on purpose: a real key exported in the environment is what
# enables `pytest tests/evals --live-llm`.
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("GROQ_MODEL", "test-model")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import models  # noqa: F401  (registers tables on Base.metadata)
from app.db.database import AsyncSessionLocal, Base, engine
from app.llm.factory import get_llm_provider
from app.main import app
from tests.fake_llm import FakeLLMProvider


@pytest_asyncio.fixture(autouse=True)
async def _reset_db() -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db_session(_reset_db: None) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    """An empty FakeLLMProvider; tests script its `.responses` before use."""
    return FakeLLMProvider(responses=[])


@pytest_asyncio.fixture
async def client(fake_llm: FakeLLMProvider) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_llm_provider, None)


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/auth/register",
        json={"email": "traveler@example.com", "password": "password123", "full_name": "Traveler One"},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
