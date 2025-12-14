# app/models.py
"""
SQLAlchemy 2.0 ORM models.

This module defines the database models for the Contacts API:
- User: Authentication, authorization, and profile management
- Contact: Contact information storage with user ownership

All models use SQLAlchemy 2.0 declarative mapping with type annotations.
"""

from datetime import date
from enum import Enum as PyEnum

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """
    Base class for all ORM models.

    Provides the declarative base for SQLAlchemy models. All models
    should inherit from this class.
    """

    pass


class UserRole(str, PyEnum):
    """
    Enumeration of user roles for authorization.

    Attributes:
        USER: Standard user with basic permissions.
        ADMIN: Administrator with elevated permissions (e.g., avatar upload).
    """

    USER = "user"
    ADMIN = "admin"


class User(Base):
    """
    User model for authentication and authorization.

    Represents a registered user in the system. Handles authentication
    credentials, profile information, and relationships to owned contacts.

    Attributes:
        id: Primary key, auto-incrementing integer.
        email: Unique email address, used for login.
        hashed_password: bcrypt-hashed password.
        full_name: Optional display name.
        avatar_url: Optional Cloudinary avatar URL.
        is_active: Account active status (can be disabled by admin).
        is_verified: Email verification status.
        role: User role for authorization (user or admin).
        contacts: Relationship to owned Contact records.

    Note:
        - Email must be verified before login is allowed.
        - Passwords are never stored in plaintext.
        - Only admins can update their avatar.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False),
        default=UserRole.USER,
        nullable=False,
    )

    # Relationships
    contacts: Mapped[list["Contact"]] = relationship(
        "Contact", back_populates="owner", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """Return string representation of User."""
        return f"<User(id={self.id}, email='{self.email}', role='{self.role.value}')>"


class Contact(Base):
    """
    Contact model representing a person's contact information.

    Stores contact details for a person, owned by a specific user.
    Each contact is isolated to its owner - users can only see/modify
    their own contacts.

    Attributes:
        id: Primary key, auto-incrementing integer.
        first_name: Contact's first name, indexed for search.
        last_name: Contact's last name, indexed for search.
        email: Contact's email address, globally unique.
        phone: Contact's phone number in flexible format.
        birthday: Contact's date of birth for birthday reminders.
        notes: Optional additional notes/comments.
        user_id: Foreign key to owning User.
        owner: Relationship to the owning User record.

    Note:
        Contact emails are globally unique across all users.
        This simplifies data integrity but may be changed if needed.
    """

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    phone: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    birthday: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Foreign key to User
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="contacts")

    __table_args__ = (Index("ix_contacts_birthday_month_day", birthday),)

    def __repr__(self) -> str:
        """Return string representation of Contact."""
        return f"<Contact(id={self.id}, email='{self.email}')>"
