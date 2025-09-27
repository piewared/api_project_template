"""Consolidated data layer tests.

This module combines and consolidates tests for:
- User entity operations (creation, validation, equality, UUID handling)
- User table operations (entity-table conversions, database persistence)
- User repository operations (both integration and mocked unit tests)
- UserIdentity entity, table, and repository operations
- Repository patterns and data access functionality
- Database session and transaction handling

Replaces:
- tests/unit/entities/test_user.py (complete coverage including equality tests)
- tests/unit/entities/test_user_identity.py
- tests/unit/core/test_repositories.py (both integration and mocked tests)
"""

import pytest
from sqlmodel import Session, select

from src.entities.user import User, UserRepository, UserTable
from src.entities.user_identity import (
    UserIdentity,
    UserIdentityRepository,
    UserIdentityTable,
)


class TestUserEntity:
    """Test User domain entity."""

    def test_user_creation(self):
        """Test user entity creation with required fields."""
        user = User(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
        )

        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.email == "john.doe@example.com"
        assert user.id is not None  # Auto-generated
        assert user.created_at is not None
        assert user.updated_at is not None

    def test_user_validation(self):
        """Test user entity field validation."""
        # Valid user
        user = User(
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
        )
        assert user.email == "jane.smith@example.com"

        # Test string representations
        assert "Jane" in str(user)
        assert "Smith" in str(user)

    def test_user_optional_fields(self):
        """Test user with optional/null fields."""
        user = User(
            first_name="Test",
            last_name="User",
            email=None,  # Optional email
        )

        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.email is None

    def test_user_equality(self):
        """Should compare users by their business attributes, ignoring timestamps."""
        user1 = User(
            id="1", first_name="John", last_name="Doe", email="john.doe@example.com"
        )

        user2 = User(
            id="1", first_name="John", last_name="Doe", email="john.doe@example.com"
        )

        user3 = User(
            id="2", first_name="Jane", last_name="Smith", email="jane.smith@example.com"
        )

        # Test equality with same business data (should ignore timestamp differences)
        assert user1 == user2
        assert user1 != user3

    def test_user_representation(self):
        """Should have a meaningful string representation."""
        user = User(
            id="1", first_name="John", last_name="Doe", email="john.doe@example.com"
        )

        user_str = str(user)
        assert "John" in user_str
        assert "Doe" in user_str
        assert "john.doe@example.com" in user_str

    def test_user_creation_with_defaults(self):
        """User should be created with auto-generated UUID."""
        user = User(first_name="Test", last_name="User", email="test@example.com")

        # ID should be auto-generated
        assert user.id is not None
        assert isinstance(user.id, str)
        # Should be a valid UUID string
        from uuid import UUID
        UUID(user.id)  # Raises ValueError if invalid

        # Other fields should be set
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.email == "test@example.com"

    def test_user_creation_with_explicit_id(self):
        """User can be created with explicit ID."""
        explicit_id = "test-id-123"
        user = User(
            id=explicit_id,
            first_name="Test",
            last_name="User",
            email="test@example.com",
        )

        assert user.id == explicit_id

    def test_user_creation_with_optional_fields(self):
        """User can be created with optional field values."""
        user = User(
            first_name="Admin",
            last_name="User",
            email="admin@example.com",
            phone="555-1234",
            address="123 Main St",
        )

        assert user.first_name == "Admin"
        assert user.last_name == "User"
        assert user.email == "admin@example.com"
        assert user.phone == "555-1234"
        assert user.address == "123 Main St"

    def test_user_validation_invalid_email(self):
        """Should allow any email format (no validation constraints in entity)."""
        # The User entity doesn't enforce email validation
        user = User(
            id="1",
            first_name="John",
            last_name="Doe",
            email="not-a-valid-email",  # This should be allowed
        )
        assert user.email == "not-a-valid-email"

    def test_user_validation_empty_names(self):
        """Should allow empty first or last names (no validation constraints in entity)."""
        # The User entity doesn't enforce name validation
        user = User(
            id="1",
            first_name="",  # Empty names should be allowed
            last_name="",
            email="test@example.com",
        )
        assert user.first_name == ""
        assert user.last_name == ""


