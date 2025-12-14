# app/crud.py
"""
CRUD operations for users and contacts - pure data access layer.

This module provides database operations separated from business logic.
All functions accept a SQLAlchemy Session and operate on the database.

Functions are organized into sections:
- User CRUD Operations
- Contact CRUD Operations
- Utility functions (birthday calculations)

Note:
    This module should not contain HTTP-specific logic or caching.
    Caching is handled at the dependency injection level.
"""

from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models import Contact, User, UserRole
from app.schemas import ContactCreate, ContactUpdate, UserCreate

# ============================================================================
# User CRUD Operations
# ============================================================================


def create_user(session: Session, data: UserCreate) -> User:
    """
    Create a new user with hashed password.

    Normalizes email to lowercase and hashes the password using bcrypt.

    Args:
        session: Database session.
        data: User registration data containing email, password, and optional name.

    Returns:
        The created User object with generated ID.

    Note:
        The user is added to the session and flushed, but not committed.
        Commit is handled by the session context manager.
    """
    user = User(
        email=data.email.lower(),
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        is_active=True,
        is_verified=False,
        role=UserRole.USER,
    )
    session.add(user)
    session.flush()
    return user


def get_user_by_id(session: Session, user_id: int) -> User | None:
    """
    Get a user by ID.

    Args:
        session: Database session.
        user_id: The user's database ID.

    Returns:
        The User object if found, None otherwise.
    """
    stmt = select(User).where(User.id == user_id)
    return session.execute(stmt).scalar_one_or_none()


def get_user_by_email(session: Session, email: str) -> User | None:
    """
    Get a user by email (case-insensitive).

    Args:
        session: Database session.
        email: The email address to search for.

    Returns:
        The User object if found, None otherwise.
    """
    stmt = select(User).where(func.lower(User.email) == func.lower(email))
    return session.execute(stmt).scalar_one_or_none()


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    """
    Authenticate a user by email and password.

    Verifies the password against the stored bcrypt hash.

    Args:
        session: Database session.
        email: User's email address.
        password: Plaintext password to verify.

    Returns:
        The User object if authentication succeeds, None otherwise.
    """
    user = get_user_by_email(session, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def verify_user_email(session: Session, email: str) -> User | None:
    """
    Mark a user's email as verified.

    Args:
        session: Database session.
        email: The email address of the user to verify.

    Returns:
        The updated User object, or None if user not found.
    """
    user = get_user_by_email(session, email)
    if user:
        user.is_verified = True
        session.flush()
    return user


def update_user_avatar(session: Session, user: User, avatar_url: str) -> User:
    """
    Update user's avatar URL.

    Args:
        session: Database session.
        user: The User object to update.
        avatar_url: New Cloudinary avatar URL.

    Returns:
        The updated User object.
    """
    user.avatar_url = avatar_url
    session.flush()
    return user


def update_user_password(session: Session, user: User, new_password: str) -> User:
    """
    Update user's password.

    Hashes the new password with bcrypt before storing.

    Args:
        session: Database session.
        user: The User object to update.
        new_password: New plaintext password (will be hashed).

    Returns:
        The updated User object.

    Note:
        Caller should invalidate user cache after this operation.
    """
    user.hashed_password = get_password_hash(new_password)
    session.flush()
    return user


def update_user_role(session: Session, user: User, role: UserRole) -> User:
    """
    Update user's role.

    Args:
        session: Database session.
        user: The User object to update.
        role: New role (UserRole.USER or UserRole.ADMIN).

    Returns:
        The updated User object.
    """
    user.role = role
    session.flush()
    return user


# ============================================================================
# Contact CRUD Operations
# ============================================================================


def create_contact(session: Session, data: ContactCreate, user_id: int) -> Contact:
    """
    Create a new contact for a specific user.

    Args:
        session: Database session.
        data: Contact data containing all required fields.
        user_id: ID of the owning user.

    Returns:
        The created Contact object with generated ID.
    """
    contact = Contact(
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        phone=data.phone,
        birthday=data.birthday,
        notes=data.notes,
        user_id=user_id,
    )
    session.add(contact)
    session.flush()
    return contact


def get_contact(session: Session, contact_id: int, user_id: int) -> Contact | None:
    """
    Get a contact by ID, scoped to a specific user.

    Ensures users can only access their own contacts.

    Args:
        session: Database session.
        contact_id: The contact's database ID.
        user_id: ID of the requesting user.

    Returns:
        The Contact object if found and owned by user, None otherwise.
    """
    stmt = select(Contact).where(Contact.id == contact_id, Contact.user_id == user_id)
    return session.execute(stmt).scalar_one_or_none()


def get_contact_by_email(session: Session, email: str) -> Contact | None:
    """
    Get a contact by email (globally unique).

    Args:
        session: Database session.
        email: The contact's email address.

    Returns:
        The Contact object if found, None otherwise.
    """
    stmt = select(Contact).where(func.lower(Contact.email) == func.lower(email))
    return session.execute(stmt).scalar_one_or_none()


def list_contacts(
    session: Session,
    user_id: int,
    *,
    q: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Contact], int]:
    """
    List contacts with optional filters and pagination, scoped to a specific user.

    Search behavior:
    - If 'q' is provided: searches first_name OR last_name OR email (OR semantics)
    - If individual fields are provided without 'q': uses AND semantics
    - All searches are case-insensitive using ILIKE

    Args:
        session: Database session.
        user_id: ID of the requesting user.
        q: General search query (optional).
        first_name: Filter by first name (optional).
        last_name: Filter by last name (optional).
        email: Filter by email (optional).
        limit: Maximum number of results (default: 20).
        offset: Number of results to skip (default: 0).

    Returns:
        Tuple of (contacts list, total count).
    """
    stmt = select(Contact).where(Contact.user_id == user_id)
    count_stmt = select(func.count(Contact.id)).where(Contact.user_id == user_id)

    # Build filter conditions
    if q:
        # General search: OR semantics across first_name, last_name, email
        search_pattern = f"%{q}%"
        or_conditions = or_(
            Contact.first_name.ilike(search_pattern),
            Contact.last_name.ilike(search_pattern),
            Contact.email.ilike(search_pattern),
        )
        stmt = stmt.where(or_conditions)
        count_stmt = count_stmt.where(or_conditions)
    else:
        # Individual field filters: AND semantics
        conditions = []
        if first_name:
            conditions.append(Contact.first_name.ilike(f"%{first_name}%"))
        if last_name:
            conditions.append(Contact.last_name.ilike(f"%{last_name}%"))
        if email:
            conditions.append(Contact.email.ilike(f"%{email}%"))

        if conditions:
            for condition in conditions:
                stmt = stmt.where(condition)
                count_stmt = count_stmt.where(condition)

    # Get total count
    total = session.execute(count_stmt).scalar() or 0

    # Apply pagination and ordering
    stmt = stmt.order_by(Contact.id).offset(offset).limit(limit)
    contacts = list(session.execute(stmt).scalars().all())

    return contacts, total


