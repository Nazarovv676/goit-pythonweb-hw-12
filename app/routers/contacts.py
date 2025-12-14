# app/routers/contacts.py
"""Contacts API router with CRUD and search endpoints, scoped to authenticated user."""

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

    - **first_name**: Contact's first name
    - **last_name**: Contact's last name
    - **email**: Unique email address (globally unique)
    - **phone**: Phone number (format: +1234567890 or similar)
    - **birthday**: Date of birth (YYYY-MM-DD)
    - **notes**: Optional additional notes
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

    **Search behavior:**
    - If `q` is provided: searches first_name OR last_name OR email (OR semantics)
    - If individual fields (first_name, last_name, email) are provided without `q`:
      uses AND semantics
    - All searches are case-insensitive partial matches (ILIKE)

    **Pagination:**
    - `limit`: Maximum items to return (1-100, default: 20)
    - `offset`: Number of items to skip (default: 0)

    **Note:** Only returns contacts owned by the authenticated user.
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

    The endpoint calculates each contact's "next birthday" considering:
    - If birthday month/day already passed this year → next year
    - If not yet passed → this year

    **Leap year handling:**
    - Feb 29 birthdays are treated as Feb 28 on non-leap years

    **Parameters:**
    - `days`: Number of days to look ahead (1-365, default: 7)

    Returns contacts ordered by their upcoming birthday date.
    **Note:** Only returns contacts owned by the authenticated user.
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

    Returns 404 if the contact doesn't exist or belongs to another user.
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

    Returns 404 if the contact doesn't exist or belongs to another user.
    Returns 409 if the new email is already used by another contact.
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

    Returns 404 if the contact doesn't exist or belongs to another user.
    Returns 409 if the new email is already used by another contact.
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

    Returns 404 if the contact doesn't exist or belongs to another user.
    """
    contact = crud.get_contact(session, contact_id, current_user.id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact with id {contact_id} not found",
        )

    crud.delete_contact(session, contact)
    return MessageResponse(message=f"Contact with id {contact_id} deleted successfully")
