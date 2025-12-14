# app/services/cloud.py
"""Cloudinary service for avatar uploads."""

import logging
from typing import Any

import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.cloudinary_cloud_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_api_secret,
    secure=True,
)


async def upload_avatar(file: UploadFile, user_id: int) -> str:
    """
    Upload an avatar image to Cloudinary.

    Args:
        file: The uploaded file
        user_id: The user's ID (used for public_id naming)

    Returns:
        The secure URL of the uploaded image

    Raises:
        ValueError: If upload fails
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise ValueError("File must be an image")

    # Read file content
    content = await file.read()

    # Generate a unique public_id
    public_id = f"contacts-api/avatars/user_{user_id}"

    try:
        # Upload to Cloudinary with transformations
        result: dict[str, Any] = cloudinary.uploader.upload(
            content,
            public_id=public_id,
            folder="contacts-api/avatars",
            overwrite=True,
            resource_type="image",
            transformation=[
                {"width": 250, "height": 250, "crop": "fill", "gravity": "face"},
                {"quality": "auto", "fetch_format": "auto"},
            ],
        )

        secure_url: str = result.get("secure_url", "")
        if not secure_url:
            raise ValueError("Upload succeeded but no secure_url returned")

        logger.info(f"Avatar uploaded for user {user_id}: {secure_url}")
        return secure_url

    except Exception as e:
        logger.error(f"Failed to upload avatar for user {user_id}: {e}")
        raise ValueError(f"Failed to upload avatar: {e}") from e


def delete_avatar(user_id: int) -> bool:
    """
    Delete an avatar from Cloudinary.

    Args:
        user_id: The user's ID

    Returns:
        True if deletion was successful
    """
    public_id = f"contacts-api/avatars/user_{user_id}"

    try:
        result = cloudinary.uploader.destroy(public_id)
        return result.get("result") == "ok"
    except Exception as e:
        logger.error(f"Failed to delete avatar for user {user_id}: {e}")
        return False