class TestUserTable:
    """Test User database table operations."""

    def test_user_table_creation(self, session: Session):
        """Test creating user table records."""
        user_table = UserTable(
            id="test-id",
            first_name="Database",
            last_name="User",
            email="db.user@example.com",
        )

        session.add(user_table)
        session.commit()

        # Verify it was saved
        saved_user = session.get(UserTable, user_table.id)
        assert saved_user is not None
        assert saved_user.first_name == "Database"
        assert saved_user.email == "db.user@example.com"

    def test_user_table_query(self, session: Session):
        """Test querying user table records."""
        # Create test users
        user1 = UserTable(
            id="user1-id",
            first_name="Alice",
            last_name="Johnson",
            email="alice@example.com",
        )
        user2 = UserTable(
            id="user2-id",
            first_name="Bob",
            last_name="Wilson",
            email="bob@example.com",
        )

        session.add_all([user1, user2])
        session.commit()

        # Query by email
        statement = select(UserTable).where(UserTable.email == "alice@example.com")
        result = session.exec(statement).first()

        assert result is not None
        assert result.first_name == "Alice"
        assert result.last_name == "Johnson"

    def test_table_model_from_entity(self):
        """UserTable should be created from User entity."""
        user = User(first_name="Test", last_name="User", email="test@example.com")

        table = UserTable.model_validate(user, from_attributes=True)

        assert table.id == user.id
        assert table.first_name == user.first_name
        assert table.last_name == user.last_name
        assert table.email == user.email

    def test_entity_from_table_model(self):
        """User entity should be created from UserTable."""
        table = UserTable(
            id="test-id",
            first_name="Test",
            last_name="User",
            email="test@example.com",
            phone=None,
            address=None,
        )

        user = User.model_validate(table, from_attributes=True)

        assert user.id == table.id
        assert user.first_name == table.first_name
        assert user.last_name == table.last_name
        assert user.email == table.email


class TestUserRepository:
    """Test User repository operations."""

    @pytest.fixture
    def user_repo(self, session: Session) -> UserRepository:
        """User repository instance."""
        return UserRepository(session)

    def test_create_user(self, user_repo: UserRepository):
        """Test creating user through repository."""
        user = User(
            first_name="Repository",
            last_name="Test",
            email="repo.test@example.com",
        )

        created_user = user_repo.create(user)

        assert created_user.id == user.id
        assert created_user.first_name == "Repository"
        assert created_user.email == "repo.test@example.com"

    def test_get_user_by_id(self, user_repo: UserRepository):
        """Test retrieving user by ID."""
        # Create user first
        user = User(
            first_name="Retrieve",
            last_name="Test",
            email="retrieve.test@example.com",
        )
        created_user = user_repo.create(user)

        # Retrieve user
        retrieved_user = user_repo.get(created_user.id)

        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.first_name == "Retrieve"

    def test_get_nonexistent_user(self, user_repo: UserRepository):
        """Test retrieving non-existent user returns None."""
        result = user_repo.get("nonexistent-id")
        assert result is None

    def test_update_user(self, user_repo: UserRepository):
        """Test updating user through repository."""
        # Create user
        user = User(
            first_name="Original",
            last_name="Name",
            email="original@example.com",
        )
        created_user = user_repo.create(user)

        # Update user
        created_user.first_name = "Updated"
        created_user.email = "updated@example.com"

        updated_user = user_repo.update(created_user)

        assert updated_user.first_name == "Updated"
        assert updated_user.email == "updated@example.com"

        # Verify in database
        retrieved_user = user_repo.get(created_user.id)
        assert retrieved_user is not None
        assert retrieved_user.first_name == "Updated"
        assert retrieved_user.email == "updated@example.com"


