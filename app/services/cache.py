# app/services/cache.py
"""
Redis cache service for user data caching.

This module provides Redis JSON get/set/delete wrappers with TTL support.
Used primarily for caching authenticated user data to reduce database load.

Functions handle Redis connection errors gracefully, allowing the application
to continue functioning (with cache misses) when Redis is unavailable.

Cache key conventions:
- User data: "user:{user_id}"
- Password reset tokens: "reset:{jti}"
"""

import json
import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def get_cached_json(redis_client: Any, key: str) -> dict[str, Any] | None:
    """
    Get a JSON value from Redis cache.

    Args:
        redis_client: Async Redis client instance.
        key: The cache key to retrieve.

    Returns:
        The parsed JSON data as a dictionary, or None if:
        - Key doesn't exist
        - Redis is unavailable
        - Data is malformed

    Note:
        Errors are logged but not raised - cache misses are expected.
    """
    if redis_client is None:
        return None

    try:
        data = await redis_client.get(key)
        if data is None:
            return None
        return json.loads(data)
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in cache for key {key}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Redis error getting key {key}: {e}")
        return None


async def set_cached_json(
    redis_client: Any,
    key: str,
    value: dict[str, Any],
    ttl_seconds: int | None = None,
) -> bool:
    """
    Set a JSON value in Redis cache with optional TTL.

    Args:
        redis_client: Async Redis client instance.
        key: The cache key to set.
        value: Dictionary to serialize and store.
        ttl_seconds: Optional time-to-live in seconds.
                    If None, uses default USER_CACHE_TTL.

    Returns:
        True if successfully cached, False otherwise.

    Note:
        Errors are logged but not raised - caching is best-effort.
    """
    if redis_client is None:
        return False

    if ttl_seconds is None:
        ttl_seconds = settings.user_cache_ttl

    try:
        json_data = json.dumps(value)
        if ttl_seconds > 0:
            await redis_client.setex(key, ttl_seconds, json_data)
        else:
            await redis_client.set(key, json_data)
        logger.debug(f"Cached key {key} with TTL {ttl_seconds}s")
        return True
    except Exception as e:
        logger.warning(f"Redis error setting key {key}: {e}")
        return False


async def delete_cached(redis_client: Any, key: str) -> bool:
    """
    Delete a key from Redis cache.

    Args:
        redis_client: Async Redis client instance.
        key: The cache key to delete.

    Returns:
        True if key was deleted (or didn't exist), False on error.

    Note:
        Errors are logged but not raised.
    """
    if redis_client is None:
        return False

    try:
        await redis_client.delete(key)
        logger.debug(f"Deleted cache key {key}")
        return True
    except Exception as e:
        logger.warning(f"Redis error deleting key {key}: {e}")
        return False


async def exists_in_cache(redis_client: Any, key: str) -> bool:
    """
    Check if a key exists in Redis cache.

    Args:
        redis_client: Async Redis client instance.
        key: The cache key to check.

    Returns:
        True if key exists, False if not or on error.
    """
    if redis_client is None:
        return False

    try:
        return await redis_client.exists(key) > 0
    except Exception as e:
        logger.warning(f"Redis error checking key {key}: {e}")
        return False


def get_user_cache_key(user_id: int) -> str:
    """
    Generate the cache key for user data.

    Args:
        user_id: The user's database ID.

    Returns:
        Cache key string in format "user:{user_id}".
    """
    return f"user:{user_id}"


def get_reset_token_cache_key(jti: str) -> str:
    """
    Generate the cache key for password reset token tracking.

    Args:
        jti: The unique token identifier (JWT ID).

    Returns:
        Cache key string in format "reset:{jti}".
    """
    return f"reset:{jti}"
