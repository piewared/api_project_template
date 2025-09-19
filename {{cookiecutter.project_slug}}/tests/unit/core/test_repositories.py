"""Unit tests for core repositories."""

import pytest
from sqlmodel import Session

from {{cookiecutter.package_name}}.core.entities.user import User
from {{cookiecutter.package_name}}.core.entities.user_identity import UserIdentity
from {{cookiecutter.package_name}}.core.repositories.user_repo import UserRepository, UserIdentityRepository
from {{cookiecutter.package_name}}.core.rows.user_row import UserRow
from {{cookiecutter.package_name}}.core.rows.user_identity_row import UserIdentityRow


class TestUserRepository:
    """Test the UserRepository in isolation."""

    @pytest.fixture
    def user_repo(self, session: Session):
        """Create a UserRepository instance for testing."""
        return UserRepository(session)

    def test_get_user_by_id(self, user_repo: UserRepository, session: Session):
        """Should retrieve user by ID."""
        # Setup
        user_row = UserRow(first_name="Jane", last_name="Smith", email="jane@example.com")
        session.add(user_row)
        session.commit()
        session.refresh(user_row)
        
        # Ensure ID is not None after persistence
        assert user_row.id is not None
        
        # Test
        result = user_repo.get(user_row.id)
        
        assert result is not None
        assert result.id == user_row.id
        assert result.first_name == "Jane"
        assert result.last_name == "Smith"
        assert result.email == "jane@example.com"

    def test_get_user_not_found(self, user_repo: UserRepository):
        """Should return None for non-existent user."""
        result = user_repo.get(999)
        assert result is None

    def test_get_returns_domain_entity(self, user_repo: UserRepository, session: Session):
        """Should return User domain entity, not database row."""
        # Setup
        user_row = UserRow(first_name="Test", last_name="Entity", email="test@example.com")
        session.add(user_row)
        session.commit()
        session.refresh(user_row)
        
        # Ensure ID is not None after persistence
        assert user_row.id is not None
        
        # Test
        result = user_repo.get(user_row.id)
        
        assert isinstance(result, User)
        assert not isinstance(result, UserRow)


class TestUserIdentityRepository:
    """Test the UserIdentityRepository in isolation."""

    @pytest.fixture
    def identity_repo(self, session: Session):
        """Create a UserIdentityRepository instance for testing."""
        return UserIdentityRepository(session)

    @pytest.fixture
    def sample_user(self, session: Session):
        """Create a sample user for identity testing."""
        user_row = UserRow(first_name="Test", last_name="User", email="test@example.com")
        session.add(user_row)
        session.commit()
        session.refresh(user_row)
        # Ensure we have a valid ID
        assert user_row.id is not None
        return user_row

    def test_get_by_uid(self, identity_repo: UserIdentityRepository, sample_user: UserRow, session: Session):
        """Should retrieve identity by UID claim."""
        # Setup
        identity = UserIdentityRow(
            issuer="https://auth.example.com",
            subject="user-123",
            uid_claim="unique-uid",
            user_id=sample_user.id  # type: ignore[arg-type] # We've asserted it's not None
        )
        session.add(identity)
        session.commit()
        session.refresh(identity)
        
        # Test
        result = identity_repo.get_by_uid("unique-uid")
        
        assert result is not None
        assert result.uid_claim == "unique-uid"
        assert result.user_id == sample_user.id

    def test_get_by_uid_not_found(self, identity_repo: UserIdentityRepository):
        """Should return None for non-existent UID."""
        result = identity_repo.get_by_uid("nonexistent-uid")
        assert result is None

    def test_get_by_issuer_subject(self, identity_repo: UserIdentityRepository, sample_user: UserRow, session: Session):
        """Should retrieve identity by issuer and subject combination."""
        # Setup
        identity = UserIdentityRow(
            issuer="https://specific.issuer.com",
            subject="specific-subject",
            uid_claim="uid-123",
            user_id=sample_user.id  # type: ignore[arg-type] # We've asserted it's not None
        )
        session.add(identity)
        session.commit()
        session.refresh(identity)
        
        # Test
        result = identity_repo.get_by_issuer_subject("https://specific.issuer.com", "specific-subject")
        
        assert result is not None
        assert result.issuer == "https://specific.issuer.com"
        assert result.subject == "specific-subject"
        assert result.user_id == sample_user.id

    def test_get_by_issuer_subject_not_found(self, identity_repo: UserIdentityRepository):
        """Should return None for non-existent issuer/subject combination."""
        result = identity_repo.get_by_issuer_subject("https://unknown.issuer", "unknown-subject")
        assert result is None

    def test_returns_domain_entity(self, identity_repo: UserIdentityRepository, sample_user: UserRow, session: Session):
        """Should return UserIdentity domain entity, not database row."""
        # Setup
        identity = UserIdentityRow(
            issuer="https://domain.test",
            subject="domain-subject",
            uid_claim="domain-uid",
            user_id=sample_user.id  # type: ignore[arg-type] # We've asserted it's not None
        )
        session.add(identity)
        session.commit()
        session.refresh(identity)
        
        # Test
        result = identity_repo.get_by_uid("domain-uid")
        
        assert isinstance(result, UserIdentity)
        assert not isinstance(result, UserIdentityRow)

    def test_uid_claim_can_be_none(self, identity_repo: UserIdentityRepository, sample_user: UserRow, session: Session):
        """Should handle identities without UID claims."""
        # Setup
        identity = UserIdentityRow(
            issuer="https://no-uid.issuer",
            subject="no-uid-subject",
            uid_claim=None,  # No UID claim
            user_id=sample_user.id  # type: ignore[arg-type] # We've asserted it's not None
        )
        session.add(identity)
        session.commit()
        session.refresh(identity)
        
        # Test
        result = identity_repo.get_by_issuer_subject("https://no-uid.issuer", "no-uid-subject")
        
        assert result is not None
        assert result.uid_claim is None
        assert result.issuer == "https://no-uid.issuer"
        assert result.subject == "no-uid-subject"