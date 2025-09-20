from sqlmodel import Session, select

from src.core.entities.user import User
from src.core.entities.user_identity import UserIdentity
from src.core.rows.user_identity_row import UserIdentityRow
from src.core.rows.user_row import UserRow


class UserRepository:
    """Data-access layer for users."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: int) -> User | None:
        row = self._session.get(UserRow, user_id)
        if row is None:
            return None
        return User.model_validate(row, from_attributes=True)


class UserIdentityRepository:
    """Data-access layer for user identities."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_uid(self, uid: str) -> UserIdentity | None:
        statement = select(UserIdentityRow).where(UserIdentityRow.uid_claim == uid)
        row = self._session.exec(statement).first()
        if row is None:
            return None
        return UserIdentity.model_validate(row, from_attributes=True)

    def get_by_issuer_subject(
        self, issuer: str, subject: str
    ) -> UserIdentity | None:
        statement = select(UserIdentityRow).where(
            (UserIdentityRow.issuer == issuer) & (UserIdentityRow.subject == subject)
        )
        row = self._session.exec(statement).first()
        if row is None:
            return None
        return UserIdentity.model_validate(row, from_attributes=True)
