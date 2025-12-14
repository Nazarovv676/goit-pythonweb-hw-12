# tests/test_auth.py
"""Tests for authentication endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import crud
from app.db import get_session
from app.main import app
from app.models import Base

# Use SQLite for tests (in-memory)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_session():
    """Override database session for testing."""
    session = TestingSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# Override the dependency
app.dependency_overrides[get_session] = override_get_session


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with fresh database."""
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def user_data():
    """Sample user registration data."""
    return {
        "email": "test@example.com",
        "password": "securepassword123",
        "full_name": "Test User",
    }


class TestUserRegistration:
    """Tests for user registration."""

    @patch("app.routers.auth.send_verification_email", new_callable=AsyncMock)
    def test_register_success(self, mock_send_email, client, user_data):
        """Test successful user registration returns 201."""
        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["full_name"] == user_data["full_name"]
        assert data["is_verified"] is False
        assert data["is_active"] is True
        assert "id" in data
        # Password should not be in response
        assert "password" not in data
        assert "hashed_password" not in data

        # Verify email was sent
        mock_send_email.assert_called_once()

    @patch("app.routers.auth.send_verification_email", new_callable=AsyncMock)
    def test_register_duplicate_email_returns_409(
        self, mock_send_email, client, user_data
    ):
        """Test that registering with existing email returns 409."""
        # First registration
        client.post("/api/auth/register", json=user_data)

        # Second registration with same email
        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    def test_register_invalid_email(self, client, user_data):
        """Test that invalid email returns 422."""
        user_data["email"] = "not-an-email"
        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == 422

    def test_register_short_password(self, client, user_data):
        """Test that short password returns 422."""
        user_data["password"] = "short"
        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == 422


class TestUserLogin:
    """Tests for user login."""

    @patch("app.routers.auth.send_verification_email", new_callable=AsyncMock)
    def test_login_unverified_user_returns_401(
        self, mock_send_email, client, user_data
    ):
        """Test that unverified user cannot login."""
        # Register user (not verified)
        client.post("/api/auth/register", json=user_data)

        # Try to login
        response = client.post(
            "/api/auth/login",
            data={
                "username": user_data["email"],
                "password": user_data["password"],
            },
        )

        assert response.status_code == 401
        assert "not verified" in response.json()["detail"].lower()

    @patch("app.routers.auth.send_verification_email", new_callable=AsyncMock)
    def test_login_verified_user_returns_token(
        self, mock_send_email, client, user_data, db_session
    ):
        """Test that verified user can login and receive token."""
        # Register user
        client.post("/api/auth/register", json=user_data)

        # Manually verify the user (simulating email verification)
        crud.verify_user_email(db_session, user_data["email"])
        db_session.commit()

        # Login
        response = client.post(
            "/api/auth/login",
            data={
                "username": user_data["email"],
                "password": user_data["password"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @patch("app.routers.auth.send_verification_email", new_callable=AsyncMock)
    def test_login_wrong_password_returns_401(
        self, mock_send_email, client, user_data, db_session
    ):
        """Test that wrong password returns 401."""
        # Register and verify user
        client.post("/api/auth/register", json=user_data)
        crud.verify_user_email(db_session, user_data["email"])
        db_session.commit()

        # Try to login with wrong password
        response = client.post(
            "/api/auth/login",
            data={
                "username": user_data["email"],
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_nonexistent_user_returns_401(self, client):
        """Test that non-existent user returns 401."""
        response = client.post(
            "/api/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "anypassword",
            },
        )

        assert response.status_code == 401


class TestEmailVerification:
    """Tests for email verification."""

    @patch("app.routers.auth.send_verification_email", new_callable=AsyncMock)
    def test_verify_valid_token(self, mock_send_email, client, user_data, db_session):
        """Test email verification with valid token."""
        from app.core.security import create_email_verification_token

        # Register user
        client.post("/api/auth/register", json=user_data)

        # Create verification token
        token = create_email_verification_token(user_data["email"])

        # Verify email
        response = client.get(f"/api/auth/verify?token={token}")

        assert response.status_code == 200
        assert "verified" in response.json()["message"].lower()

        # Verify user is now verified in database
        user = crud.get_user_by_email(db_session, user_data["email"])
        assert user.is_verified is True

    def test_verify_invalid_token(self, client):
        """Test email verification with invalid token."""
        response = client.get("/api/auth/verify?token=invalid-token")

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    def test_verify_expired_token(self, client, user_data):
        """Test email verification with expired token."""
        from datetime import datetime, timedelta, timezone

        from jose import jwt

        from app.core.config import get_settings

        settings = get_settings()

        # Create an expired token
        expire = datetime.now(timezone.utc) - timedelta(hours=1)
        token = jwt.encode(
            {"sub": user_data["email"], "exp": expire, "type": "email_verification"},
            settings.secret_key,
            algorithm=settings.algorithm,
        )

        response = client.get(f"/api/auth/verify?token={token}")

        assert response.status_code == 400


class TestCurrentUser:
    """Tests for /api/users/me endpoint."""

    @patch("app.routers.auth.send_verification_email", new_callable=AsyncMock)
    def test_get_current_user_authenticated(
        self, mock_send_email, client, user_data, db_session
    ):
        """Test getting current user with valid token."""
        # Register and verify user
        client.post("/api/auth/register", json=user_data)
        crud.verify_user_email(db_session, user_data["email"])
        db_session.commit()

        # Login to get token
        login_response = client.post(
            "/api/auth/login",
            data={
                "username": user_data["email"],
                "password": user_data["password"],
            },
        )
        token = login_response.json()["access_token"]

        # Get current user
        response = client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["full_name"] == user_data["full_name"]

    def test_get_current_user_no_token(self, client):
        """Test getting current user without token returns 401."""
        response = client.get("/api/users/me")

        assert response.status_code == 401

    def test_get_current_user_invalid_token(self, client):
        """Test getting current user with invalid token returns 401."""
        response = client.get(
            "/api/users/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401


class TestPasswordHashing:
    """Tests for password security."""

    @patch("app.routers.auth.send_verification_email", new_callable=AsyncMock)
    def test_password_is_hashed_in_database(
        self, mock_send_email, client, user_data, db_session
    ):
        """Test that password is stored as bcrypt hash, not plaintext."""
        client.post("/api/auth/register", json=user_data)

        user = crud.get_user_by_email(db_session, user_data["email"])

        # Password should be hashed
        assert user.hashed_password != user_data["password"]
        # bcrypt hashes start with $2b$
        assert user.hashed_password.startswith("$2b$")

