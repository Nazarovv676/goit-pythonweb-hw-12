# app/schemas.py
"""
Pydantic v2 schemas for request/response validation.

This module defines all Pydantic models used for API request validation
and response serialization. Organized into sections:
- User schemas (registration, login, profile)
- Contact schemas (CRUD operations)
- Password reset schemas
- Generic response schemas

All schemas use Pydantic v2 syntax with ConfigDict and field_validator.
"""

import re
from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Phone number regex pattern
PHONE_PATTERN = re.compile(r"^\+?[0-9()\-.\s]{7,20}$")


# ============================================================================
# Role Enum
# ============================================================================


class Role(str, Enum):
    """
    User role enumeration for authorization.

    Used in API responses and for role-based access control.

    Attributes:
        USER: Standard user role with basic permissions.
        ADMIN: Administrator role with elevated permissions.
    """

    USER = "user"
    ADMIN = "admin"


# ============================================================================
# User Schemas
# ============================================================================


class UserCreate(BaseModel):
    """
    Schema for user registration.

    Validates the required fields for creating a new user account.

    Attributes:
        email: Valid email address, max 255 characters.
        password: Password string, 8-100 characters.
        full_name: Optional display name, max 255 characters.
    """

    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str | None = Field(None, max_length=255)


class UserRead(BaseModel):
    """
    Schema for reading user data (excludes password).

    Used for API responses containing user profile information.
    Never includes sensitive data like passwords.

    Attributes:
        id: User's unique identifier.
        email: User's email address.
        full_name: User's display name.
        avatar_url: URL to user's avatar image.
        is_active: Whether the account is active.
        is_verified: Whether email has been verified.
        role: User's role (user or admin).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None
    avatar_url: str | None
    is_active: bool
    is_verified: bool
    role: Role


class UserCacheData(BaseModel):
    """
    Schema for caching user data in Redis.

    Contains only safe, non-sensitive fields suitable for caching.
    Does not include password hashes or other sensitive data.

    Attributes:
        id: User's unique identifier.
        email: User's email address.
        full_name: User's display name.
        avatar_url: URL to user's avatar image.
        is_active: Whether the account is active.
        is_verified: Whether email has been verified.
        role: User's role (user or admin).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str | None
    avatar_url: str | None
    is_active: bool
    is_verified: bool
    role: Role


class UserLogin(BaseModel):
    """
    Schema for user login.

    Validates credentials provided during authentication.

    Attributes:
        email: User's email address.
        password: User's password (plaintext, will be verified against hash).
    """

    email: EmailStr
    password: str


class Token(BaseModel):
    """
    JWT token response schema.

    Returned after successful authentication.

    Attributes:
        access_token: The JWT access token string.
        token_type: Token type, always "bearer".
    """

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """
    JWT token payload schema.

    Represents the decoded contents of a JWT token.

    Attributes:
        sub: Subject (user ID).
        email: User's email address.
    """

    sub: int | None = None
    email: str | None = None


# ============================================================================
# Password Reset Schemas
# ============================================================================


class PasswordResetRequest(BaseModel):
    """
    Schema for requesting a password reset.

    User provides their email to receive a reset link.

    Attributes:
        email: Email address of the account to reset.
    """

    email: EmailStr


class PasswordReset(BaseModel):
    """
    Schema for completing a password reset.

    Contains the reset token and new password.

    Attributes:
        token: The password reset token from the email link.
        new_password: The new password to set (8-100 characters).
    """

    token: str
    new_password: str = Field(..., min_length=8, max_length=100)


# ============================================================================
# Contact Schemas
# ============================================================================


class ContactBase(BaseModel):
    """
    Base schema for contact data.

    Contains all common fields shared by create and read operations.

    Attributes:
        first_name: Contact's first name (1-255 chars).
        last_name: Contact's last name (1-255 chars).
        email: Contact's email address.
        phone: Phone number in flexible format.
        birthday: Date of birth (YYYY-MM-DD).
        notes: Optional additional notes.
    """

    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr = Field(..., max_length=255)
    phone: str = Field(..., min_length=7, max_length=50)
    birthday: date
    notes: str | None = Field(None, max_length=5000)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """
        Validate phone number format.

        Allows digits, spaces, parentheses, dots, dashes,
        and optional leading plus sign.

        Args:
            v: The phone number string to validate.

        Returns:
            The validated phone number.

        Raises:
            ValueError: If phone format is invalid.
        """
        if not PHONE_PATTERN.match(v):
            raise ValueError(
                "Phone must be 7-20 characters containing digits, "
                "spaces, parentheses, dots, dashes, and optional leading +"
            )
        return v


class ContactCreate(ContactBase):
    """
    Schema for creating a new contact.

    Inherits all fields from ContactBase.
    """

    pass


class ContactUpdate(BaseModel):
    """
    Schema for updating a contact (all fields optional for partial update).

    Allows partial updates where only provided fields are changed.

    Attributes:
        first_name: Optional new first name.
        last_name: Optional new last name.
        email: Optional new email address.
        phone: Optional new phone number.
        birthday: Optional new birthday.
        notes: Optional new notes.
    """

    first_name: str | None = Field(None, min_length=1, max_length=255)
    last_name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = Field(None, max_length=255)
    phone: str | None = Field(None, min_length=7, max_length=50)
    birthday: date | None = None
    notes: str | None = Field(None, max_length=5000)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """
        Validate phone number format if provided.

        Args:
            v: The phone number string to validate, or None.

        Returns:
            The validated phone number, or None.

        Raises:
            ValueError: If phone format is invalid.
        """
        if v is not None and not PHONE_PATTERN.match(v):
            raise ValueError(
                "Phone must be 7-20 characters containing digits, "
                "spaces, parentheses, dots, dashes, and optional leading +"
            )
        return v


class ContactRead(ContactBase):
    """
    Schema for reading contact data.

    Includes database-generated fields in addition to base fields.

    Attributes:
        id: Contact's unique identifier.
        user_id: ID of the owning user.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int


class ContactListResponse(BaseModel):
    """
    Paginated list response for contacts.

    Provides pagination metadata alongside the contact list.

    Attributes:
        items: List of contacts in current page.
        total: Total number of contacts matching query.
        limit: Maximum items per page.
        offset: Number of items skipped.
    """

    items: list[ContactRead]
    total: int
    limit: int
    offset: int


# ============================================================================
# Generic Schemas
# ============================================================================


class MessageResponse(BaseModel):
    """
    Generic message response.

    Used for simple success/info messages.

    Attributes:
        message: The message text.
    """

    message: str


class VerifyEmailRequest(BaseModel):
    """
    Request schema for email verification.

    Attributes:
        token: The email verification token from the link.
    """

    token: str
