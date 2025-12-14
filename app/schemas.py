# app/schemas.py
"""Pydantic v2 schemas for request/response validation."""

import re
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Phone number regex pattern
PHONE_PATTERN = re.compile(r"^\+?[0-9()\-.\s]{7,20}$")


# ============================================================================
# User Schemas
# ============================================================================


class UserCreate(BaseModel):
    """Schema for user registration."""

    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str | None = Field(None, max_length=255)


class UserRead(BaseModel):
    """Schema for reading user data (excludes password)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None
    avatar_url: str | None
    is_active: bool
    is_verified: bool


class UserLogin(BaseModel):
    """Schema for user login."""

    email: EmailStr
    password: str


class Token(BaseModel):
    """JWT token response schema."""

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT token payload schema."""

    sub: int | None = None
    email: str | None = None


# ============================================================================
# Contact Schemas
# ============================================================================


class ContactBase(BaseModel):
    """Base schema for contact data."""

    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr = Field(..., max_length=255)
    phone: str = Field(..., min_length=7, max_length=50)
    birthday: date
    notes: str | None = Field(None, max_length=5000)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Validate phone number format."""
        if not PHONE_PATTERN.match(v):
            raise ValueError(
                "Phone must be 7-20 characters containing digits, "
                "spaces, parentheses, dots, dashes, and optional leading +"
            )
        return v


class ContactCreate(ContactBase):
    """Schema for creating a new contact."""

    pass


class ContactUpdate(BaseModel):
    """Schema for updating a contact (all fields optional for partial update)."""

    first_name: str | None = Field(None, min_length=1, max_length=255)
    last_name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = Field(None, max_length=255)
    phone: str | None = Field(None, min_length=7, max_length=50)
    birthday: date | None = None
    notes: str | None = Field(None, max_length=5000)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        """Validate phone number format if provided."""
        if v is not None and not PHONE_PATTERN.match(v):
            raise ValueError(
                "Phone must be 7-20 characters containing digits, "
                "spaces, parentheses, dots, dashes, and optional leading +"
            )
        return v


class ContactRead(ContactBase):
    """Schema for reading contact data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int


class ContactListResponse(BaseModel):
    """Paginated list response for contacts."""

    items: list[ContactRead]
    total: int
    limit: int
    offset: int


# ============================================================================
# Generic Schemas
# ============================================================================


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class VerifyEmailRequest(BaseModel):
    """Request schema for email verification."""

    token: str
