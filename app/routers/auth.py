# app/routers/auth.py
"""
Authentication router for registration, login, email verification, and password reset.

This module provides endpoints for:
- User registration with email verification
- Login to obtain JWT access tokens
- Email verification using signed tokens
- Password reset request and completion

Security notes:
- Passwords are hashed with bcrypt before storage
- Email verification required before login
- Password reset uses separate signed tokens with single-use semantics
- Response messages avoid leaking user existence information
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError

from app import crud
from app.core.security import create_access_token, verify_email_token
from app.deps import DBSession, invalidate_user_cache
from app.schemas import (
    MessageResponse,
    PasswordReset,
    PasswordResetRequest,
    Token,
    UserCreate,
    UserRead,
)
from app.services.email import send_password_reset_email, send_verification_email
from app.services.password_reset import (
    create_reset_token,
    invalidate_reset_token,
    validate_reset_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={
        409: {"description": "Email already registered"},
    },
)
async def register(
    data: UserCreate,
    session: DBSession,
    background_tasks: BackgroundTasks,
    request: Request,
) -> UserRead:
    """
    Register a new user account.

    Creates a new user with hashed password and sends a verification email.
    Users must verify their email before logging in.

    Args:
        data: User registration data (email, password, optional name).
        session: Database session.
        background_tasks: Background task queue for email sending.
        request: HTTP request for base URL extraction.

    Returns:
        The created user profile (without sensitive fields).

    Raises:
        HTTPException 409: If email is already registered.
    """
    # Check for existing user
    existing = crud.get_user_by_email(session, data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    try:
        user = crud.create_user(session, data)

        # Get base URL for verification link
        base_url = str(request.base_url).rstrip("/")

        # Send verification email in background
        background_tasks.add_task(send_verification_email, user.email, base_url)

        return UserRead.model_validate(user)
    except IntegrityError as e:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from e


@router.get(
    "/verify",
    response_model=MessageResponse,
    summary="Verify email address",
    responses={
        400: {"description": "Invalid or expired verification token"},
    },
)
async def verify_email(
    token: str,
    session: DBSession,
    request: Request,
) -> MessageResponse:
    """
    Verify a user's email address using the token from the verification email.

    Token must be valid and not expired. Marks user as verified upon success.
    Invalidates user cache after verification.

    Args:
        token: Email verification token from the email link.
        session: Database session.
        request: HTTP request for cache invalidation.

    Returns:
        Success message.

    Raises:
        HTTPException 400: If token is invalid, expired, or user not found.
    """
    email = verify_email_token(token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    user = crud.verify_user_email(session, email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    # Invalidate user cache after verification status change
    await invalidate_user_cache(request, user.id)

    return MessageResponse(message="Email verified successfully")


@router.post(
    "/login",
    response_model=Token,
    summary="Login to get access token",
    responses={
        401: {"description": "Invalid credentials or email not verified"},
    },
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: DBSession,
) -> Token:
    """
    Authenticate user and return JWT access token.

    Requires valid email and password. Email must be verified to obtain tokens.
    Use the returned token as: `Authorization: Bearer <access_token>`

    Args:
        form_data: OAuth2 form with username (email) and password.
        session: Database session.

    Returns:
        JWT access token and token type.

    Raises:
        HTTPException 401: If credentials invalid, email not verified, or account inactive.
    """
    user = crud.authenticate_user(session, form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not verified. Please check your inbox for verification email.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.id, "email": user.email})

    return Token(access_token=access_token, token_type="bearer")


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="Resend verification email",
)
async def resend_verification(
    email: str,
    session: DBSession,
    background_tasks: BackgroundTasks,
    request: Request,
) -> MessageResponse:
    """
    Resend the verification email to a user.

    Useful if the original email was lost or expired.
    Returns same message regardless of whether email exists (security).

    Args:
        email: Email address to send verification to.
        session: Database session.
        background_tasks: Background task queue.
        request: HTTP request for base URL.

    Returns:
        Generic message (doesn't reveal if email exists).
    """
    user = crud.get_user_by_email(session, email)

    if not user:
        # Don't reveal if email exists or not for security
        return MessageResponse(
            message="If the email exists, a verification link will be sent"
        )

    if user.is_verified:
        return MessageResponse(message="Email is already verified")

    base_url = str(request.base_url).rstrip("/")
    background_tasks.add_task(send_verification_email, user.email, base_url)

    return MessageResponse(
        message="If the email exists, a verification link will be sent"
    )


@router.post(
    "/request-password-reset",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MessageResponse,
    summary="Request a password reset",
)
async def request_password_reset(
    data: PasswordResetRequest,
    session: DBSession,
    background_tasks: BackgroundTasks,
    request: Request,
) -> MessageResponse:
    """
    Request a password reset email.

    Generates a time-limited reset token and emails it to the user.
    Always returns 202 to avoid user enumeration attacks.

    Args:
        data: Request containing the user's email.
        session: Database session.
        background_tasks: Background task queue for email sending.
        request: HTTP request for base URL and Redis access.

    Returns:
        Generic acceptance message (doesn't reveal if email exists).

    Note:
        - Token expires after PASSWORD_RESET_EXPIRE_MINUTES
        - Token can only be used once
        - If user doesn't exist, no email is sent but same response returned
    """
    user = crud.get_user_by_email(session, data.email)

    # Always return 202 to prevent user enumeration
    if not user:
        return MessageResponse(
            message="If the email exists, a password reset link will be sent"
        )

    # Generate reset token and store JTI in Redis
    redis_client = getattr(request.app.state, "redis", None)
    token, _jti = await create_reset_token(redis_client, user.id, user.email)

    # Send password reset email in background
    base_url = str(request.base_url).rstrip("/")
    background_tasks.add_task(send_password_reset_email, user.email, token, base_url)

    return MessageResponse(
        message="If the email exists, a password reset link will be sent"
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset password with token",
    responses={
        400: {"description": "Invalid or expired token"},
    },
)
async def reset_password(
    data: PasswordReset,
    session: DBSession,
    request: Request,
) -> MessageResponse:
    """
    Complete password reset using the token from email.

    Validates the reset token, updates the password, and invalidates
    the token and user cache.

    Args:
        data: Reset data containing token and new password.
        session: Database session.
        request: HTTP request for Redis access.

    Returns:
        Success message.

    Raises:
        HTTPException 400: If token is invalid, expired, already used, or user not found.
    """
    redis_client = getattr(request.app.state, "redis", None)

    # Validate token
    payload = await validate_reset_token(redis_client, data.token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    user_id = payload.get("sub")
    jti = payload.get("jti")

    if not user_id or not jti:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid password reset token",
        )

    # Get user and update password
    user = crud.get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found",
        )

    # Update password
    crud.update_user_password(session, user, data.new_password)

    # Invalidate the reset token (single-use)
    await invalidate_reset_token(redis_client, jti)

    # Invalidate user cache
    await invalidate_user_cache(request, user.id)

    return MessageResponse(message="Password reset successfully")


@router.get(
    "/reset-password",
    response_model=MessageResponse,
    summary="Validate password reset token",
    responses={
        400: {"description": "Invalid or expired token"},
    },
)
async def validate_reset_token_endpoint(
    token: str,
    request: Request,
) -> MessageResponse:
    """
    Validate a password reset token without using it.

    Can be used by frontend to verify token before showing reset form.

    Args:
        token: The password reset token to validate.
        request: HTTP request for Redis access.

    Returns:
        Message indicating token is valid.

    Raises:
        HTTPException 400: If token is invalid or expired.
    """
    redis_client = getattr(request.app.state, "redis", None)

    payload = await validate_reset_token(redis_client, token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token",
        )

    return MessageResponse(message="Token is valid")
