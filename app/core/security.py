# app/core/security.py
"""
Security utilities for password hashing and JWT handling.

This module provides cryptographic utilities for:
- Password hashing and verification using bcrypt
- JWT access token creation and validation
- Email verification token generation and validation
- Password reset token generation and validation using itsdangerous

All token operations use the application's configured secrets and algorithms.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.

    Uses bcrypt for secure password verification.

    Args:
        plain_password: The plaintext password to verify.
        hashed_password: The bcrypt-hashed password to compare against.

    Returns:
        True if passwords match, False otherwise.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.

    Uses the bcrypt algorithm with automatic salt generation.

    Args:
        password: The plaintext password to hash.

    Returns:
        The bcrypt-hashed password string.
    """
    return pwd_context.hash(password)


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT access token.

    Creates a signed JWT token containing the provided data with an
    expiration time. Used for authentication.

    Args:
        data: Dictionary of claims to include in the token.
              Typically includes 'sub' (user ID) and 'email'.
        expires_delta: Optional custom expiration time delta.
                      Defaults to ACCESS_TOKEN_EXPIRE_MINUTES from settings.

    Returns:
        Encoded JWT token string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.access_token_expire_minutes
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    """
    Decode and validate a JWT access token.

    Verifies the token signature and expiration.

    Args:
        token: The JWT token string to decode.

    Returns:
        The decoded token payload as a dictionary, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"verify_sub": False},  # We use int for sub, not string
        )
        return payload
    except JWTError:
        return None


def create_email_verification_token(email: str) -> str:
    """
    Create a JWT token for email verification.

    Generates a time-limited token containing the user's email address.
    Used for verifying email ownership during registration.

    Args:
        email: The email address to verify.

    Returns:
        Encoded JWT verification token string.
    """
    expire = datetime.now(UTC) + timedelta(
        hours=settings.verification_token_expire_hours
    )
    to_encode = {"sub": email, "exp": expire, "type": "email_verification"}
    return jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def verify_email_token(token: str) -> str | None:
    """
    Verify an email verification token and return the email.

    Validates the token signature, expiration, and type.

    Args:
        token: The verification token to validate.

    Returns:
        The email address from the token, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        if payload.get("type") != "email_verification":
            return None
        return payload.get("sub")
    except JWTError:
        return None


# Password Reset Token Helpers using itsdangerous
_password_reset_serializer = URLSafeTimedSerializer(
    settings.password_reset_secret, salt="pwd-reset"
)


def create_password_reset_token(user_id: int, email: str) -> tuple[str, str]:
    """
    Create a password reset token using itsdangerous URLSafeTimedSerializer.

    Generates a time-limited signed token containing user identification
    and a unique JTI (JWT ID) for single-use semantics.

    Args:
        user_id: The user's database ID.
        email: The user's email address.

    Returns:
        A tuple of (token, jti) where:
        - token: The signed URL-safe token string.
        - jti: The unique token identifier for Redis tracking.
    """
    jti = str(uuid4())
    payload = {
        "sub": user_id,
        "email": email,
        "jti": jti,
        "iat": datetime.now(UTC).isoformat(),
    }
    token = _password_reset_serializer.dumps(payload)
    return token, jti


def verify_password_reset_token(
    token: str, max_age_seconds: int | None = None
) -> dict[str, Any] | None:
    """
    Verify a password reset token and return the payload.

    Validates the token signature and checks expiration based on max_age.

    Args:
        token: The password reset token to verify.
        max_age_seconds: Maximum age of the token in seconds.
                        Defaults to PASSWORD_RESET_EXPIRE_MINUTES * 60.

    Returns:
        The decoded payload containing 'sub', 'email', 'jti', 'iat',
        or None if the token is invalid or expired.
    """
    if max_age_seconds is None:
        max_age_seconds = settings.password_reset_expire_minutes * 60

    try:
        payload = _password_reset_serializer.loads(token, max_age=max_age_seconds)
        return payload
    except SignatureExpired:
        return None
    except BadSignature:
        return None
