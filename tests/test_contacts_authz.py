# tests/test_contacts_authz.py
"""Tests for contact authorization - ensuring users can only access their own contacts."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import create_test_user, get_auth_headers


class TestContactOwnership:
    """Tests for contact ownership and isolation."""

    def test_user_can_create_contact(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that authenticated user can create a contact."""
        user = create_test_user(db_session, email="create_contact@example.com")
        headers = get_auth_headers(user)

        contact_data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone": "+1234567890",
            "birthday": "1990-05-15",
        }

        response = client.post(
            "/api/contacts",
            json=contact_data,
            headers=headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["first_name"] == contact_data["first_name"]
        assert data["email"] == contact_data["email"]
        assert "user_id" in data

    def test_user_can_read_own_contact(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that user can read their own contact."""
        user = create_test_user(db_session, email="read_own@example.com")
        headers = get_auth_headers(user)

        # Create contact
        create_response = client.post(
            "/api/contacts",
            json={
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane.smith@example.com",
                "phone": "+1234567890",
                "birthday": "1985-03-20",
            },
            headers=headers,
        )
        contact_id = create_response.json()["id"]

        # Read contact
        response = client.get(
            f"/api/contacts/{contact_id}",
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["id"] == contact_id

    def test_user_cannot_read_others_contact(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that user B cannot read user A's contact."""
        # Create user A and their contact
        user_a = create_test_user(db_session, email="user_a_read@example.com")
        headers_a = get_auth_headers(user_a)

        create_response = client.post(
            "/api/contacts",
            json={
                "first_name": "Private",
                "last_name": "Contact",
                "email": "private@example.com",
                "phone": "+1234567890",
                "birthday": "1990-01-01",
            },
            headers=headers_a,
        )
        contact_id = create_response.json()["id"]

        # Create user B
        user_b = create_test_user(db_session, email="user_b_read@example.com")
        headers_b = get_auth_headers(user_b)

        # User B tries to read user A's contact
        response = client.get(
            f"/api/contacts/{contact_id}",
            headers=headers_b,
        )

        # Should return 404 (not 403, to not reveal existence)
        assert response.status_code == 404

    def test_user_cannot_update_others_contact(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that user B cannot update user A's contact."""
        user_a = create_test_user(db_session, email="user_a_update@example.com")
        headers_a = get_auth_headers(user_a)

        create_response = client.post(
            "/api/contacts",
            json={
                "first_name": "Protected",
                "last_name": "Contact",
                "email": "protected@example.com",
                "phone": "+1234567890",
                "birthday": "1990-01-01",
            },
            headers=headers_a,
        )
        contact_id = create_response.json()["id"]

        user_b = create_test_user(db_session, email="user_b_update@example.com")
        headers_b = get_auth_headers(user_b)

        # User B tries to update user A's contact
        response = client.patch(
            f"/api/contacts/{contact_id}",
            json={"notes": "Hacked!"},
            headers=headers_b,
        )

        assert response.status_code == 404

    def test_user_cannot_delete_others_contact(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that user B cannot delete user A's contact."""
        user_a = create_test_user(db_session, email="user_a_delete@example.com")
        headers_a = get_auth_headers(user_a)

        create_response = client.post(
            "/api/contacts",
            json={
                "first_name": "Permanent",
                "last_name": "Contact",
                "email": "permanent@example.com",
                "phone": "+1234567890",
                "birthday": "1990-01-01",
            },
            headers=headers_a,
        )
        contact_id = create_response.json()["id"]

        user_b = create_test_user(db_session, email="user_b_delete@example.com")
        headers_b = get_auth_headers(user_b)

        # User B tries to delete user A's contact
        response = client.delete(
            f"/api/contacts/{contact_id}",
            headers=headers_b,
        )

        assert response.status_code == 404

        # Verify contact still exists for user A
        verify_response = client.get(
            f"/api/contacts/{contact_id}",
            headers=headers_a,
        )
        assert verify_response.status_code == 200

    def test_user_list_only_shows_own_contacts(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that listing contacts only shows user's own contacts."""
        # Create user A with 2 contacts
        user_a = create_test_user(db_session, email="user_a_list@example.com")
        headers_a = get_auth_headers(user_a)

        client.post(
            "/api/contacts",
            json={
                "first_name": "Contact",
                "last_name": "One",
                "email": "contact1_list@example.com",
                "phone": "+1111111111",
                "birthday": "1990-01-01",
            },
            headers=headers_a,
        )
        client.post(
            "/api/contacts",
            json={
                "first_name": "Contact",
                "last_name": "Two",
                "email": "contact2_list@example.com",
                "phone": "+2222222222",
                "birthday": "1990-02-02",
            },
            headers=headers_a,
        )

        # Create user B with 1 contact
        user_b = create_test_user(db_session, email="user_b_list@example.com")
        headers_b = get_auth_headers(user_b)

        client.post(
            "/api/contacts",
            json={
                "first_name": "Contact",
                "last_name": "Three",
                "email": "contact3_list@example.com",
                "phone": "+3333333333",
                "birthday": "1990-03-03",
            },
            headers=headers_b,
        )

        # User A should see 2 contacts
        response_a = client.get("/api/contacts", headers=headers_a)
        assert response_a.status_code == 200
        assert response_a.json()["total"] == 2

        # User B should see 1 contact
        response_b = client.get("/api/contacts", headers=headers_b)
        assert response_b.status_code == 200
        assert response_b.json()["total"] == 1
        assert response_b.json()["items"][0]["last_name"] == "Three"


class TestContactCRUD:
    """Tests for contact CRUD operations by owner."""

    def test_owner_can_update_contact(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that owner can update their contact."""
        user = create_test_user(db_session, email="owner_update@example.com")
        headers = get_auth_headers(user)

        create_response = client.post(
            "/api/contacts",
            json={
                "first_name": "Update",
                "last_name": "Me",
                "email": "update_me@example.com",
                "phone": "+1234567890",
                "birthday": "1990-01-01",
            },
            headers=headers,
        )
        contact_id = create_response.json()["id"]

        response = client.patch(
            f"/api/contacts/{contact_id}",
            json={"notes": "Updated notes"},
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["notes"] == "Updated notes"

    def test_owner_can_delete_contact(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that owner can delete their contact."""
        user = create_test_user(db_session, email="owner_delete@example.com")
        headers = get_auth_headers(user)

        create_response = client.post(
            "/api/contacts",
            json={
                "first_name": "Delete",
                "last_name": "Me",
                "email": "delete_me@example.com",
                "phone": "+1234567890",
                "birthday": "1990-01-01",
            },
            headers=headers,
        )
        contact_id = create_response.json()["id"]

        response = client.delete(
            f"/api/contacts/{contact_id}",
            headers=headers,
        )

        assert response.status_code == 200

        # Verify contact is deleted
        get_response = client.get(
            f"/api/contacts/{contact_id}",
            headers=headers,
        )
        assert get_response.status_code == 404

    def test_contact_requires_authentication(self, client: TestClient) -> None:
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
                "email": "auth_test@example.com",
                "phone": "+1234567890",
                "birthday": "1990-01-01",
            },
        )
        assert response.status_code == 401


class TestGlobalEmailUniqueness:
    """Tests for globally unique contact emails."""

    def test_different_users_cannot_create_contacts_with_same_email(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Test that contact emails are globally unique."""
        user_a = create_test_user(db_session, email="user_a_unique@example.com")
        headers_a = get_auth_headers(user_a)

        response_a = client.post(
            "/api/contacts",
            json={
                "first_name": "Unique",
                "last_name": "Contact",
                "email": "unique_contact@example.com",
                "phone": "+1234567890",
                "birthday": "1990-01-01",
            },
            headers=headers_a,
        )
        assert response_a.status_code == 201

        user_b = create_test_user(db_session, email="user_b_unique@example.com")
        headers_b = get_auth_headers(user_b)

        response_b = client.post(
            "/api/contacts",
            json={
                "first_name": "Duplicate",
                "last_name": "Email",
                "email": "unique_contact@example.com",  # Same email
                "phone": "+0987654321",
                "birthday": "1990-01-01",
            },
            headers=headers_b,
        )
        assert response_b.status_code == 409
