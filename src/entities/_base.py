import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from pydantic import BaseModel
from pydantic import Field as PydanticField
from sqlmodel import Field, SQLModel


class Entity(BaseModel):
    """Base entity class with auto-generated UUID identifier."""

    id: str = PydanticField(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the entity",
    )

    created_at: datetime = PydanticField(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = PydanticField(default_factory=lambda: datetime.now(UTC))


class EntityTable(SQLModel, table=False):
    """Base entity class with auto-generated UUID identifier."""

    id: str = Field(
        primary_key=True,
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the entity",
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        nullable=False,
        sa_column_kwargs={
            "server_default": sa.func.now(),
            "onupdate": sa.func.now(),  # This is the key for automatic updates
        },
    )
