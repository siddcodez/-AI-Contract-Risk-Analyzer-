"""Repository for Organization CRUD operations.

The organizations table does NOT have RLS enabled — it is an identity
table.  Tenant isolation for organizations is enforced at the
application layer (users can only access their own org).
"""

import re
import unicodedata
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization


def generate_slug(name: str) -> str:
    """Generate a URL-safe slug from an organization name.

    Steps: NFKD normalise → ASCII → lowercase → non-alnum to hyphens
           → strip/collapse hyphens.
    """
    slug = unicodedata.normalize("NFKD", name)
    slug = slug.encode("ascii", "ignore").decode("ascii")
    slug = slug.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or "org"


async def get_by_id(session: AsyncSession, org_id: uuid.UUID) -> Organization | None:
    """Fetch an organization by primary key."""
    result = await session.execute(select(Organization).where(Organization.id == org_id))
    return result.scalars().first()


async def get_by_slug(session: AsyncSession, slug: str) -> Organization | None:
    """Fetch an organization by its unique slug."""
    result = await session.execute(select(Organization).where(Organization.slug == slug))
    return result.scalars().first()


async def create_with_unique_slug(
    session: AsyncSession,
    *,
    name: str,
) -> Organization:
    """Create a new organization with an auto-generated unique slug.

    If the base slug already exists, a numeric suffix is appended
    deterministically (e.g. acme, acme-1, acme-2, …).
    """
    base_slug = generate_slug(name)
    slug = base_slug
    suffix = 1

    while await get_by_slug(session, slug) is not None:
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    org = Organization(
        id=uuid.uuid4(),
        name=name,
        slug=slug,
        is_active=True,
    )
    session.add(org)
    await session.flush()  # populate server-defaults (created_at, etc.)
    return org
