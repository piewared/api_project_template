"""User database table model."""

from src.entities._base import EntityTable


class UserTable(EntityTable, table=True):
    """Database persistence model for users.

    This represents how the User entity is stored in the database.
    It's separate from the domain entity to maintain clean architecture
    while keeping related code together.
    """

    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None
