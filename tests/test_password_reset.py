# tests/test_password_reset.py
"""
Tests for password reset functionality.

This module tests:
- Password reset request (always returns 202)
- Password reset completion with valid token
- Invalid/expired token handling
- Single-use token enforcement
- Cache invalidation after password reset
"""

from datetime import UTC
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import verify_password
from tests.conftest import FakeRedis, create_test_user


class TestPasswordResetRequest:
    """Tests for password reset request endpoint."""

    def test_request_reset_returns_202_for_existing_user(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        """Test that password reset request returns 202 for existing user."""
        user = create_test_user(db_session, email="reset_test@example.com")

        with patch(
            "app.routers.auth.send_password_reset_email", new_callable=AsyncMock
        ) as mock_email:
            response = client.post(
                "/api/auth/request-password-reset",
                json={"email": user.email},
            )

        assert response.status_code == 202
        assert "reset link will be sent" in response.json()["message"].lower()
        mock_email.assert_called_once()

    def test_request_reset_returns_202_for_nonexistent_user(
        self,
        client: TestClient,
    ) -> None:
        """Test that password reset returns 202 even for non-existent email (no enumeration)."""
        with patch(
            "app.routers.auth.send_password_reset_email", new_callable=AsyncMock
        ) as mock_email:
            response = client.post(
                "/api/auth/request-password-reset",
                json={"email": "nonexistent@example.com"},
            )

        assert response.status_code == 202
        # Email should NOT be sent for non-existent user
        mock_email.assert_not_called()

    def test_request_reset_sends_email_in_background(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        """Test that password reset email is sent via background task."""
        user = create_test_user(db_session, email="bg_email@example.com")

        with patch(
            "app.routers.auth.send_password_reset_email", new_callable=AsyncMock
        ) as mock_email:
            response = client.post(
                "/api/auth/request-password-reset",
                json={"email": user.email},
            )

        assert response.status_code == 202
        # Verify email function was called with correct params
        mock_email.assert_called_once()
        call_args = mock_email.call_args
        assert call_args[0][0] == user.email  # First arg is email


class TestPasswordResetCompletion:
    """Tests for completing password reset."""

    def test_reset_password_success(
        self,
        client: TestClient,
        db_session: Session,
        fake_redis: FakeRedis,
    ) -> None:
        """Test successful password reset with valid token."""
        from app.core.security import create_password_reset_token

        user = create_test_user(
            db_session,
            email="reset_success@example.com",
            password="oldpassword123",
        )

        # Create reset token
        token, jti = create_password_reset_token(user.id, user.email)

        # Store JTI in fake Redis (simulating what create_reset_token does)
        fake_redis._store[f"reset:{jti}"] = '{"used": false}'

        # Reset password
        response = client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "newpassword456"},
        )

        assert response.status_code == 200
        assert "successfully" in response.json()["message"].lower()

        # Verify password was changed
        db_session.refresh(user)
        assert verify_password("newpassword456", user.hashed_password)
        assert not verify_password("oldpassword123", user.hashed_password)

    def test_reset_password_invalid_token(
        self,
        client: TestClient,
    ) -> None:
        """Test password reset with invalid token."""
        response = client.post(
            "/api/auth/reset-password",
            json={"token": "invalid-token-here", "new_password": "newpassword123"},
        )

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    def test_reset_password_expired_token(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        """Test password reset with expired token."""
        from datetime import datetime, timedelta

        from app.core.security import _password_reset_serializer

        user = create_test_user(db_session, email="expired_reset@example.com")

        # Create an "old" token by using a past timestamp
        # The serializer won't accept this as it will be expired
        payload = {
            "sub": user.id,
            "email": user.email,
            "jti": "test-jti",
            "iat": (datetime.now(UTC) - timedelta(hours=2)).isoformat(),
        }
        token = _password_reset_serializer.dumps(payload)

        # Try to reset with old token (max_age will reject it)
        response = client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "newpassword123"},
        )

        # Token should be rejected (either as expired or invalid)
        assert response.status_code == 400

    def test_reset_password_short_password_rejected(
        self,
        client: TestClient,
        db_session: Session,
        fake_redis: FakeRedis,
    ) -> None:
        """Test that short passwords are rejected."""
        from app.core.security import create_password_reset_token

        user = create_test_user(db_session, email="short_pw@example.com")
        token, jti = create_password_reset_token(user.id, user.email)
        fake_redis._store[f"reset:{jti}"] = '{"used": false}'

        response = client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "short"},  # Too short
        )

        assert response.status_code == 422  # Validation error


