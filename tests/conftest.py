# tests/conftest.py
"""
Pytest fixtures and configuration for testing the Contacts API.

This module provides:
- In-memory SQLite database setup for isolated tests
- Test client with dependency overrides
- User factories for creating test users
- Redis mock for caching tests
- Authentication helpers

All fixtures are function-scoped to ensure test isolation.
"""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, get_password_hash
from app.db import get_session
from app.main import app
from app.models import Base, User, UserRole

# Use SQLite for tests (in-memory)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_session() -> Generator[Session, None, None]:
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


class FakeRedis:
    """
    Fake Redis client for testing.

    Provides an in-memory dictionary-based implementation of the
    async Redis interface used by the application.
    """

    def __init__(self) -> None:
        """Initialize fake Redis with empty store."""
        self._store: dict[str, str] = {}
        self._ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        """Get value by key."""
        return self._store.get(key)

    async def set(self, key: str, value: str) -> None:
        """Set value without expiration."""
        self._store[key] = value

    async def setex(self, key: str, ttl: int, value: str) -> None:
        """Set value with expiration (TTL stored but not enforced in tests)."""
        self._store[key] = value
        self._ttls[key] = ttl

    async def delete(self, key: str) -> int:
        """Delete key and return count of deleted keys."""
        if key in self._store:
            del self._store[key]
            self._ttls.pop(key, None)
            return 1
        return 0

    async def exists(self, key: str) -> int:
        """Check if key exists."""
        return 1 if key in self._store else 0

    async def ping(self) -> bool:
        """Health check."""
        return True

    async def close(self) -> None:
        """Close connection (no-op for fake)."""
        pass

    def clear(self) -> None:
        """Clear all stored data."""
        self._store.clear()
        self._ttls.clear()


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def fake_redis() -> FakeRedis:
    """Create a fake Redis client for testing."""
    return FakeRedis()


@pytest.fixture(scope="function")
def client(
    db_session: Session, fake_redis: FakeRedis
) -> Generator[TestClient, None, None]:
    """Create a test client with fresh database and fake Redis."""
    from app.routers import users as users_router

    Base.metadata.create_all(bind=engine)

    # Inject fake Redis into app state
    app.state.redis = fake_redis

    # Reset rate limiter storage to prevent 429 errors between tests
    # The limiter uses in-memory storage by default
    if hasattr(users_router.limiter, "_storage"):
        users_router.limiter._storage.reset()
    if hasattr(app.state, "limiter") and hasattr(app.state.limiter, "_storage"):
        app.state.limiter._storage.reset()

    yield TestClient(app)

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def user_data() -> dict[str, Any]:
    """Sample user registration data."""
    return {
        "email": "test@example.com",
        "password": "securepassword123",
        "full_name": "Test User",
    }


@pytest.fixture
def admin_user_data() -> dict[str, Any]:
    """Sample admin user data."""
    return {
        "email": "admin@example.com",
        "password": "adminpassword123",
        "full_name": "Admin User",
    }


@pytest.fixture
def contact_data() -> dict[str, Any]:
    """Sample contact data."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "+1234567890",
        "birthday": "1990-05-15",
        "notes": "Test contact",
    }


def create_test_user(
    session: Session,
    email: str = "test@example.com",
    password: str = "testpassword123",
    full_name: str = "Test User",
    is_verified: bool = True,
    role: UserRole = UserRole.USER,
) -> User:
    """
    Create a test user directly in the database.

    Args:
        session: Database session.
        email: User email address.
        password: Plain text password (will be hashed).
        full_name: User's display name.
        is_verified: Whether email is verified.
        role: User role (USER or ADMIN).

    Returns:
        The created User object.
    """
    user = User(
        email=email.lower(),
        hashed_password=get_password_hash(password),
        full_name=full_name,
        is_active=True,
        is_verified=is_verified,
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_auth_token(user: User) -> str:
    """
    Generate an access token for a user.

    Args:
        user: The user to generate token for.

    Returns:
        JWT access token string.
    """
    return create_access_token(data={"sub": user.id, "email": user.email})


def get_auth_headers(user: User) -> dict[str, str]:
    """
    Get Authorization headers for a user.

    Args:
        user: The user to authenticate as.

    Returns:
        Dictionary with Authorization header.
    """
    token = get_auth_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def verified_user(db_session: Session) -> User:
    """Create a verified regular user."""
    return create_test_user(
        db_session,
        email="verified@example.com",
        password="verifiedpass123",
        is_verified=True,
        role=UserRole.USER,
    )


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Create a verified admin user."""
    return create_test_user(
        db_session,
        email="admin@example.com",
        password="adminpass123",
        is_verified=True,
        role=UserRole.ADMIN,
    )


@pytest.fixture
def unverified_user(db_session: Session) -> User:
    """Create an unverified user."""
    return create_test_user(
        db_session,
        email="unverified@example.com",
        password="unverifiedpass123",
        is_verified=False,
        role=UserRole.USER,
    )


@pytest.fixture
def mock_send_email() -> Generator[AsyncMock, None, None]:
    """Mock email sending functions."""
    with (
        patch(
            "app.routers.auth.send_verification_email", new_callable=AsyncMock
        ) as mock_verification,
        patch("app.routers.auth.send_password_reset_email", new_callable=AsyncMock),
    ):
        yield mock_verification
