from typing import Optional

from sqlmodel import Field, SQLModel


class UserRow(SQLModel, table=True):
    """Persistence model for users."""

    id: Optional[int] = Field(default=None, primary_key=True)
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
