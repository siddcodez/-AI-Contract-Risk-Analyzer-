"""Script to create required Supabase Storage buckets.

Usage:
    python scripts/create_buckets.py
"""

import sys

from app.core.config import get_settings
from supabase import Client, create_client


def create_bucket_if_missing(client: Client, bucket_name: str) -> None:
    """Create a Supabase storage bucket if it does not already exist."""
    try:
        client.storage.get_bucket(bucket_name)
        print(f"  [OK] Bucket already exists: {bucket_name}")
    except Exception:
        try:
            client.storage.create_bucket(bucket_name, options={"public": False})
            print(f"  [OK] Created bucket: {bucket_name}")
        except Exception as exc:
            print(
                f"  [ERROR] Failed to ensure bucket '{bucket_name}': {exc}",
                file=sys.stderr,
            )
            raise


def main() -> None:
    settings = get_settings()

    print(f"Connecting to Supabase Storage at {settings.SUPABASE_URL} …")

    client: Client = create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY,
    )

    buckets = [
        settings.SUPABASE_STORAGE_BUCKET,
    ]

    print("Ensuring buckets exist …")
    for bucket in buckets:
        create_bucket_if_missing(client, bucket)

    print("Done.")


if __name__ == "__main__":
    main()
