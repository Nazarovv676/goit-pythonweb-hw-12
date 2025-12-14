# app/routers/contacts.py
"""
Contacts API router with CRUD and search endpoints, scoped to authenticated user.

This module provides endpoints for managing contacts:
- Create new contacts
- List contacts with search and pagination
- Get single contact by ID
- Full and partial contact updates
- Delete contacts
- Get upcoming birthdays

All endpoints are scoped to the authenticated user - users can only
access and modify their own contacts.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app import crud
from app.deps import CurrentVerifiedUser, DBSession, Pagination
from app.schemas import (
    ContactCreate,
    ContactListResponse,
    ContactRead,
    ContactUpdate,
    MessageResponse,
)

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post(
    "",
    response_model=ContactRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new contact",
    responses={
        409: {"description": "Contact with this email already exists"},
    },
)
def create_contact(
    data: ContactCreate,
    session: DBSession,
    current_user: CurrentVerifiedUser,
) -> ContactRead:
    """
    Create a new contact for the authenticated user.

    Creates a contact with the provided information and associates
    it with the current user. Contact emails must be globally unique.

    Args:
        data: Contact data including name, email, phone, birthday.
        session: Database session.
        current_user: The authenticated and verified user.

    Returns:
        The created contact with generated ID.

    Raises:
        HTTPException 409: If a contact with the given email already exists.
    """
    # Check for existing email (globally unique)
    existing = crud.get_contact_by_email(session, data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Contact with email '{data.email}' already exists",
        )

    try:
        contact = crud.create_contact(session, data, current_user.id)
        return ContactRead.model_validate(contact)
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact with this email already exists",
        ) from e


@router.get(
    "",
    response_model=ContactListResponse,
    summary="List contacts with optional filters",
)
def list_contacts(
    session: DBSession,
    current_user: CurrentVerifiedUser,
    pagination: Pagination,
    q: Annotated[
        str | None,
        Query(
            description="General search query (searches first_name, last_name, email with OR semantics)"
        ),
    ] = None,
    first_name: Annotated[
        str | None,
        Query(description="Filter by first name (case-insensitive, partial match)"),
    ] = None,
    last_name: Annotated[
        str | None,
        Query(description="Filter by last name (case-insensitive, partial match)"),
    ] = None,
    email: Annotated[
        str | None,
        Query(description="Filter by email (case-insensitive, partial match)"),
    ] = None,
) -> ContactListResponse:
    """
    List contacts for the authenticated user with optional filtering and pagination.

    Supports two search modes:
    - General search (`q` parameter): OR semantics across first_name, last_name, email
    - Field-specific search: AND semantics between provided fields

    All searches are case-insensitive partial matches (ILIKE).

    Args:
        session: Database session.
        current_user: The authenticated and verified user.
        pagination: Pagination parameters (limit, offset).
        q: General search query (optional).
        first_name: Filter by first name (optional).
        last_name: Filter by last name (optional).
        email: Filter by email (optional).

    Returns:
        Paginated list of contacts with total count.

    Note:
        Only returns contacts owned by the authenticated user.
    """
    contacts, total = crud.list_contacts(
        session,
        current_user.id,
        q=q,
        first_name=first_name,
        last_name=last_name,
        email=email,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return ContactListResponse(
        items=[ContactRead.model_validate(c) for c in contacts],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.get(
    "/upcoming-birthdays",
    response_model=list[ContactRead],
    summary="Get contacts with upcoming birthdays",
)
def get_upcoming_birthdays(
    session: DBSession,
    current_user: CurrentVerifiedUser,
    days: Annotated[
        int,
        Query(
            ge=1,
            le=365,
            description="Number of days to look ahead for birthdays",
        ),
    ] = 7,
) -> list[ContactRead]:
    """
    Get contacts whose birthdays fall within the next N days.

    Calculates each contact's "next birthday" considering year rollover:
    - If birthday has passed this year -> next year's occurrence
    - If not yet passed -> this year's occurrence

    Handles leap year birthdays (Feb 29) by treating them as Feb 28
    on non-leap years.

    Args:
        session: Database session.
        current_user: The authenticated and verified user.
        days: Number of days to look ahead (1-365, default: 7).

    Returns:
        List of contacts with upcoming birthdays, ordered by date.

    Note:
        Only returns contacts owned by the authenticated user.
    """
    contacts = crud.upcoming_birthdays(session, current_user.id, days=days)
    return [ContactRead.model_validate(c) for c in contacts]


@router.get(
    "/{contact_id}",
    response_model=ContactRead,
    summary="Get a contact by ID",
    responses={
        404: {"description": "Contact not found"},
    },
)
def get_contact(
    contact_id: int,
    session: DBSession,
    current_user: CurrentVerifiedUser,
) -> ContactRead:
    """
    Get a single contact by their ID.

    Only returns the contact if it exists and belongs to the current user.
    Returns 404 for both non-existent contacts and contacts belonging
    to other users (to prevent information leakage).

    Args:
        contact_id: The contact's database ID.
        session: Database session.
        current_user: The authenticated and verified user.

    Returns:
        The contact data.

    Raises:
        HTTPException 404: If contact not found or belongs to another user.
    """
    contact = crud.get_contact(session, contact_id, current_user.id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact with id {contact_id} not found",
        )
    return ContactRead.model_validate(contact)


@router.put(
    "/{contact_id}",
    response_model=ContactRead,
    summary="Full update of a contact",
    responses={
        404: {"description": "Contact not found"},
        409: {"description": "Email already exists"},
    },
)
def update_contact_full(
    contact_id: int,
    data: ContactCreate,
    session: DBSession,
    current_user: CurrentVerifiedUser,
) -> ContactRead:
    """
    Perform a full update of a contact (all fields required).

    Replaces all contact fields with the provided values.
    If changing email, validates that the new email is not already in use.

    Args:
        contact_id: The contact's database ID.
        data: Complete contact data for update.
        session: Database session.
        current_user: The authenticated and verified user.

    Returns:
        The updated contact data.

    Raises:
        HTTPException 404: If contact not found or belongs to another user.
        HTTPException 409: If new email is already used by another contact.
    """
    contact = crud.get_contact(session, contact_id, current_user.id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact with id {contact_id} not found",
        )

    # Check email uniqueness if email is changing
    if data.email.lower() != contact.email.lower():
        existing = crud.get_contact_by_email(session, data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Contact with email '{data.email}' already exists",
            )

    update_data = ContactUpdate(**data.model_dump())
    try:
        updated = crud.update_contact(session, contact, update_data)
        return ContactRead.model_validate(updated)
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        ) from e


@router.patch(
    "/{contact_id}",
    response_model=ContactRead,
    summary="Partial update of a contact",
    responses={
        404: {"description": "Contact not found"},
        409: {"description": "Email already exists"},
    },
)
def update_contact_partial(
    contact_id: int,
    data: ContactUpdate,
    session: DBSession,
    current_user: CurrentVerifiedUser,
) -> ContactRead:
    """
    Perform a partial update of a contact (only provided fields are updated).

    Updates only the fields that are explicitly provided in the request.
    If changing email, validates that the new email is not already in use.

    Args:
        contact_id: The contact's database ID.
        data: Partial contact data with fields to update.
        session: Database session.
        current_user: The authenticated and verified user.

    Returns:
        The updated contact data.

    Raises:
        HTTPException 404: If contact not found or belongs to another user.
        HTTPException 409: If new email is already used by another contact.
    """
    contact = crud.get_contact(session, contact_id, current_user.id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact with id {contact_id} not found",
        )

    # Check email uniqueness if email is changing
    if data.email is not None and data.email.lower() != contact.email.lower():
        existing = crud.get_contact_by_email(session, data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Contact with email '{data.email}' already exists",
            )

    try:
        updated = crud.update_contact(session, contact, data)
        return ContactRead.model_validate(updated)
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        ) from e


@router.delete(
    "/{contact_id}",
    response_model=MessageResponse,
    summary="Delete a contact",
    responses={
        404: {"description": "Contact not found"},
    },
)
def delete_contact(
    contact_id: int,
    session: DBSession,
    current_user: CurrentVerifiedUser,
) -> MessageResponse:
    """
    Delete a contact by their ID.

    Permanently removes the contact from the database.
    Only the owner can delete their contacts.

    Args:
        contact_id: The contact's database ID.
        session: Database session.
        current_user: The authenticated and verified user.

    Returns:
        Success message.

    Raises:
        HTTPException 404: If contact not found or belongs to another user.
    """
    contact = crud.get_contact(session, contact_id, current_user.id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact with id {contact_id} not found",
        )

    crud.delete_contact(session, contact)
    return MessageResponse(message=f"Contact with id {contact_id} deleted successfully")
