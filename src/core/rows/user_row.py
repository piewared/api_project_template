from sqlmodel import Field, SQLModel


class UserRow(SQLModel, table=True):
    """Persistence model for users."""

    id: int | None = Field(default=None, primary_key=True)
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None
