"""Object storage service for MinIO / S3.

Provides a thin wrapper over boto3 for uploading, downloading, and
deleting contract files.  Uses the same connection settings as the
main application (MINIO_ENDPOINT, MINIO_ACCESS_KEY, etc.).

The service uses synchronous boto3 calls because:
1. Upload is called from async endpoints via run_in_executor or
   directly (boto3 calls are fast for MinIO on localhost).
2. Keeping it synchronous avoids the complexity of aiobotocore
   session management for simple put/get/delete operations.
"""

import io
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger

logger = get_logger(__name__)


def _get_s3_client() -> Any:
    """Create a boto3 S3 client configured for MinIO."""
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name="us-east-1",
    )


def upload_file(
    *,
    file_data: bytes,
    key: str,
    content_type: str,
) -> str:
    """Upload a file to object storage.

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
        client = _get_s3_client()
        client.upload_fileobj(
            Fileobj=io.BytesIO(file_data),
            Bucket=settings.MINIO_BUCKET_NAME,
            Key=key,
            ExtraArgs={"ContentType": content_type},
        )
        logger.info("File uploaded to storage", key=key, size=len(file_data))
        return key
    except ClientError as exc:
        logger.error("Storage upload failed", key=key, exc_info=exc)
        raise StorageError(
            "Failed to upload file to storage",
            details={"key": key},
        ) from exc


def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Generate a presigned URL for downloading a file.

    Args:
        key: The object key in the bucket.
        expires_in: URL validity in seconds (default: 1 hour).

    Returns:
        A presigned URL string.

    Raises:
        StorageError: If URL generation fails.
    """
    settings = get_settings()
    try:
        client = _get_s3_client()
        url: str = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.MINIO_BUCKET_NAME, "Key": key},
            ExpiresIn=expires_in,
        )
        return url
    except ClientError as exc:
        logger.error("Presigned URL generation failed", key=key, exc_info=exc)
        raise StorageError(
            "Failed to generate download URL",
            details={"key": key},
        ) from exc


def delete_file(key: str) -> None:
    """Delete a file from object storage.

    Args:
        key: The object key to delete.

    Raises:
        StorageError: If the deletion fails.
    """
    settings = get_settings()
    try:
        client = _get_s3_client()
        client.delete_object(
            Bucket=settings.MINIO_BUCKET_NAME,
            Key=key,
        )
        logger.info("File deleted from storage", key=key)
    except ClientError as exc:
        logger.error("Storage deletion failed", key=key, exc_info=exc)
        raise StorageError(
            "Failed to delete file from storage",
            details={"key": key},
        ) from exc


def download_file(key: str) -> bytes:
    """Download file bytes from object storage.

    Args:
        key: The object key in the bucket.

    Returns:
        Raw file bytes.

    Raises:
        StorageError: If the download fails.
    """
    settings = get_settings()
    try:
        client = _get_s3_client()
        response = client.get_object(
            Bucket=settings.MINIO_BUCKET_NAME,
            Key=key,
        )
        data: bytes = response["Body"].read()
        logger.info("Downloaded file from storage", key=key, size=len(data))
        return data
    except ClientError as exc:
        logger.error("Storage download failed", key=key, exc_info=exc)
        raise StorageError(
            "Failed to download file from storage",
            details={"key": key},
        ) from exc
