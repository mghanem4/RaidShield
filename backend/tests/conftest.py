import os

os.environ.update(
    {
        "APP_ENV": "test",
        "ADMIN_TOKEN": "test-admin-token",
        "PSEUDONYMIZATION_KEY": "test-installation-pseudonym-key",
        "DATA_ENCRYPTION_KEY": "_f7sGD0YkjbT0nLwrX_InpiMIM2VN0tEfMzM4eeibtg=",
        "DATABASE_URL": "sqlite:///./data/test.db",
        "META_VERIFY_TOKEN": "verify-me",
        "META_APP_SECRET": "meta-test-secret",
        "STORE_RAW_TEXT": "false",
    }
)

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def auth():
    return {"Authorization": "Bearer test-admin-token"}
