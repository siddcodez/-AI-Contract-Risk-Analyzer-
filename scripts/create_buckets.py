"""Script to create required MinIO buckets for local development.

Run once after `docker compose up -d`:
    python scripts/create_buckets.py

The ObjectStorageProvider abstraction means real S3 buckets are created
via Terraform/CDK in prod — this script is dev-only.
"""

import sys

import boto3
from app.core.config import get_settings
from botocore.exceptions import ClientError


def create_bucket(client: boto3.client, bucket_name: str) -> None:  # type: ignore[type-arg]
    """Create a bucket if it does not already exist."""
    try:
        client.head_bucket(Bucket=bucket_name)
        print(f"  [OK] Bucket already exists: {bucket_name}")
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code in ("404", "NoSuchBucket"):
            client.create_bucket(Bucket=bucket_name)
            print(f"  [OK] Created bucket: {bucket_name}")
        else:
            print(f"  [ERROR] Unexpected error for bucket {bucket_name}: {exc}", file=sys.stderr)
            raise


def main() -> None:
    settings = get_settings()

    print(f"Connecting to object storage at {settings.MINIO_ENDPOINT} …")

    client = boto3.client(
        "s3",
        endpoint_url=settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name="us-east-1",  # MinIO accepts any region string
    )

    buckets = [
        settings.MINIO_BUCKET_NAME,
    ]

    print("Ensuring buckets exist …")
    for bucket in buckets:
        create_bucket(client, bucket)

    print("Done.")


if __name__ == "__main__":
    main()
