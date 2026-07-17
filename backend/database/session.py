"""Database session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.config import get_settings
from backend.database.models import Base


def get_engine():
    """Create SQLAlchemy engine from settings."""
    settings = get_settings()
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},  # SQLite specific
        echo=False,
    )
    return engine


def get_session_factory():
    """Create a session factory."""
    engine = get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Module-level session factory
SessionFactory = get_session_factory()


def get_db() -> Session:
    """FastAPI dependency — yields a database session."""
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()
