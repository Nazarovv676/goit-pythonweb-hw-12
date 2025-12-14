# tests/test_auth.py
"""Tests for authentication endpoints."""

from datetime import UTC
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_email_verification_token
from tests.conftest import create_test_user, get_auth_headers


class TestUserRegistration:
    """Tests for user registration."""

    @patch("app.routers.auth.send_verification_email", new_callable=AsyncMock)
    def test_register_success(
        self, mock_send_email: AsyncMock, client: TestClient
    ) -> None:
        """Test successful user registration returns 201."""
        user_data = {
            "email": "newuser@example.com",
            "password": "securepassword123",
            "full_name": "New User",
        }
        response = client.post("/api/auth/register", json=user_data)

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["full_name"] == user_data["full_name"]
        assert data["is_verified"] is False
        assert data["is_active"] is True
        assert data["role"] == "user"  # Default role
        assert "id" in data
        # Password should not be in response
        assert "password" not in data
        assert "hashed_password" not in data

        # Verify email was sent
        mock_send_email.assert_called_once()

    @patch("app.routers.auth.send_verification_email", new_callable=AsyncMock)
    def test_register_duplicate_email_returns_409(
        self, mock_send_email: AsyncMock, client: TestClient, db_session: Session
    ) -> None:
        """Test that registering with existing email returns 409."""
        # First registration
        create_test_user(db_session, email="duplicate@example.com")

        # Second registration with same email
        response = client.post(
            "/api/auth/register",
            json={
                "email": "duplicate@example.com",
                "password": "password123",
                "full_name": "Test",
            },
        )

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"].lower()

    def test_register_invalid_email(self, client: TestClient) -> None:
        """Test that invalid email returns 422."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "not-an-email",
                "password": "password123",
                "full_name": "Test",
            },
        )

        assert response.status_code == 422

    def test_register_short_password(self, client: TestClient) -> None:
        """Test that short password returns 422."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "valid@example.com",
                "password": "short",
                "full_name": "Test",
            },
        )

        assert response.status_code == 422


class TestUserLogin:
    """Tests for user login."""

    def test_login_unverified_user_returns_401(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that unverified user cannot login."""
        create_test_user(
            db_session,
            email="unverified_login@example.com",
            password="password123",
            is_verified=False,
        )

        response = client.post(
            "/api/auth/login",
            data={
                "username": "unverified_login@example.com",
                "password": "password123",
            },
        )

        assert response.status_code == 401
        assert "not verified" in response.json()["detail"].lower()

    def test_login_verified_user_returns_token(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that verified user can login and receive token."""
        create_test_user(
            db_session,
            email="verified_login@example.com",
            password="password123",
            is_verified=True,
        )

        response = client.post(
            "/api/auth/login",
            data={
                "username": "verified_login@example.com",
                "password": "password123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password_returns_401(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that wrong password returns 401."""
        create_test_user(
            db_session,
            email="wrong_pw@example.com",
            password="correctpassword",
            is_verified=True,
        )

        response = client.post(
            "/api/auth/login",
            data={
                "username": "wrong_pw@example.com",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_nonexistent_user_returns_401(self, client: TestClient) -> None:
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

    def test_verify_valid_token(self, client: TestClient, db_session: Session) -> None:
        """Test email verification with valid token."""
        user = create_test_user(
            db_session,
            email="verify_test@example.com",
            is_verified=False,
        )

        # Create verification token
        token = create_email_verification_token(user.email)

        # Verify email
        response = client.get(f"/api/auth/verify?token={token}")

        assert response.status_code == 200
        assert "verified" in response.json()["message"].lower()

        # Verify user is now verified in database
        db_session.refresh(user)
        assert user.is_verified is True

    def test_verify_invalid_token(self, client: TestClient) -> None:
        """Test email verification with invalid token."""
        response = client.get("/api/auth/verify?token=invalid-token")

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    def test_verify_expired_token(self, client: TestClient) -> None:
        """Test email verification with expired token."""
        from datetime import datetime, timedelta

        from jose import jwt

        from app.core.config import get_settings

        settings = get_settings()

        # Create an expired token
        expire = datetime.now(UTC) - timedelta(hours=1)
        token = jwt.encode(
            {"sub": "test@example.com", "exp": expire, "type": "email_verification"},
            settings.secret_key,
            algorithm=settings.algorithm,
        )

        response = client.get(f"/api/auth/verify?token={token}")

        assert response.status_code == 400


class TestCurrentUser:
    """Tests for /api/users/me endpoint."""

    def test_get_current_user_authenticated(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test getting current user with valid token."""
        user = create_test_user(
            db_session,
            email="me_test@example.com",
            full_name="Me Test",
        )
        headers = get_auth_headers(user)

        response = client.get("/api/users/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == user.email
        assert data["full_name"] == user.full_name
        assert data["role"] == "user"

    def test_get_current_user_no_token(self, client: TestClient) -> None:
        """Test getting current user without token returns 401."""
        response = client.get("/api/users/me")

        assert response.status_code == 401

    def test_get_current_user_invalid_token(self, client: TestClient) -> None:
        """Test getting current user with invalid token returns 401."""
        response = client.get(
            "/api/users/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401


class TestPasswordHashing:
    """Tests for password security."""

    def test_password_is_hashed_in_database(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that password is stored as bcrypt hash, not plaintext."""
        user = create_test_user(
            db_session,
            email="hash_test@example.com",
            password="myplainpassword",
        )

        # Password should be hashed
        assert user.hashed_password != "myplainpassword"
        # bcrypt hashes start with $2b$
        assert user.hashed_password.startswith("$2b$")
