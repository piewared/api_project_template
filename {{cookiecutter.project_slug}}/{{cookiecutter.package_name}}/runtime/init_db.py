"""Database initialization script."""

from {{cookiecutter.package_name}}.runtime.db import engine
from {{cookiecutter.package_name}}.core.rows.user_row import UserRow  # noqa: F401
from {{cookiecutter.package_name}}.core.rows.user_identity_row import UserIdentityRow  # noqa: F401
from sqlmodel import SQLModel


def init_db() -> None:
    """Create all database tables."""
    SQLModel.metadata.create_all(engine)
    print("Database initialized with tables.")


if __name__ == "__main__":
    init_db()