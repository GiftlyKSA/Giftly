import random
import string
import uuid
from typing import Dict

import boto3
from utils.database.config import settings
from models.enums import ImageType
from fastapi import UploadFile


def generate_random_string(length: int = 8) -> str:
    """Generate a random string of specified length."""
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(length))


def get_subfolder(image_type: ImageType) -> str:
    """Get the subfolder name based on image type."""
    if image_type == ImageType.CHAT:
        return "chat_images"
    elif image_type == ImageType.ORDER:
        return "order_creation_images"
    elif image_type == ImageType.GALLERY:
        return "gallery"
    else:
        raise ValueError(f"Invalid image type: {image_type}")


def get_media_subfolder(media_type: str) -> str:
    """Get the subfolder name based on media type for messages."""
    if media_type == "image":
        return "chat_images"
    elif media_type == "video":
        return "chat_videos"
    else:
        raise ValueError(f"Invalid media type: {media_type}")


async def upload_image(
    user_id: int, username: str, image_type: ImageType, image: UploadFile
) -> Dict[str, str]:
    """
    Upload an image to S3 storage.

    Args:
        user_id: The user's ID
        username: The user's username
        image_type: The type of image (CHAT, ORDER, GALLERY)
        image: The uploaded image file

    Returns:
        Dict containing 'url' and 'filename'
    """
    # Generate random 8-character string
    random_str = generate_random_string(8)

    # Create folder name: RANDOM_8_CHARS-USER_ID-USERNAME
    folder_name = f"{random_str}-{user_id}-{username}"

    # Get subfolder based on image type
    subfolder = get_subfolder(image_type)

    # Generate unique filename
    file_extension = image.filename.split(".")[-1] if "." in image.filename else "jpg"
    unique_filename = f"{uuid.uuid4()}.{file_extension}"

    # Full S3 key
    s3_key = f"{folder_name}/{subfolder}/{unique_filename}"

    # Read image content
    image_content = await image.read()

    # Create S3 client
    s3_client_kwargs = {
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
    }

    # Use Cloudflare R2 endpoint if provided
    if settings.storage_endpoint_url:
        s3_client_kwargs["endpoint_url"] = settings.storage_endpoint_url
        s3_client_kwargs["region_name"] = "auto"  # Cloudflare R2 uses 'auto' region
    else:
        s3_client_kwargs["region_name"] = settings.aws_region

    s3_client = boto3.client("s3", **s3_client_kwargs)

    # Upload to S3
    s3_client.put_object(
        Bucket=settings.aws_s3_bucket_name,
        Key=s3_key,
        Body=image_content,
        ContentType=image.content_type or "image/jpeg",
    )

    # Generate public URL using custom domain
    image_url = f"{settings.storage_base_url}/{s3_key}"

    return {"url": image_url, "filename": unique_filename}


async def upload_media(
    user_id: int, username: str, media_type: str, media: UploadFile
) -> Dict[str, str]:
    """
    Upload media (image or video) to S3 storage for messages.

    Args:
        user_id: The user's ID
        username: The user's username
        media_type: The type of media ('image' or 'video')
        media: The uploaded media file

    Returns:
        Dict containing 'url' and 'filename'
    """
    # Generate random 8-character string
    random_str = generate_random_string(8)

    # Create folder name: RANDOM_8_CHARS-USER_ID-USERNAME
    folder_name = f"{random_str}-{user_id}-{username}"

    # Get subfolder based on media type
    subfolder = get_media_subfolder(media_type)

    # Generate unique filename
    file_extension = (
        media.filename.split(".")[-1]
        if "." in media.filename
        else ("jpg" if media_type == "image" else "mp4")
    )
    unique_filename = f"{uuid.uuid4()}.{file_extension}"

    # Full S3 key
    s3_key = f"{folder_name}/{subfolder}/{unique_filename}"

    # Read media content
    media_content = await media.read()

    # Create S3 client
    s3_client_kwargs = {
        "aws_access_key_id": settings.aws_access_key_id,
        "aws_secret_access_key": settings.aws_secret_access_key,
    }

    # Use Cloudflare R2 endpoint if provided
    if settings.storage_endpoint_url:
        s3_client_kwargs["endpoint_url"] = settings.storage_endpoint_url
        s3_client_kwargs["region_name"] = "auto"  # Cloudflare R2 uses 'auto' region
    else:
        s3_client_kwargs["region_name"] = settings.aws_region

    s3_client = boto3.client("s3", **s3_client_kwargs)

    # Determine content type
    if media_type == "image":
        content_type = media.content_type or "image/jpeg"
    elif media_type == "video":
        content_type = media.content_type or "video/mp4"
    else:
        content_type = media.content_type or "application/octet-stream"

    # Upload to S3
    s3_client.put_object(
        Bucket=settings.aws_s3_bucket_name,
        Key=s3_key,
        Body=media_content,
        ContentType=content_type,
    )

    # Generate public URL using custom domain
    media_url = f"{settings.storage_base_url}/{s3_key}"

    return {"url": media_url, "filename": unique_filename}
