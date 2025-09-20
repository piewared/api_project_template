from datetime import datetime
from typing import Optional

from src.core.entities._base import Entity


class UserIdentity(Entity):
    """Domain entity linking external identities to users."""

    id: Optional[int] = None
    issuer: str
    subject: str
    uid_claim: Optional[str] = None
    user_id: int
    created_at: datetime
