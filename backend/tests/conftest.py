"""Test fixtures and configuration."""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Set test environment before importing app
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["ENCRYPTION_KEY"] = "dGVzdC1lbmNyeXB0aW9uLWtleS1mb3ItdGVzdGluZw=="  # valid base64 44 chars
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "testpass123"
os.environ["DEMO_MODE"] = "true"
os.environ["WG_SERVER_IP"] = "127.0.0.1"

from app.database import Base, get_db
from app.main import app
from app.core.security import hash_password
from app.models.admin import Admin


# Test database
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    """Get a database session for tests."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """Get a test client."""
    return TestClient(app)


@pytest.fixture
def admin_user(db):
    """Create and return a super_admin user."""
    admin = Admin(
        username="testadmin",
        password_hash=hash_password("testpass123"),
        role="super_admin",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.fixture
def limited_admin(db):
    """Create and return a limited admin user."""
    import json
    admin = Admin(
        username="limitedadmin",
        password_hash=hash_password("testpass123"),
        role="admin",
        permissions=json.dumps(["users.view", "logs.view"]),
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.fixture
def auth_headers(client, admin_user):
    """Get auth headers for a super_admin."""
    res = client.post("/api/auth/login", json={
        "username": "testadmin",
        "password": "testpass123",
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def limited_auth_headers(client, limited_admin):
    """Get auth headers for a limited admin."""
    res = client.post("/api/auth/login", json={
        "username": "limitedadmin",
        "password": "testpass123",
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
