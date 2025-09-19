from datetime import datetime, UTC
from typing import Optional

from sqlalchemy import Column, String, UniqueConstraint, DateTime
from sqlmodel import Field, SQLModel


def utc_now():
    """Return current UTC datetime."""
    return datetime.now(UTC)


class UserIdentityRow(SQLModel, table=True):
    """Persistence model mapping external identities to user accounts."""

    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_identity_issuer_subject"),
        UniqueConstraint("user_id", name="uq_identity_user"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    issuer: str = Field(sa_column=Column(String(512), nullable=False, index=True))
    subject: str = Field(sa_column=Column(String(512), nullable=False, index=True))
    uid_claim: Optional[str] = Field(default=None, sa_column=Column(String(512), nullable=True, index=True))
    user_id: int = Field(foreign_key="userrow.id", index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
