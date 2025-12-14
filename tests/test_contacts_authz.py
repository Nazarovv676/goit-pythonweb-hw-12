# tests/test_contacts_authz.py
"""Tests for contact authorization - ensuring users can only access their own contacts."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import crud
from app.db import get_session
from app.main import app
from app.models import Base
from app.schemas import ContactCreate, UserCreate

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
def user_a_data():
    """User A registration data."""
    return {
        "email": "user_a@example.com",
        "password": "password_a_123",
        "full_name": "User A",
    }


@pytest.fixture
def user_b_data():
    """User B registration data."""
    return {
        "email": "user_b@example.com",
        "password": "password_b_123",
        "full_name": "User B",
    }


@pytest.fixture
def contact_data():
    """Sample contact data."""
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "+1234567890",
        "birthday": "1990-05-15",
        "notes": "Test contact",
    }


def create_verified_user_and_get_token(client, db_session, user_data):
    """Helper to create a verified user and get their token."""
    with patch(
        "app.routers.auth.send_verification_email", new_callable=AsyncMock
    ):
        client.post("/api/auth/register", json=user_data)

    # Verify user
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
    return response.json()["access_token"]


class TestContactOwnership:
    """Tests for contact ownership and isolation."""

    def test_user_can_create_contact(
        self, client, db_session, user_a_data, contact_data
    ):
        """Test that authenticated user can create a contact."""
        token = create_verified_user_and_get_token(client, db_session, user_a_data)

        response = client.post(
            "/api/contacts",
            json=contact_data,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == contact_data["first_name"]
        assert data["email"] == contact_data["email"]
        assert "user_id" in data

    def test_user_can_read_own_contact(
        self, client, db_session, user_a_data, contact_data
    ):
        """Test that user can read their own contact."""
        token = create_verified_user_and_get_token(client, db_session, user_a_data)

        # Create contact
        create_response = client.post(
            "/api/contacts",
            json=contact_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        contact_id = create_response.json()["id"]

        # Read contact
        response = client.get(
            f"/api/contacts/{contact_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["id"] == contact_id

    def test_user_cannot_read_others_contact(
        self, client, db_session, user_a_data, user_b_data, contact_data
    ):
        """Test that user B cannot read user A's contact."""
        # Create user A and their contact
        token_a = create_verified_user_and_get_token(client, db_session, user_a_data)
        create_response = client.post(
            "/api/contacts",
            json=contact_data,
            headers={"Authorization": f"Bearer {token_a}"},
        )
        contact_id = create_response.json()["id"]

        # Create user B
        token_b = create_verified_user_and_get_token(client, db_session, user_b_data)

        # User B tries to read user A's contact
        response = client.get(
            f"/api/contacts/{contact_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )

        # Should return 404 (not 403, to not reveal existence)
        assert response.status_code == 404

    def test_user_cannot_update_others_contact(
        self, client, db_session, user_a_data, user_b_data, contact_data
    ):
        """Test that user B cannot update user A's contact."""
        # Create user A and their contact
        token_a = create_verified_user_and_get_token(client, db_session, user_a_data)
        create_response = client.post(
            "/api/contacts",
            json=contact_data,
            headers={"Authorization": f"Bearer {token_a}"},
        )
        contact_id = create_response.json()["id"]

        # Create user B
        token_b = create_verified_user_and_get_token(client, db_session, user_b_data)

        # User B tries to update user A's contact
        response = client.patch(
            f"/api/contacts/{contact_id}",
            json={"notes": "Hacked!"},
            headers={"Authorization": f"Bearer {token_b}"},
        )

        assert response.status_code == 404

    def test_user_cannot_delete_others_contact(
        self, client, db_session, user_a_data, user_b_data, contact_data
    ):
        """Test that user B cannot delete user A's contact."""
        # Create user A and their contact
        token_a = create_verified_user_and_get_token(client, db_session, user_a_data)
        create_response = client.post(
            "/api/contacts",
            json=contact_data,
            headers={"Authorization": f"Bearer {token_a}"},
        )
        contact_id = create_response.json()["id"]

        # Create user B
        token_b = create_verified_user_and_get_token(client, db_session, user_b_data)

        # User B tries to delete user A's contact
        response = client.delete(
            f"/api/contacts/{contact_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )

        assert response.status_code == 404

        # Verify contact still exists for user A
        verify_response = client.get(
            f"/api/contacts/{contact_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert verify_response.status_code == 200

    def test_user_list_only_shows_own_contacts(
        self, client, db_session, user_a_data, user_b_data
    ):
        """Test that listing contacts only shows user's own contacts."""
        # Create user A with 2 contacts
        token_a = create_verified_user_and_get_token(client, db_session, user_a_data)
        client.post(
            "/api/contacts",
            json={
                "first_name": "Contact",
                "last_name": "One",
                "email": "contact1@example.com",
                "phone": "+1111111111",
                "birthday": "1990-01-01",
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )
        client.post(
            "/api/contacts",
            json={
                "first_name": "Contact",
                "last_name": "Two",
                "email": "contact2@example.com",
                "phone": "+2222222222",
                "birthday": "1990-02-02",
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )

        # Create user B with 1 contact
        token_b = create_verified_user_and_get_token(client, db_session, user_b_data)
        client.post(
            "/api/contacts",
            json={
                "first_name": "Contact",
                "last_name": "Three",
                "email": "contact3@example.com",
                "phone": "+3333333333",
                "birthday": "1990-03-03",
            },
            headers={"Authorization": f"Bearer {token_b}"},
        )

        # User A should see 2 contacts
        response_a = client.get(
            "/api/contacts",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert response_a.status_code == 200
        assert response_a.json()["total"] == 2

        # User B should see 1 contact
        response_b = client.get(
            "/api/contacts",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert response_b.status_code == 200
        assert response_b.json()["total"] == 1
        assert response_b.json()["items"][0]["last_name"] == "Three"


class TestContactCRUD:
    """Tests for contact CRUD operations by owner."""

    def test_owner_can_update_contact(
        self, client, db_session, user_a_data, contact_data
    ):
        """Test that owner can update their contact."""
        token = create_verified_user_and_get_token(client, db_session, user_a_data)

        # Create contact
        create_response = client.post(
            "/api/contacts",
            json=contact_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        contact_id = create_response.json()["id"]

        # Update contact
        response = client.patch(
            f"/api/contacts/{contact_id}",
            json={"notes": "Updated notes"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["notes"] == "Updated notes"

    def test_owner_can_delete_contact(
        self, client, db_session, user_a_data, contact_data
    ):
        """Test that owner can delete their contact."""
        token = create_verified_user_and_get_token(client, db_session, user_a_data)

        # Create contact
        create_response = client.post(
            "/api/contacts",
            json=contact_data,
            headers={"Authorization": f"Bearer {token}"},
        )
        contact_id = create_response.json()["id"]

        # Delete contact
        response = client.delete(
            f"/api/contacts/{contact_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

        # Verify contact is deleted
        get_response = client.get(
            f"/api/contacts/{contact_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_response.status_code == 404

    def test_contact_requires_authentication(self, client):
        """Test that contact endpoints require authentication."""
        # Try to list contacts without token
        response = client.get("/api/contacts")
        assert response.status_code == 401

        # Try to create contact without token
        response = client.post(
            "/api/contacts",
            json={
                "first_name": "Test",
                "last_name": "Test",
                "email": "test@test.com",
                "phone": "+1234567890",
                "birthday": "1990-01-01",
            },
        )
        assert response.status_code == 401


class TestGlobalEmailUniqueness:
    """Tests for globally unique contact emails."""

    def test_different_users_cannot_create_contacts_with_same_email(
        self, client, db_session, user_a_data, user_b_data, contact_data
    ):
        """Test that contact emails are globally unique."""
        # User A creates contact
        token_a = create_verified_user_and_get_token(client, db_session, user_a_data)
        response_a = client.post(
            "/api/contacts",
            json=contact_data,
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert response_a.status_code == 201

        # User B tries to create contact with same email
        token_b = create_verified_user_and_get_token(client, db_session, user_b_data)
        response_b = client.post(
            "/api/contacts",
            json=contact_data,
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert response_b.status_code == 409