class TestPasswordResetSingleUse:
    """Tests for single-use token enforcement."""

    def test_token_invalidated_after_use(
        self,
        client: TestClient,
        db_session: Session,
        fake_redis: FakeRedis,
    ) -> None:
        """Test that token is invalidated after successful reset."""
        from app.core.security import create_password_reset_token

        user = create_test_user(db_session, email="single_use@example.com")
        token, jti = create_password_reset_token(user.id, user.email)

        # Store JTI in Redis
        cache_key = f"reset:{jti}"
        fake_redis._store[cache_key] = '{"used": false}'

        # First reset should succeed
        response = client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "firstpassword123"},
        )
        assert response.status_code == 200

        # JTI should be removed from Redis
        assert cache_key not in fake_redis._store

        # Second attempt should fail
        response = client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "secondpassword456"},
        )
        assert response.status_code == 400


class TestPasswordResetCacheInvalidation:
    """Tests for cache invalidation after password reset."""

    def test_user_cache_invalidated_after_reset(
        self,
        client: TestClient,
        db_session: Session,
        fake_redis: FakeRedis,
    ) -> None:
        """Test that user cache is cleared after password reset."""
        from app.core.security import create_password_reset_token
        from app.schemas import UserCacheData

        user = create_test_user(db_session, email="cache_reset@example.com")

        # Pre-populate user cache
        user_cache_key = f"user:{user.id}"
        cache_data = UserCacheData(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            avatar_url=None,
            is_active=True,
            is_verified=True,
            role="user",
        )
        fake_redis._store[user_cache_key] = cache_data.model_dump_json()

        # Create reset token
        token, jti = create_password_reset_token(user.id, user.email)
        fake_redis._store[f"reset:{jti}"] = '{"used": false}'

        # Reset password
        response = client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "newpassword123"},
        )
        assert response.status_code == 200

        # User cache should be invalidated
        assert user_cache_key not in fake_redis._store


class TestPasswordResetTokenValidation:
    """Tests for the token validation endpoint."""

    def test_validate_valid_token(
        self,
        client: TestClient,
        db_session: Session,
        fake_redis: FakeRedis,
    ) -> None:
        """Test validating a valid unused token."""
        from app.core.security import create_password_reset_token

        user = create_test_user(db_session, email="validate@example.com")
        token, jti = create_password_reset_token(user.id, user.email)
        fake_redis._store[f"reset:{jti}"] = '{"used": false}'

        response = client.get(f"/api/auth/reset-password?token={token}")

        assert response.status_code == 200
        assert "valid" in response.json()["message"].lower()

    def test_validate_invalid_token(
        self,
        client: TestClient,
    ) -> None:
        """Test validating an invalid token."""
        response = client.get("/api/auth/reset-password?token=invalid")

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()


class TestLoginWithNewPassword:
    """Tests for logging in after password reset."""

    def test_can_login_with_new_password(
        self,
        client: TestClient,
        db_session: Session,
        fake_redis: FakeRedis,
    ) -> None:
        """Test that user can login with new password after reset."""
        from app.core.security import create_password_reset_token

        user = create_test_user(
            db_session,
            email="login_after_reset@example.com",
            password="oldpassword123",
        )

        # Reset password
        token, jti = create_password_reset_token(user.id, user.email)
        fake_redis._store[f"reset:{jti}"] = '{"used": false}'

        client.post(
            "/api/auth/reset-password",
            json={"token": token, "new_password": "newpassword456"},
        )

        # Login with new password should succeed
        response = client.post(
            "/api/auth/login",
            data={
                "username": user.email,
                "password": "newpassword456",
            },
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

        # Login with old password should fail
        response = client.post(
            "/api/auth/login",
            data={
                "username": user.email,
                "password": "oldpassword123",
            },
        )
        assert response.status_code == 401
