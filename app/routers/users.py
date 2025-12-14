# app/routers/users.py
"""
Users router for profile management and avatar upload.

This module provides endpoints for:
- Getting current user profile
- Uploading/updating avatar (admin only)

Rate limiting is applied to the profile endpoint to prevent abuse.

Policy changes (v2.1):
- Avatar upload is now restricted to admin users only
- Regular users receive 403 Forbidden on avatar update
"""

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app import crud
from app.core.config import get_settings
from app.deps import CurrentAdmin, CurrentVerifiedUser, DBSession, invalidate_user_cache
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

    Returns profile information including email, name, avatar URL,
    verification status, and role.

    **Rate Limited**: 5 requests per minute per IP.

    Args:
        request: HTTP request (for rate limiting).
        current_user: The authenticated and verified user.

    Returns:
        User profile data (excluding sensitive fields like password).

    Note:
        Requires a valid JWT token in the Authorization header.
    """
    return UserRead.model_validate(current_user)


@router.patch(
    "/me/avatar",
    response_model=UserRead,
    summary="Upload user avatar (Admin only)",
    responses={
        400: {"description": "Invalid file type or upload failed"},
        403: {"description": "Only admins can update avatars"},
    },
)
async def update_avatar(
    request: Request,
    current_user: CurrentAdmin,
    session: DBSession,
    file: UploadFile = File(..., description="Avatar image file (JPEG, PNG, etc.)"),
) -> UserRead:
    """
    Upload or update the user's avatar image.

    **Admin Only**: Only users with admin role can update their avatar.
    Regular users will receive 403 Forbidden.

    Image requirements:
    - Accepted formats: JPEG, PNG, GIF, WebP
    - Maximum size: 5MB
    - Image is automatically resized to 250x250
    - Stored in Cloudinary with face detection cropping

    Args:
        request: HTTP request for cache invalidation.
        current_user: The authenticated admin user.
        session: Database session.
        file: The uploaded image file.

    Returns:
        Updated user profile with new avatar URL.

    Raises:
        HTTPException 400: If file type invalid or upload fails.
        HTTPException 403: If user is not an admin.
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

        # Invalidate user cache after avatar change
        await invalidate_user_cache(request, current_user.id)

        return UserRead.model_validate(updated_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
