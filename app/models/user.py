"""User model and UserRole enum — represents an authenticated user.

Users belong to exactly one organization and have one of three roles:
admin, reviewer, or viewer.  The password_hash column stores bcrypt
hashes — plaintext passwords are never persisted.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.organization import Organization


class UserRole(enum.StrEnum):
    """RBAC roles ordered by privilege level (highest → lowest)."""

    admin = "admin"
    reviewer = "reviewer"
    viewer = "viewer"


class User(Base):
    """An authenticated user within an organization.

    Attributes:
        id: Primary key (UUID).
        email: Globally unique login identifier.
        password_hash: bcrypt hash of the password.
        full_name: Display name.
        role: RBAC role (admin | reviewer | viewer).
        org_id: FK to the user's organization.
        is_active: Soft-delete flag.
        created_at: Row creation timestamp.
        updated_at: Last modification timestamp.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(1024))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            create_constraint=False,
            native_enum=True,
            create_type=False,
        ),
        default=UserRole.viewer,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Eager-load via SELECT IN to avoid async lazy-load errors
    organization: Mapped[Organization] = relationship(lazy="selectin")
