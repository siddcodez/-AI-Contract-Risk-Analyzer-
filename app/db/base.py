"""SQLAlchemy declarative base — all ORM models import from here.

Keeping Base in its own module (rather than in session.py or a model file)
breaks circular imports: models import Base, session imports Base for Alembic,
neither imports the other.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    Provides:
    - Automatic __tablename__ via convention (overridden per model).
    - Shared metadata for Alembic migrations.
    - Type-checked column declarations via SQLAlchemy 2.0 Mapped[] syntax.
    """

    pass
