"""
S3-compatible object storage client (AWS S3 or Cloudflare R2).

Design:
- One boto3 client is created per process at first use and reused across requests.
- Blocking `put_object` calls are offloaded to a thread-pool executor so the
  async event loop is never stalled during uploads.
- S3 key path components (username) are sanitised to prevent path traversal.
"""

import asyncio
import functools
import logging
import re
import uuid
from typing import Dict

import boto3
from fastapi import UploadFile

from models.enums import ImageType
from utils.database.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton S3 client — created once, reused across all requests
# ---------------------------------------------------------------------------

_s3_client: boto3.client = None  # type: ignore[assignment]


def _get_s3_client() -> boto3.client:  # type: ignore[name-defined]
    global _s3_client
    if _s3_client is None:
        kwargs: dict = {
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
        }
        if settings.storage_endpoint_url:
            kwargs["endpoint_url"] = settings.storage_endpoint_url
            kwargs["region_name"] = "auto"
        else:
            kwargs["region_name"] = settings.aws_region
        _s3_client = boto3.client("s3", **kwargs)
        logger.info("S3 client initialised (endpoint=%s, bucket=%s)",
                    settings.storage_endpoint_url or "aws", settings.aws_s3_bucket_name)
    return _s3_client


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_SAFE_COMPONENT = re.compile(r"[^a-zA-Z0-9._-]")


def _safe(value: str, max_len: int = 48) -> str:
    """Replace unsafe characters and cap length for use in S3 key segments."""
    return _SAFE_COMPONENT.sub("_", value)[:max_len]


_SUBFOLDER: dict[ImageType, str] = {
    ImageType.CHAT:    "chat_images",
    ImageType.ORDER:   "order_images",
    ImageType.GALLERY: "gallery",
}

_MEDIA_SUBFOLDER: dict[str, str] = {
    "image": "chat_images",
    "video": "chat_videos",
}


def _ext_from_filename(filename: str | None, fallback: str) -> str:
    if filename and "." in filename:
        raw = filename.rsplit(".", 1)[-1].lower()
        return _SAFE_COMPONENT.sub("", raw)[:10] or fallback
    return fallback


# ---------------------------------------------------------------------------
# Core upload — runs blocking boto3 call in executor
# ---------------------------------------------------------------------------

async def _put_object(s3_key: str, body: bytes, content_type: str) -> None:
    client = _get_s3_client()
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            None,
            functools.partial(
                client.put_object,
                Bucket=settings.aws_s3_bucket_name,
                Key=s3_key,
                Body=body,
                ContentType=content_type,
                ServerSideEncryption="AES256",
            ),
        )
    except Exception:
        logger.exception("S3 upload failed: key=%s bucket=%s",
                         s3_key, settings.aws_s3_bucket_name)
        raise


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

async def upload_image(
    user_id: int,
    username: str,
    image_type: ImageType,
    image: UploadFile,
) -> Dict[str, str]:
    """Upload an image to S3; returns ``{"url": ..., "filename": ...}``."""
    subfolder = _SUBFOLDER.get(image_type, "uploads")
    ext = _ext_from_filename(image.filename, "jpg")
    s3_key = f"{subfolder}/{user_id}-{_safe(username)}/{uuid.uuid4()}.{ext}"

    content = await image.read()
    content_type = image.content_type or "image/jpeg"

    logger.debug("Uploading image: key=%s size=%d ct=%s", s3_key, len(content), content_type)
    await _put_object(s3_key, content, content_type)

    url = f"{settings.storage_base_url}/{s3_key}"
    return {"url": url, "filename": s3_key.rsplit("/", 1)[-1]}


async def upload_media(
    user_id: int,
    username: str,
    media_type: str,
    media: UploadFile,
) -> Dict[str, str]:
    """Upload chat media (image or video) to S3; returns ``{"url": ..., "filename": ...}``."""
    subfolder = _MEDIA_SUBFOLDER.get(media_type, "uploads")
    default_ext = "jpg" if media_type == "image" else "mp4"
    ext = _ext_from_filename(media.filename, default_ext)
    s3_key = f"{subfolder}/{user_id}-{_safe(username)}/{uuid.uuid4()}.{ext}"

    content = await media.read()
    if media_type == "image":
        content_type = media.content_type or "image/jpeg"
    else:
        content_type = media.content_type or "video/mp4"

    logger.debug("Uploading media: key=%s size=%d ct=%s", s3_key, len(content), content_type)
    await _put_object(s3_key, content, content_type)

    url = f"{settings.storage_base_url}/{s3_key}"
    return {"url": url, "filename": s3_key.rsplit("/", 1)[-1]}
