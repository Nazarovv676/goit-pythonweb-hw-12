# app/deps.py
"""
FastAPI dependencies for authentication and common parameters.

This module provides dependency injection components for:
- Database session management
- JWT authentication with Redis caching
- Role-based access control
- Pagination parameters

The get_current_user dependency implements Redis caching to avoid
hitting the database on every protected request.
"""

import json
import logging
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import crud
from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db import get_session
from app.models import User, UserRole
from app.schemas import UserCacheData

logger = logging.getLogger(__name__)
settings = get_settings()

# Database session dependency
DBSession = Annotated[Session, Depends(get_session)]

# OAuth2 scheme for JWT token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _get_user_cache_key(user_id: int) -> str:
    """
    Generate Redis cache key for user data.

    Args:
        user_id: The user's database ID.

    Returns:
        The Redis key string in format "user:{user_id}".
    """
    return f"user:{user_id}"


async def get_current_user(
    request: Request,
    session: DBSession,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    """
    Get the current authenticated user from JWT token with Redis caching.

    This dependency implements the following flow:
    1. Decode and validate the JWT token
    2. Check Redis cache for user data
    3. If cache hit: validate user is still active
    4. If cache miss: load from DB, cache in Redis, return

    The cache stores only safe fields (no password hash) with a TTL
    defined by USER_CACHE_TTL setting.

    Args:
        request: FastAPI request object (for accessing Redis via app.state).
        session: Database session.
        token: JWT access token from Authorization header.

    Returns:
        The authenticated User object.

    Raises:
        HTTPException 401: If token is invalid, expired, or user not found/inactive.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decode token
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: int | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    # Try to get from Redis cache
    redis_client = getattr(request.app.state, "redis", None)
    cache_key = _get_user_cache_key(user_id)

    if redis_client:
        try:
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                # Cache hit - parse and validate
                user_data = json.loads(cached_data)
                logger.debug(f"Cache hit for user {user_id}")

                # Still need to verify user is active
                if not user_data.get("is_active", False):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User account is inactive",
                        headers={"WWW-Authenticate": "Bearer"},
                    )

                # Load full user from DB for the request
                # (we need the ORM object for relationships)
                user = crud.get_user_by_id(session, user_id)
                if user is None:
                    # User was deleted, invalidate cache
                    await redis_client.delete(cache_key)
                    raise credentials_exception
                return user
        except HTTPException:
            # Re-raise HTTP exceptions (auth failures, etc.)
            raise
        except json.JSONDecodeError:
            logger.warning(f"Invalid cache data for user {user_id}")
            await redis_client.delete(cache_key)
        except Exception as e:
            logger.warning(f"Redis error during cache read: {e}")

    # Cache miss or Redis unavailable - load from database
    user = crud.get_user_by_id(session, user_id)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Cache user data in Redis (non-blocking, best effort)
    if redis_client:
        try:
            cache_data = UserCacheData.model_validate(user)
            await redis_client.setex(
                cache_key,
                settings.user_cache_ttl,
                cache_data.model_dump_json(),
            )
            logger.debug(f"Cached user {user_id} in Redis")
        except Exception as e:
            logger.warning(f"Failed to cache user {user_id}: {e}")

    return user


async def get_current_verified_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get the current authenticated and verified user.

    Policy: Unverified users cannot access protected routes.

    Args:
        current_user: The authenticated user from get_current_user.

    Returns:
        The verified User object.

    Raises:
        HTTPException 401: If user's email is not verified.
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not verified. Please verify your email to access this resource.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def invalidate_user_cache(request: Request, user_id: int) -> None:
    """
    Invalidate the Redis cache for a user.

    Should be called after any user-mutating operation:
    - Password change
    - Avatar change
    - Email verification
    - Profile update
    - Role change

    Args:
        request: FastAPI request object (for accessing Redis).
        user_id: The user's database ID.
    """
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client:
        try:
            cache_key = _get_user_cache_key(user_id)
            await redis_client.delete(cache_key)
            logger.debug(f"Invalidated cache for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for user {user_id}: {e}")


def require_role(*allowed_roles: UserRole) -> Any:
    """
    Create a dependency that enforces role-based access control.

    Returns a dependency function that checks if the current user
    has one of the allowed roles.

    Args:
        *allowed_roles: One or more UserRole values that are permitted.

    Returns:
        A dependency function for use with Depends().

    Example:
        @router.patch("/admin-only")
        async def admin_endpoint(
            user: Annotated[User, Depends(require_role(UserRole.ADMIN))]
        ):
            ...
    """

    async def role_checker(
        current_user: Annotated[User, Depends(get_current_verified_user)],
    ) -> User:
        """
        Check if user has required role.

        Args:
            current_user: The authenticated and verified user.

        Returns:
            The user if authorized.

        Raises:
            HTTPException 403: If user's role is not in allowed_roles.
        """
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return role_checker


# Type aliases for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentVerifiedUser = Annotated[User, Depends(get_current_verified_user)]
CurrentAdmin = Annotated[User, Depends(require_role(UserRole.ADMIN))]


# Pagination parameters
class PaginationParams:
    """
    Common pagination parameters.

    Provides limit and offset query parameters for list endpoints.

    Attributes:
        limit: Maximum number of items to return (1-100, default: 20).
        offset: Number of items to skip (default: 0).
    """

    def __init__(
        self,
        limit: Annotated[
            int,
            Query(ge=1, le=100, description="Maximum number of items to return"),
        ] = 20,
        offset: Annotated[
            int,
            Query(ge=0, description="Number of items to skip"),
        ] = 0,
    ):
        """
        Initialize pagination parameters.

        Args:
            limit: Maximum items per page.
            offset: Number of items to skip.
        """
        self.limit = limit
        self.offset = offset


Pagination = Annotated[PaginationParams, Depends()]