class TestUserRepositoryMocked:
    """Test the UserRepository with mocked dependencies for isolation."""

    def setup_method(self):
        """Set up test fixtures."""
        from unittest.mock import Mock
        self.mock_session = Mock()
        self.repo = UserRepository(self.mock_session)

    def test_repository_initialization(self):
        """Repository should initialize with session."""
        assert self.repo._session == self.mock_session

    def test_get_existing_user(self):
        """get() should return User when record exists."""
        # Mock database row
        mock_row = UserTable(
            id="test-id",
            first_name="Test",
            last_name="User",
            email="test@example.com",
            phone=None,
            address=None,
        )
        self.mock_session.get.return_value = mock_row

        user = self.repo.get("test-id")

        # Verify session was called correctly
        self.mock_session.get.assert_called_once_with(UserTable, "test-id")

        # Verify returned user
        assert user is not None
        assert user.id == "test-id"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        assert user.email == "test@example.com"

    def test_get_nonexistent_user(self):
        """get() should return None when record doesn't exist."""
        self.mock_session.get.return_value = None

        user = self.repo.get("nonexistent-id")

        assert user is None
        self.mock_session.get.assert_called_once_with(UserTable, "nonexistent-id")

    def test_create_user(self):
        """create() should persist User and return it unchanged."""
        user = User(first_name="New", last_name="User", email="new@example.com")

        result = self.repo.create(user)

        # Verify session operations
        self.mock_session.add.assert_called_once()
        added_table = self.mock_session.add.call_args[0][0]
        assert isinstance(added_table, UserTable)
        assert added_table.id == user.id
        assert added_table.first_name == user.first_name
        assert added_table.last_name == user.last_name
        assert added_table.email == user.email

        # Verify return value is unchanged entity
        assert result is user


class TestUserIdentityEntity:
    """Test UserIdentity domain entity."""

    def test_user_identity_creation(self):
        """Test user identity entity creation."""
        identity = UserIdentity(
            issuer="https://auth.example.com",
            subject="user-12345",
            uid_claim="auth.example.com|user-12345",
            user_id="user-uuid-123",
        )

        assert identity.issuer == "https://auth.example.com"
        assert identity.subject == "user-12345"
        assert identity.uid_claim == "auth.example.com|user-12345"
        assert identity.user_id == "user-uuid-123"
        assert identity.id is not None  # Auto-generated
        assert identity.created_at is not None

    def test_user_identity_optional_uid_claim(self):
        """Test user identity with optional UID claim."""
        identity = UserIdentity(
            issuer="https://auth.example.com",
            subject="user-67890",
            uid_claim=None,  # Optional
            user_id="user-uuid-456",
        )

        assert identity.issuer == "https://auth.example.com"
        assert identity.subject == "user-67890"
        assert identity.uid_claim is None
        assert identity.user_id == "user-uuid-456"


class TestUserIdentityTable:
    """Test UserIdentity database table operations."""

    def test_user_identity_table_creation(self, session: Session):
        """Test creating user identity table records."""
        identity_table = UserIdentityTable(
            id="test-id",
            issuer="https://db.auth.example.com",
            subject="db-user-123",
            uid_claim="db.auth.example.com|db-user-123",
            user_id="db-user-uuid-123",
        )

        session.add(identity_table)
        session.commit()

        # Verify it was saved
        saved_identity = session.get(UserIdentityTable, identity_table.id)
        assert saved_identity is not None
        assert saved_identity.issuer == "https://db.auth.example.com"
        assert saved_identity.subject == "db-user-123"

    def test_user_identity_table_unique_constraints(self, session: Session):
        """Test unique constraints on user identity table."""
        # Create first identity
        identity1 = UserIdentityTable(
            id="user1-id",
            issuer="https://auth.example.com",
            subject="unique-user-123",
            uid_claim="auth.example.com|unique-user-123",
            user_id="user-uuid-123",
        )
        session.add(identity1)
        session.commit()

        # Try to create duplicate identity (same issuer + subject)
        identity2 = UserIdentityTable(
            id="user2-id",
            issuer="https://auth.example.com",
            subject="unique-user-123",  # Same subject
            uid_claim="auth.example.com|unique-user-123",
            user_id="user-uuid-456",  # Different user
        )
        session.add(identity2)

        # This should raise a constraint violation
        with pytest.raises(Exception):  # SQLite/DB specific error
            session.commit()


