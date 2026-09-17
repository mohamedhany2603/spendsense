"""Test setup — isolated SQLite DB, scheduler off, empty cache per test."""

import os

# Must be set before importing the app modules (engine binds at import time).
os.environ["DATABASE_URL"] = "sqlite:///./test_spendsense.db"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["SECRET_KEY"] = "test-only-secret-key-that-is-longer-than-32-bytes"
os.environ["CACHE_TTL_SECONDS"] = "60"
os.environ["OPENROUTER_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from app.database import Base, SessionLocal, engine
from app.main import app
from app.services.cache import analytics_cache
from app.services.categorizer import ensure_default_categories


@pytest.fixture(scope="session", autouse=True)
def _db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        ensure_default_categories(db)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clear_cache():
    analytics_cache._store.clear()
    yield
    analytics_cache._store.clear()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def user_headers(client) -> dict:
    email = f"user{uuid4().hex}@example.com"
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "name": "Test User"},
    )
    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}