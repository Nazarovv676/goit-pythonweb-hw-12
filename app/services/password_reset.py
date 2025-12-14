# app/services/password_reset.py
"""
Password reset service for token management.

This module handles password reset token lifecycle:
- Token creation with JTI for single-use semantics
- Token validation with expiration checking
- Redis-based token invalidation tracking

Security features:
- Tokens are signed using itsdangerous URLSafeTimedSerializer
- Separate secret from main JWT secret
- Single-use enforcement via Redis JTI tracking
- Configurable expiration time
"""

import logging
from typing import Any

from app.core.config import get_settings
from app.core.security import create_password_reset_token, verify_password_reset_token
from app.services.cache import (
    delete_cached,
    exists_in_cache,
    get_reset_token_cache_key,
    set_cached_json,
)

logger = logging.getLogger(__name__)
settings = get_settings()


async def create_reset_token(
    redis_client: Any, user_id: int, email: str
) -> tuple[str, str]:
    """
    Create a password reset token and store JTI in Redis.

    Creates a signed token containing user information and a unique
    JTI (JWT ID). The JTI is stored in Redis to enforce single-use
    semantics.

    Args:
        redis_client: Async Redis client for JTI tracking.
        user_id: The user's database ID.
        email: The user's email address.

    Returns:
        A tuple of (token, jti) where:
        - token: The URL-safe reset token to include in email.
        - jti: The unique identifier stored in Redis.

    Note:
        If Redis is unavailable, token is still created but
        single-use enforcement won't work (server restart clears JTIs).
    """
    token, jti = create_password_reset_token(user_id, email)

    # Store JTI in Redis for single-use tracking
    cache_key = get_reset_token_cache_key(jti)
    ttl_seconds = settings.password_reset_expire_minutes * 60

    await set_cached_json(
        redis_client,
        cache_key,
        {"user_id": user_id, "email": email, "used": False},
        ttl_seconds,
    )

    logger.info(f"Created password reset token for user {user_id}")
    return token, jti


async def validate_reset_token(redis_client: Any, token: str) -> dict[str, Any] | None:
    """
    Validate a password reset token and check if it's been used.

    Performs the following checks:
    1. Token signature is valid
    2. Token hasn't expired
    3. JTI exists in Redis (hasn't been invalidated)
    4. Token hasn't already been used

    Args:
        redis_client: Async Redis client for JTI checking.
        token: The password reset token to validate.

    Returns:
        The token payload dict if valid, containing:
        - sub: User ID
        - email: User email
        - jti: Token identifier
        - iat: Issue timestamp

        Returns None if token is invalid, expired, or already used.
    """
    # Verify token signature and expiration
    payload = verify_password_reset_token(token)
    if payload is None:
        logger.warning("Invalid or expired password reset token")
        return None

    jti = payload.get("jti")
    if not jti:
        logger.warning("Password reset token missing JTI")
        return None

    # Check if JTI exists in Redis (not invalidated)
    cache_key = get_reset_token_cache_key(jti)

    if redis_client:
        if not await exists_in_cache(redis_client, cache_key):
            logger.warning(f"Password reset token {jti} not found or already used")
            return None

    return payload


async def invalidate_reset_token(redis_client: Any, jti: str) -> bool:
    """
    Invalidate a password reset token after use.

    Deletes the JTI from Redis to prevent token reuse.
    Should be called after successful password reset.

    Args:
        redis_client: Async Redis client.
        jti: The token's JTI to invalidate.

    Returns:
        True if successfully invalidated, False otherwise.
    """
    cache_key = get_reset_token_cache_key(jti)
    result = await delete_cached(redis_client, cache_key)

    if result:
        logger.info(f"Invalidated password reset token {jti}")
    else:
        logger.warning(f"Failed to invalidate password reset token {jti}")

    return result
