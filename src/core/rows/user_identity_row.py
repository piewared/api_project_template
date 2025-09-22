from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String, UniqueConstraint
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

    id: str = Field(primary_key=True)
    issuer: str = Field(sa_column=Column(String(512), nullable=False, index=True))
    subject: str = Field(sa_column=Column(String(512), nullable=False, index=True))
    uid_claim: str | None = Field(default=None, sa_column=Column(String(512), nullable=True, index=True))
    user_id: str = Field(foreign_key="userrow.id", index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
