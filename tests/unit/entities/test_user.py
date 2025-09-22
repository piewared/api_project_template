"""Unit tests for the user entity package.

Tests the hybrid entity structure where domain model, database model,
and repository are colocated in the same package.
"""

from unittest.mock import Mock
from uuid import UUID

import pytest

from src.entities.user import User, UserRepository, UserTable


class TestUser:
    """Test the User domain entity."""

    def test_user_creation_with_defaults(self):
        """User should be created with auto-generated UUID."""
        user = User(first_name="Test", last_name="User", email="test@example.com")

        # ID should be auto-generated
        assert user.id is not None
        assert isinstance(user.id, str)
        # Should be a valid UUID string
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

    def test_create_valid_user(self):
        """Should create a valid user with required fields."""
        user = User(
            id="1", first_name="John", last_name="Doe", email="john.doe@example.com"
        )

        assert user.id == "1"
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.email == "john.doe@example.com"
        assert user.phone is None
        assert user.address is None

    def test_create_user_with_optional_fields(self):
        """Should create a user with all optional fields."""
        user = User(
            id="2",
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
            phone="+1-555-123-4567",
            address="123 Main St, Anytown, USA",
        )

        assert user.phone == "+1-555-123-4567"
        assert user.address == "123 Main St, Anytown, USA"

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

    def test_user_equality(self):
        """Should compare users by their attributes."""
        user1 = User(
            id="1", first_name="John", last_name="Doe", email="john.doe@example.com"
        )

        user2 = User(
            id="1", first_name="John", last_name="Doe", email="john.doe@example.com"
        )

        user3 = User(
            id="2", first_name="Jane", last_name="Smith", email="jane.smith@example.com"
        )

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



class TestUserTable:
    """Test the UserTable database model."""

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
    """Test the UserRepository data access layer."""

    def setup_method(self):
        """Set up test fixtures."""
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