def update_contact(session: Session, contact: Contact, data: ContactUpdate) -> Contact:
    """
    Update an existing contact with provided fields.

    Only updates fields that are explicitly set in the update data.

    Args:
        session: Database session.
        contact: The Contact object to update.
        data: Update data with optional fields.

    Returns:
        The updated Contact object.
    """
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact, field, value)
    session.flush()
    return contact


def delete_contact(session: Session, contact: Contact) -> None:
    """
    Delete a contact.

    Args:
        session: Database session.
        contact: The Contact object to delete.
    """
    session.delete(contact)
    session.flush()


def upcoming_birthdays(
    session: Session,
    user_id: int,
    days: int = 7,
    today: date | None = None,
) -> list[Contact]:
    """
    Get contacts with birthdays in the next N days, scoped to a specific user.

    This function computes each contact's "next birthday" considering year rollover:
    - If the birthday (month/day) has already passed this year, the next birthday
      is next year
    - Otherwise, it's this year

    For leap year birthdays (Feb 29):
    - On non-leap years, Feb 29 birthdays are treated as Feb 28

    Args:
        session: Database session.
        user_id: ID of the user whose contacts to search.
        days: Number of days to look ahead (default: 7, range: 1-365).
        today: Reference date (default: current date in UTC).

    Returns:
        List of contacts with upcoming birthdays, ordered by their next birthday date.
    """
    if today is None:
        today = date.today()

    end_date = today + timedelta(days=days)

    # Fetch user's contacts and filter in Python for accurate year rollover handling
    stmt = select(Contact).where(Contact.user_id == user_id)
    all_contacts = list(session.execute(stmt).scalars().all())

    result = []
    for contact in all_contacts:
        next_bday = _get_next_birthday(contact.birthday, today)
        if today <= next_bday <= end_date:
            result.append((next_bday, contact))

    # Sort by next birthday date
    result.sort(key=lambda x: x[0])
    return [contact for _, contact in result]


def _get_next_birthday(birthday: date, reference_date: date) -> date:
    """
    Calculate the next occurrence of a birthday relative to reference_date.

    Handles leap year edge case: Feb 29 birthdays become Feb 28 on non-leap years.

    Args:
        birthday: The original birthday date.
        reference_date: The date to compare against.

    Returns:
        The next occurrence of the birthday.
    """
    this_year = reference_date.year

    # Try to create birthday this year
    try:
        bday_this_year = birthday.replace(year=this_year)
    except ValueError:
        # Feb 29 on non-leap year -> use Feb 28
        bday_this_year = date(this_year, 2, 28)

    if bday_this_year >= reference_date:
        return bday_this_year

    # Birthday already passed this year, use next year
    next_year = this_year + 1
    try:
        return birthday.replace(year=next_year)
    except ValueError:
        # Feb 29 on non-leap year -> use Feb 28
        return date(next_year, 2, 28)