class TestUserIdentityRepository:
    """Test UserIdentity repository operations."""

    @pytest.fixture
    def identity_repo(self, session: Session) -> UserIdentityRepository:
        """User identity repository instance."""
        return UserIdentityRepository(session)

    def test_create_user_identity(self, identity_repo: UserIdentityRepository):
        """Test creating user identity through repository."""
        identity = UserIdentity(
            issuer="https://repo.auth.example.com",
            subject="repo-user-123",
            uid_claim="repo.auth.example.com|repo-user-123",
            user_id="repo-user-uuid-123",
        )

        created_identity = identity_repo.create(identity)

        assert created_identity.id == identity.id
        assert created_identity.issuer == "https://repo.auth.example.com"
        assert created_identity.subject == "repo-user-123"

    def test_get_by_uid(self, identity_repo: UserIdentityRepository):
        """Test retrieving user identity by UID claim."""
        identity = UserIdentity(
            issuer="https://uid.auth.example.com",
            subject="uid-user-123",
            uid_claim="uid.auth.example.com|uid-user-123",
            user_id="uid-user-uuid-123",
        )
        identity_repo.create(identity)

        # Retrieve by UID
        retrieved_identity = identity_repo.get_by_uid(
            "uid.auth.example.com|uid-user-123"
        )

        assert retrieved_identity is not None
        assert retrieved_identity.issuer == "https://uid.auth.example.com"
        assert retrieved_identity.subject == "uid-user-123"

    def test_get_by_uid_nonexistent(self, identity_repo: UserIdentityRepository):
        """Test retrieving non-existent identity by UID returns None."""
        result = identity_repo.get_by_uid("nonexistent-uid")
        assert result is None

    def test_get_by_issuer_subject(self, identity_repo: UserIdentityRepository):
        """Test retrieving user identity by issuer and subject."""
        identity = UserIdentity(
            issuer="https://issuer.auth.example.com",
            subject="issuer-user-123",
            uid_claim=None,  # No UID claim
            user_id="issuer-user-uuid-123",
        )
        identity_repo.create(identity)

        # Retrieve by issuer and subject
        retrieved_identity = identity_repo.get_by_issuer_subject(
            "https://issuer.auth.example.com", "issuer-user-123"
        )

        assert retrieved_identity is not None
        assert retrieved_identity.issuer == "https://issuer.auth.example.com"
        assert retrieved_identity.subject == "issuer-user-123"

    def test_get_by_issuer_subject_nonexistent(
        self, identity_repo: UserIdentityRepository
    ):
        """Test retrieving non-existent identity by issuer/subject returns None."""
        result = identity_repo.get_by_issuer_subject(
            "https://nonexistent.example.com", "nonexistent-subject"
        )
        assert result is None


class TestDataLayerIntegration:
    """Test integrated data layer operations."""

    def test_user_with_multiple_identities(self, session: Session):
        """Test user with multiple identity mappings."""
        user_repo = UserRepository(session)
        identity_repo = UserIdentityRepository(session)

        # Create user
        user = User(
            first_name="Multi",
            last_name="Identity",
            email="multi.identity@example.com",
        )
        created_user = user_repo.create(user)

        # Create multiple identities for same user
        identity1 = UserIdentity(
            issuer="https://google.com",
            subject="google-user-123",
            uid_claim="google.com|google-user-123",
            user_id=created_user.id,
        )

        identity2 = UserIdentity(
            issuer="https://github.com",
            subject="github-user-456",
            uid_claim="github.com|github-user-456",
            user_id=created_user.id,
        )

        identity_repo.create(identity1)
        identity_repo.create(identity2)

        # Verify both identities point to same user
        retrieved_identity1 = identity_repo.get_by_uid("google.com|google-user-123")
        retrieved_identity2 = identity_repo.get_by_uid("github.com|github-user-456")

        assert retrieved_identity1 is not None
        assert retrieved_identity2 is not None

        assert retrieved_identity1.user_id == created_user.id
        assert retrieved_identity2.user_id == created_user.id
        assert retrieved_identity1.user_id == retrieved_identity2.user_id

    def test_cascade_operations(self, session: Session):
        """Test that related operations work correctly."""
        user_repo = UserRepository(session)
        identity_repo = UserIdentityRepository(session)

        # Create user and identity
        user = User(
            first_name="Cascade",
            last_name="Test",
            email="cascade.test@example.com",
        )
        created_user = user_repo.create(user)

        identity = UserIdentity(
            issuer="https://cascade.example.com",
            subject="cascade-user-123",
            uid_claim="cascade.example.com|cascade-user-123",
            user_id=created_user.id,
        )
        identity_repo.create(identity)

        # Verify user can be retrieved via identity
        retrieved_identity = identity_repo.get_by_uid(
            "cascade.example.com|cascade-user-123"
        )

        assert retrieved_identity is not None
        assert retrieved_identity.user_id == created_user.id

        retrieved_user = user_repo.get(retrieved_identity.user_id)
        assert retrieved_user is not None
        assert retrieved_user.first_name == "Cascade"
        assert retrieved_user.email == "cascade.test@example.com"
