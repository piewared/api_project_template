"""Unit tests for session service."""

import time
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from sqlmodel import Session

from src.core.services import session_service
from src.core.services.session_service import AuthSession, UserSession
from src.entities.user import User
from src.entities.user_identity import UserIdentity


class TestSessionService:
    """Test session service functions in isolation."""

    def test_create_auth_session(self):
        """Test creating temporary auth session for OIDC flow."""
        session_id = session_service.create_auth_session(
            pkce_verifier="test-verifier",
            state="test-state",
            provider="google",
            redirect_uri="/dashboard",
        )

        # Should return a session ID
        assert isinstance(session_id, str)
        assert len(session_id) > 0

        # Should be able to retrieve the session
        auth_session = session_service.get_auth_session(session_id)
        assert auth_session is not None
        assert isinstance(auth_session, AuthSession)
        assert auth_session.pkce_verifier == "test-verifier"
        assert auth_session.state == "test-state"
        assert auth_session.provider == "google"
        assert auth_session.redirect_uri == "/dashboard"

        # Should have reasonable expiry (10 minutes)
        now = int(time.time())
        assert auth_session.expires_at > now + 500  # At least 8+ minutes
        assert auth_session.expires_at <= now + 600  # At most 10 minutes

    def test_get_auth_session_nonexistent(self):
        """Test getting non-existent auth session returns None."""
        result = session_service.get_auth_session("nonexistent-session")
        assert result is None

    def test_get_auth_session_expired(self):
        """Test getting expired auth session returns None and cleans up."""
        # Create session that expires immediately
        session_id = session_service.create_auth_session(
            pkce_verifier="test-verifier",
            state="test-state",
            provider="google",
            redirect_uri="/dashboard",
        )

        # Manually expire it by modifying the internal storage
        auth_session = session_service._auth_sessions[session_id]
        auth_session.expires_at = int(time.time()) - 1  # Expired 1 second ago

        # Should return None and clean up
        result = session_service.get_auth_session(session_id)
        assert result is None
        assert session_id not in session_service._auth_sessions

    def test_delete_auth_session(self):
        """Test deleting auth session."""
        session_id = session_service.create_auth_session(
            pkce_verifier="test-verifier",
            state="test-state",
            provider="google",
            redirect_uri="/dashboard",
        )

        # Verify it exists
        assert session_service.get_auth_session(session_id) is not None

        # Delete it
        session_service.delete_auth_session(session_id)

        # Should be gone
        assert session_service.get_auth_session(session_id) is None

    def test_delete_nonexistent_auth_session(self):
        """Test deleting non-existent auth session doesn't error."""
        # Should not raise an exception
        session_service.delete_auth_session("nonexistent-session")

    def test_create_user_session(self):
        """Test creating persistent user session."""
        user_id = "12345678-1234-5678-9abc-123456789012"

        session_id = session_service.create_user_session(
            user_id=user_id,
            provider="google",
            refresh_token="refresh-123",
            access_token="access-456",
            expires_at=int(time.time()) + 3600,
        )

        # Should return a session ID
        assert isinstance(session_id, str)
        assert len(session_id) > 0

        # Should be able to retrieve the session
        user_session = session_service.get_user_session(session_id)
        assert user_session is not None
        assert isinstance(user_session, UserSession)
        assert user_session.user_id == user_id
        assert user_session.provider == "google"
        assert user_session.refresh_token == "refresh-123"
        assert user_session.access_token == "access-456"

    def test_get_user_session_nonexistent(self):
        """Test getting non-existent user session returns None."""
        result = session_service.get_user_session("nonexistent-session")
        assert result is None

    def test_get_user_session_expired(self):
        """Test getting expired user session returns None and cleans up."""
        user_id = "12345678-1234-5678-9abc-123456789012"

        session_id = session_service.create_user_session(
            user_id=user_id,
            provider="google",
            refresh_token="refresh-123",
            access_token="access-456",
            expires_at=int(time.time()) + 3600,
        )

        # Manually expire it
        user_session = session_service._user_sessions[session_id]
        user_session.expires_at = int(time.time()) - 1

        # Should return None and clean up
        result = session_service.get_user_session(session_id)
        assert result is None
        assert session_id not in session_service._user_sessions

    def test_get_user_session_updates_last_accessed(self):
        """Test getting user session updates last_accessed_at."""
        user_id = "12345678-1234-5678-9abc-123456789012"

        # Create session with a fixed time
        base_time = int(time.time())
        session_id = session_service.create_user_session(
            user_id=user_id,
            provider="google",
            refresh_token="refresh-123",
            access_token="access-456",
            expires_at=base_time + 3600,
        )

        # Get initial last accessed time
        user_session = session_service.get_user_session(session_id)
        assert user_session is not None
        initial_time = user_session.last_accessed_at

        # Mock time.time to return a later time for the next call
        with patch('time.time', return_value=base_time + 2):
            user_session = session_service.get_user_session(session_id)
            assert user_session is not None
            updated_time = user_session.last_accessed_at

            # Should be updated
            assert updated_time > initial_time

    def test_delete_user_session(self):
        """Test deleting user session."""
        user_id = "12345678-1234-5678-9abc-123456789012"

        session_id = session_service.create_user_session(
            user_id=user_id,
            provider="google",
            refresh_token="refresh-123",
            access_token="access-456",
            expires_at=int(time.time()) + 3600,
        )

        # Verify it exists
        assert session_service.get_user_session(session_id) is not None

        # Delete it
        session_service.delete_user_session(session_id)

        # Should be gone
        assert session_service.get_user_session(session_id) is None

    def test_generate_csrf_token(self):
        """Test CSRF token generation."""
        session_id = "test-session-123"

        csrf_token = session_service.generate_csrf_token(session_id)

        # Should be a non-empty string
        assert isinstance(csrf_token, str)
        assert len(csrf_token) > 0

        # Should be deterministic for same session and time window
        csrf_token2 = session_service.generate_csrf_token(session_id)
        assert csrf_token == csrf_token2

        # Should be different for different session
        csrf_token3 = session_service.generate_csrf_token("different-session")
        assert csrf_token != csrf_token3

    def test_validate_csrf_token_valid(self):
        """Test validating a valid CSRF token."""
        session_id = "test-session-123"
        csrf_token = session_service.generate_csrf_token(session_id)

        # Should validate correctly
        is_valid = session_service.validate_csrf_token(session_id, csrf_token)
        assert is_valid is True

    def test_validate_csrf_token_invalid(self):
        """Test validating an invalid CSRF token."""
        session_id = "test-session-123"

        # Should reject invalid token
        is_valid = session_service.validate_csrf_token(session_id, "invalid-token")
        assert is_valid is False

        # Should reject token for wrong session
        csrf_token = session_service.generate_csrf_token("different-session")
        is_valid = session_service.validate_csrf_token(session_id, csrf_token)
        assert is_valid is False

    def test_validate_csrf_token_malformed(self):
        """Test validating malformed CSRF token doesn't crash."""
        session_id = "test-session-123"

        # Should handle empty/None gracefully
        is_valid = session_service.validate_csrf_token(session_id, "")
        assert is_valid is False

        is_valid = session_service.validate_csrf_token(session_id, None)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_provision_user_from_claims_new_user(self, session: Session):
        """Test JIT user provisioning for new user."""
        claims = {
            "iss": "https://test.provider",
            "sub": "user-12345",
            "email": "test@example.com",
            "given_name": "Test",
            "family_name": "User",
        }

        with patch("src.runtime.db.session", return_value=session):
            user = await session_service.provision_user_from_claims(claims, "test")

            # Should create a new user
            assert isinstance(user, User)
            assert user.email == "test@example.com"
            assert user.first_name == "Test"
            assert user.last_name == "User"

    @pytest.mark.asyncio
    async def test_provision_user_from_claims_existing_user(self, session: Session):
        """Test JIT user provisioning for existing user."""
        # Create existing user first
        from src.entities.user import UserRepository, UserTable
        from src.entities.user_identity import UserIdentityRepository, UserIdentityTable

        user_repo = UserRepository(session)
        identity_repo = UserIdentityRepository(session)

        # Create user and identity
        existing_user = user_repo.create(
            User(first_name="Existing", last_name="User", email="existing@example.com")
        )

        identity_repo.create(
            UserIdentity(
                user_id=existing_user.id,
                issuer="https://test.provider",
                subject="user-12345",
                uid_claim="https://test.provider|user-12345",  # Set the UID claim that the function will look for
            )
        )

        # Commit the test data to ensure it's visible
        session.commit()

        claims = {
            "iss": "https://test.provider",
            "sub": "user-12345",
            "email": "updated@example.com",  # Updated email
            "given_name": "Updated",
            "family_name": "User",
        }

        with patch("src.core.services.session_service.session", return_value=session):
            # Mock the close method to prevent the function from closing our test session
            with patch.object(session, 'close', return_value=None):
                user = await session_service.provision_user_from_claims(claims, "test")

                # Should return the existing user with updated info
                assert user.id == existing_user.id
                # Email should be updated
                assert user.email == "updated@example.com"
                assert user.first_name == "Updated"

    @pytest.mark.asyncio
    async def test_refresh_user_session_success(self):
        """Test successful user session refresh."""
        user_id = "12345678-1234-5678-9abc-123456789012"

        # Create initial session
        session_id = session_service.create_user_session(
            user_id=user_id,
            provider="google",
            refresh_token="old-refresh-token",
            access_token="old-access-token",
            expires_at=int(time.time()) + 3600,
        )

        # Mock the OIDC client service
        with patch(
            "src.core.services.oidc_client_service.refresh_access_token"
        ) as mock_refresh:
            from src.core.services.oidc_client_service import TokenResponse

            mock_refresh.return_value = TokenResponse(
                access_token="new-access-token",
                token_type="Bearer",
                expires_in=3600,
                refresh_token="new-refresh-token",
            )

            # Refresh the session
            new_session_id = await session_service.refresh_user_session(session_id)

            # Should return new session ID
            assert isinstance(new_session_id, str)
            assert new_session_id != session_id

            # Old session should be gone
            assert session_service.get_user_session(session_id) is None

            # New session should exist with updated tokens
            new_session = session_service.get_user_session(new_session_id)
            assert new_session is not None
            assert new_session.access_token == "new-access-token"
            assert new_session.refresh_token == "new-refresh-token"

            # Mock should have been called correctly
            mock_refresh.assert_called_once_with("old-refresh-token", "google")

    @pytest.mark.asyncio
    async def test_refresh_user_session_not_found(self):
        """Test refreshing non-existent session raises error."""
        with pytest.raises(ValueError, match="Session not found or expired"):
            await session_service.refresh_user_session("nonexistent-session")

    @pytest.mark.asyncio
    async def test_refresh_user_session_no_refresh_token(self):
        """Test refreshing session without refresh token raises error."""
        user_id = "12345678-1234-5678-9abc-123456789012"

        # Create session without refresh token
        session_id = session_service.create_user_session(
            user_id=user_id,
            provider="google",
            refresh_token=None,  # No refresh token
            access_token="access-token",
            expires_at=int(time.time()) + 3600,
        )

        with pytest.raises(ValueError, match="No refresh token available"):
            await session_service.refresh_user_session(session_id)

    @pytest.mark.asyncio
    async def test_refresh_user_session_refresh_fails(self):
        """Test refresh session when token refresh fails."""
        user_id = "12345678-1234-5678-9abc-123456789012"

        session_id = session_service.create_user_session(
            user_id=user_id,
            provider="google",
            refresh_token="refresh-token",
            access_token="access-token",
            expires_at=int(time.time()) + 3600,
        )

        # Mock refresh to fail
        with patch(
            "src.core.services.oidc_client_service.refresh_access_token"
        ) as mock_refresh:
            mock_refresh.side_effect = Exception("Token refresh failed")

            with pytest.raises(ValueError, match="Token refresh failed"):
                await session_service.refresh_user_session(session_id)

            # Session should be cleaned up on failure
            assert session_service.get_user_session(session_id) is None
