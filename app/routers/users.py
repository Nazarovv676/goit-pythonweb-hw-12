# app/routers/users.py
"""Users router for profile management and avatar upload."""

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app import crud
from app.core.config import get_settings
from app.deps import CurrentVerifiedUser, DBSession
from app.schemas import UserRead
from app.services.cloud import upload_avatar

settings = get_settings()
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user profile",
    description="Returns the authenticated user's profile. Rate limited to 5 requests per minute.",
)
@limiter.limit(settings.me_rate_limit)
async def get_current_user_profile(
    request: Request,
    current_user: CurrentVerifiedUser,
) -> UserRead:
    """
    Get the current authenticated user's profile.

    **Rate Limited**: 5 requests per minute per IP.

    Requires a valid JWT token in the Authorization header.
    """
    return UserRead.model_validate(current_user)


@router.patch(
    "/me/avatar",
    response_model=UserRead,
    summary="Upload user avatar",
    responses={
        400: {"description": "Invalid file type or upload failed"},
    },
)
async def update_avatar(
    current_user: CurrentVerifiedUser,
    session: DBSession,
    file: UploadFile = File(..., description="Avatar image file (JPEG, PNG, etc.)"),
) -> UserRead:
    """
    Upload or update the user's avatar image.

    - Accepts JPEG, PNG, GIF, and WebP images
    - Image is automatically resized to 250x250 and optimized
    - Stored in Cloudinary with face detection cropping
    """
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}",
        )

    # Validate file size (max 5MB)
    max_size = 5 * 1024 * 1024  # 5MB
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 5MB.",
        )

    # Reset file position for upload
    await file.seek(0)

    try:
        avatar_url = await upload_avatar(file, current_user.id)
        updated_user = crud.update_user_avatar(session, current_user, avatar_url)
        return UserRead.model_validate(updated_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
