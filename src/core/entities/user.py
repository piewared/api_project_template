from pydantic import Field

from src.core.entities._base import Entity


class User(Entity):
    """User entity representing a person in the system."""

    first_name: str = Field(description="User's first name")
    last_name: str = Field(description="User's last name")
    email: str | None = Field(default=None, description="User's email address")
    phone: str | None = Field(default=None, description="User's phone number")
    address: str | None = Field(default=None, description="User's address")
