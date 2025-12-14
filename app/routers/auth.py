# app/routers/auth.py
"""Authentication router for registration, login, and email verification."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError

from app import crud
from app.core.security import create_access_token, verify_email_token
from app.deps import DBSession
from app.schemas import MessageResponse, Token, UserCreate, UserRead
from app.services.email import send_verification_email

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

    - Creates a new user with hashed password
    - Sends verification email
    - User must verify email before logging in

    Returns 409 if email is already registered.
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
async def verify_email(token: str, session: DBSession) -> MessageResponse:
    """
    Verify a user's email address using the token from the verification email.

    - Token must be valid and not expired
    - Marks user as verified upon success
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

    - Requires valid email and password
    - **Requires verified email** to obtain tokens
    - Returns JWT access token for use in Authorization header

    Use the returned token as: `Authorization: Bearer <access_token>`
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

    access_token = create_access_token(
        data={"sub": user.id, "email": user.email}
    )

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

