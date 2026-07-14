"""
Shared pytest fixtures.

Every test gets a fresh, isolated SQLite database (a temp file that's
deleted after the test session) and an HTTP client wired to the real
FastAPI app — so tests exercise the actual routes, not mocks, without
ever touching your real dev database (app.db).
"""

import asyncio
import os
import tempfile

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Point the app at a throwaway test database BEFORE importing app code,
# since settings are read once at import time.
_test_db_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_test_db_path}"
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production")

from app.main import app  # noqa: E402
from app.dependencies import get_db  # noqa: E402
from db.base import Base  # noqa: E402
from db.session import AsyncSessionLocal, engine  # noqa: E402

# Import models so Base.metadata knows about every table.
from app.users.models import User  # noqa: E402, F401
from app.conversations.models import Conversation, Message  # noqa: E402, F401
from app.documents.models import Document  # noqa: E402, F401
import pytest_asyncio

@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_test_schema():
    """Create all tables once before the test session, drop the file after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    os.close(_test_db_fd)
    os.remove(_test_db_path)


@pytest_asyncio.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    """An async HTTP client that talks directly to the FastAPI app in-process."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def registered_user(client):
    """Registers a fresh user and returns (email, password) for logging in."""
    email = "testuser@example.com"
    password = "testpassword123"
    await client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Test User"},
    )
    return email, password


@pytest_asyncio.fixture
async def auth_headers(client, registered_user):
    """Logs in and returns headers ready to use for authenticated requests."""
    email, password = registered_user
    response = await client.post("/auth/login", json={"email": email, "password": password})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
