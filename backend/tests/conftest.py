"""Shared pytest fixtures.

Tests run fully isolated from the production stack:
  - the database is an in-memory SQLite (aiosqlite) created fresh per test;
  - Redis is replaced by an in-memory fake so no Redis server is required;
  - external services (LLM, Qdrant) are never called by the tested endpoints,
    and where they would be, tests monkeypatch the relevant function.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.main import app
from app.models.user import User


# --- In-memory Redis replacement -------------------------------------------

class _FakePipe:
    def __init__(self, redis):
        self._redis = redis
        self._ops = []

    def incr(self, key):
        self._ops.append(("incr", key))
        return self

    def expire(self, key, ttl):
        self._ops.append(("expire", key, ttl))
        return self

    async def execute(self):
        for op in self._ops:
            if op[0] == "incr":
                await self._redis.incr(op[1])
        self._ops = []
        return []


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value

    async def incr(self, key):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    async def expire(self, key, ttl):
        return True

    def pipeline(self):
        return _FakePipe(self)

    async def ping(self):
        return True

    async def close(self):
        pass

    async def scan_iter(self, match=None):
        for key in list(self.store):
            yield key

    async def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """Replace get_redis everywhere it is referenced so tests need no Redis."""
    redis = FakeRedis()

    async def _get_redis():
        return redis

    monkeypatch.setattr("app.core.redis.get_redis", _get_redis)
    monkeypatch.setattr("app.core.security.get_redis", _get_redis)
    monkeypatch.setattr("app.core.rate_limiter.get_redis", _get_redis)
    return redis


# --- Database ----------------------------------------------------------------

@pytest_asyncio.fixture
async def db_sessionmaker():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_sessionmaker):
    """A session for arranging test data directly."""
    async with db_sessionmaker() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_sessionmaker):
    async def _override_get_db():
        async with db_sessionmaker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# --- Users / auth helpers ----------------------------------------------------

async def _make_user(db_sessionmaker, username, password, role):
    async with db_sessionmaker() as session:
        user = User(
            username=username,
            email=f"{username}@test.local",
            full_name=username,
            hashed_password=get_password_hash(password),
            role=role,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


@pytest_asyncio.fixture
async def admin_user(db_sessionmaker):
    uid = await _make_user(db_sessionmaker, "admin", "admin123", "super_admin")
    return {"id": uid, "username": "admin", "password": "admin123"}


@pytest_asyncio.fixture
async def employee_user(db_sessionmaker):
    uid = await _make_user(db_sessionmaker, "bob", "bobpass1", "employee")
    return {"id": uid, "username": "bob", "password": "bobpass1"}


async def _login(client, username, password):
    resp = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def admin_headers(client, admin_user):
    token = await _login(client, admin_user["username"], admin_user["password"])
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def employee_headers(client, employee_user):
    token = await _login(client, employee_user["username"], employee_user["password"])
    return {"Authorization": f"Bearer {token}"}
