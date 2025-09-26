"""Database initialization script."""

from sqlmodel import SQLModel

from src.entities.user import UserTable  # noqa: F401
from src.entities.user_identity import UserIdentityTable  # noqa: F401
from src.runtime.db import engine


def init_db() -> None:
    """Create all database tables."""
    SQLModel.metadata.create_all(engine)
    print("Database initialized with tables.")


if __name__ == "__main__":
    init_db()
