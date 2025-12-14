# tests/test_cache_current_user.py
"""
Tests for Redis caching of authenticated user data.

This module tests:
- Cache hit behavior (user loaded from Redis)
- Cache miss behavior (user loaded from DB, then cached)
- Cache invalidation after user changes
- Graceful degradation when Redis is unavailable
"""

import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas import UserCacheData
from tests.conftest import (
    FakeRedis,
    create_test_user,
    get_auth_headers,
)


class TestUserCacheHitMiss:
    """Tests for cache hit and miss scenarios."""

    def test_cache_miss_loads_from_db_and_caches(
        self,
        client: TestClient,
        db_session: Session,
        fake_redis: FakeRedis,
    ) -> None:
        """Test that cache miss loads user from DB and stores in Redis."""
        # Create verified user
        user = create_test_user(db_session, email="cache_test@example.com")
        headers = get_auth_headers(user)

        # Ensure cache is empty
        fake_redis.clear()

        # Make request - should be a cache miss
        response = client.get("/api/users/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "cache_test@example.com"

        # Verify user was cached
        cache_key = f"user:{user.id}"
        cached_data = fake_redis._store.get(cache_key)
        assert cached_data is not None

        # Verify cached data structure
        cached_user = json.loads(cached_data)
        assert cached_user["id"] == user.id
        assert cached_user["email"] == user.email
        assert "hashed_password" not in cached_user

    def test_cache_hit_returns_user(
        self,
        client: TestClient,
        db_session: Session,
        fake_redis: FakeRedis,
    ) -> None:
        """Test that cache hit returns user without DB query."""
        # Create verified user
        user = create_test_user(db_session, email="cached_user@example.com")
        headers = get_auth_headers(user)

        # Pre-populate cache
        cache_key = f"user:{user.id}"
        cache_data = UserCacheData(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            is_active=True,
            is_verified=True,
            role="user",
        )
        fake_redis._store[cache_key] = cache_data.model_dump_json()

        # Make request - should be a cache hit
        response = client.get("/api/users/me", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "cached_user@example.com"

    def test_cache_stores_safe_fields_only(
        self,
        client: TestClient,
        db_session: Session,
        fake_redis: FakeRedis,
    ) -> None:
        """Test that cache does not store sensitive fields like password hash."""
        user = create_test_user(db_session, email="safe_cache@example.com")
        headers = get_auth_headers(user)

        fake_redis.clear()

        # Make request to populate cache
        response = client.get("/api/users/me", headers=headers)
        assert response.status_code == 200

        # Check cached data doesn't contain password
        cache_key = f"user:{user.id}"
        cached_data = json.loads(fake_redis._store[cache_key])

        assert "hashed_password" not in cached_data
        assert "password" not in cached_data
        # Should contain safe fields
        assert "id" in cached_data
        assert "email" in cached_data
        assert "role" in cached_data


class TestCacheInvalidation:
    """Tests for cache invalidation scenarios."""

    def test_cache_invalidated_on_email_verification(
        self,
        client: TestClient,
        db_session: Session,
        fake_redis: FakeRedis,
    ) -> None:
        """Test that cache is invalidated after email verification."""
        from app.core.security import create_email_verification_token

        # Create unverified user
        user = create_test_user(
            db_session,
            email="verify_cache@example.com",
            is_verified=False,
        )

        # Pre-populate cache with unverified status
        cache_key = f"user:{user.id}"
        cache_data = UserCacheData(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            avatar_url=None,
            is_active=True,
            is_verified=False,
            role="user",
        )
        fake_redis._store[cache_key] = cache_data.model_dump_json()

        # Verify email
        token = create_email_verification_token(user.email)
        response = client.get(f"/api/auth/verify?token={token}")
        assert response.status_code == 200

        # Cache should be invalidated
        assert cache_key not in fake_redis._store


class TestCacheGracefulDegradation:
    """Tests for behavior when Redis is unavailable."""

    def test_works_without_redis(
        self,
        db_session: Session,
    ) -> None:
        """Test that authentication works when Redis is None."""
        from fastapi.testclient import TestClient as TC

        from app.main import app as test_app

        # Create user
        user = create_test_user(db_session, email="no_redis@example.com")
        headers = get_auth_headers(user)

        # Set Redis to None
        original_redis = getattr(test_app.state, "redis", None)
        test_app.state.redis = None

        try:
            with TC(test_app) as tc:
                response = tc.get("/api/users/me", headers=headers)
                # Should work without Redis
                assert response.status_code == 200
                assert response.json()["email"] == "no_redis@example.com"
        finally:
            test_app.state.redis = original_redis


class TestCacheWithInactiveUser:
    """Tests for cache behavior with inactive users."""

    def test_cached_inactive_user_rejected(
        self,
        client: TestClient,
        db_session: Session,
        fake_redis: FakeRedis,
    ) -> None:
        """Test that cached inactive user is still rejected."""
        # Create user (will be made inactive in cache)
        user = create_test_user(db_session, email="inactive_cache@example.com")
        headers = get_auth_headers(user)

        # Pre-populate cache with inactive status
        cache_key = f"user:{user.id}"
        cache_data = UserCacheData(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            avatar_url=None,
            is_active=False,  # Marked as inactive
            is_verified=True,
            role="user",
        )
        fake_redis._store[cache_key] = cache_data.model_dump_json()

        # Request should be rejected
        response = client.get("/api/users/me", headers=headers)
        assert response.status_code == 401
        assert "inactive" in response.json()["detail"].lower()
