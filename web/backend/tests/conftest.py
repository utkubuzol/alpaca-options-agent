import os

from cryptography.fernet import Fernet

os.environ.setdefault("APP_SECRET_KEY", Fernet.generate_key().decode())
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-bot-token")

import pytest
from fastapi.testclient import TestClient

from app.deps import get_current_user
from app.main import app

TEST_USER = {"id": "11111111-1111-1111-1111-111111111111", "email": "t@example.com"}


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
