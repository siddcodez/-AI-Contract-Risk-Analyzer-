"""Object storage service for Supabase Storage.

Provides an abstraction for uploading, downloading, deleting, and generating
signed download URLs for contract documents using the official Supabase client.
"""

from typing import cast

from storage3.types import FileOptions
from supabase import Client, create_client

from app.core.config import get_settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger

logger = get_logger(__name__)

_supabase_client: Client | None = None


def _get_supabase_client() -> Client:
    """Create or return the cached Supabase client for storage operations."""
    global _supabase_client
    if _supabase_client is None:
        settings = get_settings()
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        )
    return _supabase_client


def upload_file(
    *,
    file_data: bytes,
    key: str,
    content_type: str,
) -> str:
    """Upload a file to Supabase Storage.

    Args:
        file_data: Raw file bytes.
        key: The object key (path) in the bucket.
        content_type: MIME type for the object.

    Returns:
        The storage key (same as input key).

    Raises:
        StorageError: If the upload fails.
    """
    settings = get_settings()
    try:
        client = _get_supabase_client()
        bucket = client.storage.from_(settings.SUPABASE_STORAGE_BUCKET)
        file_options = cast(
            FileOptions,
            {
                "content-type": content_type,
                "upsert": "true",
            },
        )
        bucket.upload(
            path=key,
            file=file_data,
            file_options=file_options,
        )
        logger.info("File uploaded to Supabase storage", key=key, size=len(file_data))
        return key
    except Exception as exc:
        logger.error("Storage upload failed", key=key, exc_info=exc)
        raise StorageError(
            "Failed to upload file to storage",
            details={"key": key},
        ) from exc


def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Generate a presigned/signed URL for downloading a private file.

    Args:
        key: The object key in the bucket.
        expires_in: URL validity in seconds (default: 1 hour).

    Returns:
        A signed URL string.

    Raises:
        StorageError: If URL generation fails.
    """
    settings = get_settings()
    try:
        client = _get_supabase_client()
        bucket = client.storage.from_(settings.SUPABASE_STORAGE_BUCKET)
        res = bucket.create_signed_url(path=key, expires_in=expires_in)

        # Handle both dict response and object response formats
        signed_url: str | None = None
        if isinstance(res, dict):
            raw_url = (
                res.get("signedURL")
                or res.get("signedUrl")
                or res.get("signed_url")
                or res.get("url")
            )
            if isinstance(raw_url, str):
                signed_url = raw_url
        elif hasattr(res, "signedURL"):
            raw_val = getattr(res, "signedURL", None)
            if isinstance(raw_val, str):
                signed_url = raw_val
        elif hasattr(res, "signedUrl"):
            raw_val = getattr(res, "signedUrl", None)
            if isinstance(raw_val, str):
                signed_url = raw_val

        if not signed_url and isinstance(res, str):
            signed_url = res

        if not signed_url:
            signed_url = str(res)

        return signed_url
    except Exception as exc:
        logger.error("Signed URL generation failed", key=key, exc_info=exc)
        raise StorageError(
            "Failed to generate download URL",
            details={"key": key},
        ) from exc


def delete_file(key: str) -> None:
    """Delete a file from Supabase Storage.

    Args:
        key: The object key to delete.

    Raises:
        StorageError: If the deletion fails.
    """
    settings = get_settings()
    try:
        client = _get_supabase_client()
        bucket = client.storage.from_(settings.SUPABASE_STORAGE_BUCKET)
        bucket.remove([key])
        logger.info("File deleted from Supabase storage", key=key)
    except Exception as exc:
        logger.error("Storage deletion failed", key=key, exc_info=exc)
        raise StorageError(
            "Failed to delete file from storage",
            details={"key": key},
        ) from exc


def download_file(key: str) -> bytes:
    """Download file bytes from Supabase Storage.

    Args:
        key: The object key in the bucket.

    Returns:
        Raw file bytes.

    Raises:
        StorageError: If the download fails.
    """
    settings = get_settings()
    try:
        client = _get_supabase_client()
        bucket = client.storage.from_(settings.SUPABASE_STORAGE_BUCKET)
        data: bytes = bucket.download(path=key)
        logger.info("Downloaded file from Supabase storage", key=key, size=len(data))
        return data
    except Exception as exc:
        logger.error("Storage download failed", key=key, exc_info=exc)
        raise StorageError(
            "Failed to download file from storage",
            details={"key": key},
        ) from exc


def exists(key: str) -> bool:
    """Check if a file exists in Supabase Storage.

    Args:
        key: The object key in the bucket.

    Returns:
        True if file exists, False otherwise.
    """
    settings = get_settings()
    try:
        client = _get_supabase_client()
        bucket = client.storage.from_(settings.SUPABASE_STORAGE_BUCKET)
        return bool(bucket.exists(path=key))
    except Exception as exc:
        logger.warning("Storage exists check failed", key=key, exc_info=exc)
        return False
