"""Database initialization — create all tables."""

from backend.database.models import Base
from backend.database.session import get_engine


def init_db():
    """Create all database tables."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    return engine


if __name__ == "__main__":
    init_db()
    print("Database tables created successfully.")
