"""
Database engine and session factory.

SQLAlchemy 2.0 style — uses DeclarativeBase instead of deprecated declarative_base().
Reads DATABASE_URL from config.py (which reads from .env).

Supports both SQLite (development) and PostgreSQL (production) via
automatic driver detection from the DATABASE_URL scheme.

Phase E8: Dual-driver abstraction.
  - SQLite:      connect_args={"check_same_thread": False}
  - PostgreSQL:  pool_size=5, max_overflow=10, pool_pre_ping=True
"""

from config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# ---------------------------------------------------------------------------
# Driver-specific configuration
# ---------------------------------------------------------------------------

_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite:
    _engine_kwargs = {
        "connect_args": {"check_same_thread": False},
    }
else:
    # PostgreSQL (or any non-SQLite database)
    _engine_kwargs = {
        "pool_size": 5,
        "max_overflow": 10,
        "pool_pre_ping": True,
    }


engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    **_engine_kwargs,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base class."""

    pass


def get_db():
    """Dependency that provides a database session and ensures it is closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
