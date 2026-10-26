from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.deps import get_today
from app.main import app


class Clock:
    """Lets a test pretend it is any day."""

    def __init__(self):
        self.today = date(2026, 10, 1)


@pytest.fixture()
def clock():
    return Clock()


@pytest.fixture()
def client(clock):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_today] = lambda: clock.today
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def make_headers(client):
    """make_headers('a@x.com') registers + logs in a user and returns auth headers."""

    def _make(email: str):
        client.post("/auth/register", json={"name": "T", "email": email, "password": "password123"})
        token = client.post("/auth/login", data={"username": email, "password": "password123"}).json()[
            "access_token"
        ]
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture()
def headers(make_headers):
    return make_headers("owner@example.com")
