from typing import Optional

from src.core.entities._base import Entity


class User(Entity):
    """Domain entity representing an application user."""

    id: int
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
