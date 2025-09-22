"""Unit tests for the user_identity entity package.

Tests the hybrid entity structure for UserIdentity which handles
JWT authentication provider mappings.
"""

from datetime import datetime
from unittest.mock import Mock
from uuid import UUID

import pytest

from src.entities.user_identity import (
    UserIdentity,
    UserIdentityRepository,
    UserIdentityTable,
)


class TestUserIdentity:
    """Test the UserIdentity domain entity."""

    def test_user_identity_creation_with_defaults(self):
        """UserIdentity should be created with auto-generated UUID."""
        identity = UserIdentity(
            user_id="user-123",
            issuer="https://accounts.google.com",
            subject="google-user-456",
        )

        # ID should be auto-generated
        assert identity.id is not None
        assert isinstance(identity.id, str)
        # Should be a valid UUID string
        UUID(identity.id)  # Raises ValueError if invalid

        # Other fields should be set
        assert identity.user_id == "user-123"
        assert identity.issuer == "https://accounts.google.com"
        assert identity.subject == "google-user-456"
        assert identity.uid_claim is None
        assert isinstance(identity.created_at, datetime)

    def test_user_identity_creation_with_explicit_id(self):
        """UserIdentity can be created with explicit ID."""
        explicit_id = "identity-id-123"
        identity = UserIdentity(
            id=explicit_id,
            user_id="user-123",
            issuer="https://github.com",
            subject="github-user-789",
        )

        assert identity.id == explicit_id

    def test_user_identity_with_uid_claim(self):
        """UserIdentity should handle optional uid_claim."""
        identity = UserIdentity(
            user_id="user-123",
            issuer="https://auth0.example.com",
            subject="auth0|123456",
            uid_claim="uid_value_123",
        )
        assert identity.uid_claim == "uid_value_123"

    def test_user_identity_with_different_issuers(self):
        """UserIdentity should work with different JWT issuers."""
        issuers = [
            "https://accounts.google.com",
            "https://github.com",
            "https://login.microsoftonline.com",
            "https://auth0.example.com",
        ]

        for issuer in issuers:
            identity = UserIdentity(
                user_id="user-123", issuer=issuer, subject=f"subject-for-{issuer}"
            )
            assert identity.issuer == issuer


class TestUserIdentityTable:
    """Test the UserIdentityTable database model."""

    def test_table_model_from_entity(self):
        """UserIdentityTable should be created from UserIdentity entity."""
        identity = UserIdentity(
            user_id="user-123",
            issuer="https://accounts.google.com",
            subject="google-user-456",
        )

        table = UserIdentityTable.model_validate(identity, from_attributes=True)

        assert table.id == identity.id
        assert table.user_id == identity.user_id
        assert table.issuer == identity.issuer
        assert table.subject == identity.subject
        assert table.uid_claim == identity.uid_claim
        assert table.created_at == identity.created_at

    def test_entity_from_table_model(self):
        """UserIdentity entity should be created from UserIdentityTable."""
        table = UserIdentityTable(
            id="identity-id",
            user_id="user-123",
            issuer="https://github.com",
            subject="github-user-789",
            uid_claim=None,
            created_at=datetime.now(),
        )

        identity = UserIdentity.model_validate(table, from_attributes=True)

        assert identity.id == table.id
        assert identity.user_id == table.user_id
        assert identity.issuer == table.issuer
        assert identity.subject == table.subject
        assert identity.uid_claim == table.uid_claim
        assert identity.created_at == table.created_at


class TestUserIdentityRepository:
    """Test the UserIdentityRepository data access layer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_session = Mock()
        self.repo = UserIdentityRepository(self.mock_session)

    def test_repository_initialization(self):
        """Repository should initialize with session."""
        assert self.repo._session == self.mock_session

    def test_get_existing_identity_by_uid(self):
        """get_by_uid() should return UserIdentity when record exists."""
        # Mock database row
        mock_row = UserIdentityTable(
            id="identity-id",
            user_id="user-123",
            issuer="https://accounts.google.com",
            subject="google-user-456",
            uid_claim="uid_123",
            created_at=datetime.now(),
        )

        # Mock the query execution
        mock_result = Mock()
        mock_result.first.return_value = mock_row
        self.mock_session.exec.return_value = mock_result

        identity = self.repo.get_by_uid("uid_123")

        # Verify returned identity
        assert identity is not None
        assert identity.id == "identity-id"
        assert identity.user_id == "user-123"
        assert identity.issuer == "https://accounts.google.com"
        assert identity.subject == "google-user-456"
        assert identity.uid_claim == "uid_123"

    def test_get_nonexistent_identity_by_uid(self):
        """get_by_uid() should return None when record doesn't exist."""
        # Mock empty query result
        mock_result = Mock()
        mock_result.first.return_value = None
        self.mock_session.exec.return_value = mock_result

        identity = self.repo.get_by_uid("nonexistent-uid")

        assert identity is None

    def test_create_identity(self):
        """create() should persist UserIdentity and return it unchanged."""
        identity = UserIdentity(
            user_id="user-123",
            issuer="https://accounts.google.com",
            subject="google-user-456",
        )

        result = self.repo.create(identity)

        # Verify session operations
        self.mock_session.add.assert_called_once()
        added_table = self.mock_session.add.call_args[0][0]
        assert isinstance(added_table, UserIdentityTable)
        assert added_table.id == identity.id
        assert added_table.user_id == identity.user_id
        assert added_table.issuer == identity.issuer
        assert added_table.subject == identity.subject

        # Verify return value is unchanged entity
        assert result is identity

    def test_get_by_issuer_subject_found(self):
        """get_by_issuer_subject() should return UserIdentity when found."""
        mock_row = UserIdentityTable(
            id="identity-id",
            user_id="user-123",
            issuer="https://accounts.google.com",
            subject="google-user-456",
            uid_claim=None,
            created_at=datetime.now(),
        )

        # Mock the query execution
        mock_result = Mock()
        mock_result.first.return_value = mock_row
        self.mock_session.exec.return_value = mock_result

        identity = self.repo.get_by_issuer_subject(
            "https://accounts.google.com", "google-user-456"
        )

        # Verify identity was found and converted
        assert identity is not None
        assert identity.issuer == "https://accounts.google.com"
        assert identity.subject == "google-user-456"
        assert identity.user_id == "user-123"

    def test_get_by_issuer_subject_not_found(self):
        """get_by_issuer_subject() should return None when not found."""
        # Mock empty query result
        mock_result = Mock()
        mock_result.first.return_value = None
        self.mock_session.exec.return_value = mock_result

        identity = self.repo.get_by_issuer_subject(
            "https://accounts.google.com", "nonexistent"
        )

        assert identity is None
