# tests/test_roles_avatar.py
"""
Tests for role-based access control and avatar upload restrictions.

This module tests:
- Admin users can upload avatars
- Regular users are forbidden from uploading avatars (403)
- Role enforcement on protected endpoints
- User role display in profile
"""

from io import BytesIO
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import UserRole
from tests.conftest import (
    FakeRedis,
    create_test_user,
    get_auth_headers,
)


class TestAvatarRoleEnforcement:
    """Tests for avatar upload role restrictions."""

    def test_admin_can_upload_avatar(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        """Test that admin users can upload avatars."""
        admin = create_test_user(
            db_session,
            email="avatar_admin@example.com",
            role=UserRole.ADMIN,
        )
        headers = get_auth_headers(admin)

        # Create a fake image file
        fake_image = BytesIO(b"fake image content")
        fake_image.name = "avatar.png"

        with patch(
            "app.routers.users.upload_avatar", new_callable=AsyncMock
        ) as mock_upload:
            mock_upload.return_value = "https://cloudinary.com/avatar.png"

            response = client.patch(
                "/api/users/me/avatar",
                headers=headers,
                files={"file": ("avatar.png", fake_image, "image/png")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["avatar_url"] == "https://cloudinary.com/avatar.png"
        mock_upload.assert_called_once()

    def test_regular_user_forbidden_from_avatar_upload(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        """Test that regular users get 403 when trying to upload avatar."""
        user = create_test_user(
            db_session,
            email="regular_user@example.com",
            role=UserRole.USER,
        )
        headers = get_auth_headers(user)

        # Create a fake image file
        fake_image = BytesIO(b"fake image content")

        response = client.patch(
            "/api/users/me/avatar",
            headers=headers,
            files={"file": ("avatar.png", fake_image, "image/png")},
        )

        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    def test_unverified_user_cannot_upload_avatar(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        """Test that unverified users cannot upload avatar."""
        user = create_test_user(
            db_session,
            email="unverified_avatar@example.com",
            role=UserRole.ADMIN,  # Even admin but unverified
            is_verified=False,
        )
        headers = get_auth_headers(user)

        fake_image = BytesIO(b"fake image content")

        response = client.patch(
            "/api/users/me/avatar",
            headers=headers,
            files={"file": ("avatar.png", fake_image, "image/png")},
        )

        # Should fail because unverified
        assert response.status_code == 401
        assert "verified" in response.json()["detail"].lower()

    def test_unauthenticated_cannot_upload_avatar(
        self,
        client: TestClient,
    ) -> None:
        """Test that unauthenticated requests are rejected."""
        fake_image = BytesIO(b"fake image content")

        response = client.patch(
            "/api/users/me/avatar",
            files={"file": ("avatar.png", fake_image, "image/png")},
        )

        assert response.status_code == 401


class TestRoleDisplay:
    """Tests for role display in user profile."""

    def test_user_role_shown_in_profile(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        """Test that user role is included in profile response."""
        user = create_test_user(
            db_session,
            email="role_display@example.com",
            role=UserRole.USER,
        )
        headers = get_auth_headers(user)

        response = client.get("/api/users/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "user"

    def test_admin_role_shown_in_profile(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        """Test that admin role is correctly shown in profile."""
        admin = create_test_user(
            db_session,
            email="admin_display@example.com",
            role=UserRole.ADMIN,
        )
        headers = get_auth_headers(admin)

        response = client.get("/api/users/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"


class TestNewUserDefaultRole:
    """Tests for default role on new user registration."""

    def test_new_user_has_user_role(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        """Test that newly registered users have 'user' role by default."""
        with patch("app.routers.auth.send_verification_email", new_callable=AsyncMock):
            response = client.post(
                "/api/auth/register",
                json={
                    "email": "newuser@example.com",
                    "password": "newpassword123",
                    "full_name": "New User",
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "user"


class TestAvatarCacheInvalidation:
    """Tests for cache invalidation after avatar update."""

    def test_cache_invalidated_after_avatar_change(
        self,
        client: TestClient,
        db_session: Session,
        fake_redis: FakeRedis,
    ) -> None:
        """Test that user cache is invalidated after avatar update."""
        from app.schemas import UserCacheData

        admin = create_test_user(
            db_session,
            email="cache_avatar@example.com",
            role=UserRole.ADMIN,
        )
        headers = get_auth_headers(admin)

        # Pre-populate cache
        cache_key = f"user:{admin.id}"
        cache_data = UserCacheData(
            id=admin.id,
            email=admin.email,
            full_name=admin.full_name,
            avatar_url=None,
            is_active=True,
            is_verified=True,
            role="admin",
        )
        fake_redis._store[cache_key] = cache_data.model_dump_json()

        # Upload avatar
        fake_image = BytesIO(b"fake image content")

        with patch(
            "app.routers.users.upload_avatar", new_callable=AsyncMock
        ) as mock_upload:
            mock_upload.return_value = "https://cloudinary.com/new_avatar.png"

            response = client.patch(
                "/api/users/me/avatar",
                headers=headers,
                files={"file": ("avatar.png", fake_image, "image/png")},
            )

        assert response.status_code == 200

        # Cache should be invalidated
        assert cache_key not in fake_redis._store


class TestAvatarValidation:
    """Tests for avatar file validation."""

    def test_invalid_file_type_rejected(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        """Test that non-image files are rejected."""
        admin = create_test_user(
            db_session,
            email="invalid_file@example.com",
            role=UserRole.ADMIN,
        )
        headers = get_auth_headers(admin)

        # Try to upload a text file
        fake_file = BytesIO(b"not an image")

        response = client.patch(
            "/api/users/me/avatar",
            headers=headers,
            files={"file": ("document.txt", fake_file, "text/plain")},
        )

        assert response.status_code == 400
        assert "invalid file type" in response.json()["detail"].lower()

    def test_file_size_limit_enforced(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        """Test that files over 5MB are rejected."""
        admin = create_test_user(
            db_session,
            email="large_file@example.com",
            role=UserRole.ADMIN,
        )
        headers = get_auth_headers(admin)

        # Create a file larger than 5MB
        large_content = b"x" * (6 * 1024 * 1024)  # 6MB
        large_file = BytesIO(large_content)

        response = client.patch(
            "/api/users/me/avatar",
            headers=headers,
            files={"file": ("large.png", large_file, "image/png")},
        )

        assert response.status_code == 400
        assert "too large" in response.json()["detail"].lower()


class TestContactsAccessWithRoles:
    """Tests verifying that roles don't affect contact access."""

    def test_admin_can_access_contacts(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        """Test that admin users can still access their contacts."""
        admin = create_test_user(
            db_session,
            email="admin_contacts@example.com",
            role=UserRole.ADMIN,
        )
        headers = get_auth_headers(admin)

        # Create a contact
        response = client.post(
            "/api/contacts",
            headers=headers,
            json={
                "first_name": "Contact",
                "last_name": "Person",
                "email": "contact@example.com",
                "phone": "+1234567890",
                "birthday": "1990-01-01",
            },
        )
        assert response.status_code == 201

        # List contacts
        response = client.get("/api/contacts", headers=headers)
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_regular_user_can_access_contacts(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        """Test that regular users can access their contacts."""
        user = create_test_user(
            db_session,
            email="user_contacts@example.com",
            role=UserRole.USER,
        )
        headers = get_auth_headers(user)

        # Create a contact
        response = client.post(
            "/api/contacts",
            headers=headers,
            json={
                "first_name": "Another",
                "last_name": "Contact",
                "email": "another@example.com",
                "phone": "+0987654321",
                "birthday": "1985-06-15",
            },
        )
        assert response.status_code == 201

        # List contacts
        response = client.get("/api/contacts", headers=headers)
        assert response.status_code == 200
        assert response.json()["total"] == 1
