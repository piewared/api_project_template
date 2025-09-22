import uuid

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """Base entity class with auto-generated UUID identifier."""

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the entity",
    )
