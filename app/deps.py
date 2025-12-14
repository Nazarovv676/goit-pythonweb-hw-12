# app/deps.py
"""FastAPI dependencies for authentication and common parameters."""

from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app import crud
from app.core.security import decode_access_token
from app.db import get_session
from app.models import User

# Database session dependency
DBSession = Annotated[Session, Depends(get_session)]

# OAuth2 scheme for JWT token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    session: DBSession,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    """
    Get the current authenticated user from JWT token.

    Raises:
        HTTPException 401: If token is invalid, expired, or user not found/inactive
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: int | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    user = crud.get_user_by_id(session, user_id)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_verified_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get the current authenticated and verified user.

    Policy: Unverified users cannot access protected routes.

    Raises:
        HTTPException 401: If user is not verified
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not verified. Please verify your email to access this resource.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


# Type aliases for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentVerifiedUser = Annotated[User, Depends(get_current_verified_user)]


# Pagination parameters
class PaginationParams:
    """Common pagination parameters."""

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
        self.limit = limit
        self.offset = offset


Pagination = Annotated[PaginationParams, Depends()]
