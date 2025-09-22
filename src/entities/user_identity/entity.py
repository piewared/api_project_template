"""User identity domain entity."""

from datetime import datetime

from pydantic import Field

from src.entities._base import Entity


class UserIdentity(Entity):
    """User identity entity mapping external authentication to internal users.

    This domain model represents the link between external JWT identities
    and internal user accounts, enabling JIT (Just-In-Time) provisioning.
    """

    issuer: str = Field(description="JWT issuer that authenticated this identity")
    subject: str = Field(description="Subject claim from the JWT")
    uid_claim: str | None = Field(
        default=None, description="UID claim from the JWT, if available"
    )
    user_id: str = Field(description="Internal user ID this identity maps to")
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When this identity mapping was created",
    )
