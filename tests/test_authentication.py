"""Consolidated authentication system tests.

This module combines and consolidates tests for:
- OIDC client service (token exchange, user claims, PKCE flow)
- Session service (auth sessions, user sessions, JIT provisioning)
- BFF authentication router (login initiation, callback handling, /me endpoint)
- Authentication dependencies and state management

Replaces:
- tests/unit/core/test_oidc_client_service.py
- tests/unit/core/test_session_service.py
- tests/unit/api/test_auth_bff_router.py (partially)
- Various other auth-related tests
"""

import time
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.core.services import oidc_client_service, session_service
from src.core.services.oidc_client_service import TokenResponse
from src.core.services.session_service import AuthSession, UserSession
from src.entities.user import User
from src.entities.user_identity import UserIdentity
from src.runtime.config import with_context


class TestOIDCClientService:
    """Test OIDC client functionality."""

    def test_generate_pkce_pair(self):
        """Test PKCE verifier and challenge generation."""
        verifier, challenge = oidc_client_service.generate_pkce_pair()

        # Should generate valid PKCE pairs
        assert isinstance(verifier, str) and len(verifier) > 0
        assert isinstance(challenge, str) and len(challenge) > 0

        # Should be different each time
        verifier2, challenge2 = oidc_client_service.generate_pkce_pair()
        assert verifier != verifier2
        assert challenge != challenge2

    def test_generate_state(self):
        """Test state parameter generation."""
        state1 = oidc_client_service.generate_state()
        state2 = oidc_client_service.generate_state()

        assert isinstance(state1, str) and len(state1) > 0
        assert state1 != state2

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_success(
        self, base_oidc_provider, mock_http_response_factory, auth_test_config
    ):
        """Test successful token exchange."""
        mock_response_data = {
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "mock-refresh-token",
            "id_token": "mock-id-token",
        }
        mock_response = mock_http_response_factory(mock_response_data)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            with with_context(config_override=auth_test_config):
                result = await oidc_client_service.exchange_code_for_tokens(
                    code="test-auth-code",
                    pkce_verifier="test-verifier",
                    provider="default",
                )

                assert isinstance(result, TokenResponse)
                assert result.access_token == "mock-access-token"
                assert result.token_type == "Bearer"
                assert result.expires_in == 3600

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_http_error(
        self, base_oidc_provider, mock_http_response_factory, auth_test_config
    ):
        """Test token exchange with HTTP error."""
        mock_response = mock_http_response_factory({}, status_code=400)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            with with_context(config_override=auth_test_config):
                with pytest.raises(httpx.HTTPStatusError):
                    await oidc_client_service.exchange_code_for_tokens(
                        code="test-auth-code",
                        pkce_verifier="test-verifier",
                        provider="default",
                    )

    @pytest.mark.asyncio
    async def test_get_user_claims_from_id_token(
        self, base_oidc_provider, test_user_claims, auth_test_config
    ):
        """Test extracting user claims from ID token."""
        with patch("src.core.services.jwt_service.verify_jwt") as mock_verify:
            mock_verify.return_value = test_user_claims

            with with_context(config_override=auth_test_config):
                result = await oidc_client_service.get_user_claims(
                    access_token="mock-access-token",
                    id_token="mock-id-token",
                    provider="default",
                )

                assert result == test_user_claims
                mock_verify.assert_called_once_with("mock-id-token")


class TestSessionService:
    """Test session management functionality."""

    def test_auth_session_lifecycle(self):
        """Test complete auth session lifecycle."""
        # Create session
        session_id = session_service.create_auth_session(
            pkce_verifier="test-verifier",
            state="test-state",
            provider="google",
            redirect_uri="/dashboard",
        )

        assert isinstance(session_id, str)

        # Retrieve session
        auth_session = session_service.get_auth_session(session_id)
        assert auth_session is not None
        assert isinstance(auth_session, AuthSession)
        assert auth_session.pkce_verifier == "test-verifier"
        assert auth_session.state == "test-state"

        # Delete session
        session_service.delete_auth_session(session_id)
        assert session_service.get_auth_session(session_id) is None

    def test_auth_session_expiry(self):
        """Test auth session expiry handling."""
        session_id = session_service.create_auth_session(
            pkce_verifier="test-verifier",
            state="test-state",
            provider="google",
            redirect_uri="/dashboard",
        )

        # Manually expire session
        auth_session = session_service._auth_sessions[session_id]
        auth_session.expires_at = int(time.time()) - 1

        # Should return None and clean up
        result = session_service.get_auth_session(session_id)
        assert result is None
        assert session_id not in session_service._auth_sessions

    def test_user_session_lifecycle(self):
        """Test complete user session lifecycle."""
        user_id = "12345678-1234-5678-9abc-123456789012"

        # Create session
        session_id = session_service.create_user_session(
            user_id=user_id,
            provider="google",
            refresh_token="refresh-123",
            access_token="access-456",
            expires_at=int(time.time()) + 3600,
        )

        assert isinstance(session_id, str)

        # Retrieve session
        user_session = session_service.get_user_session(session_id)
        assert user_session is not None
        assert isinstance(user_session, UserSession)
        assert user_session.user_id == user_id

        # Delete session
        session_service.delete_user_session(session_id)
        assert session_service.get_user_session(session_id) is None

    def test_user_session_updates_last_accessed(self):
        """Test user session last_accessed_at updates."""
        user_id = "12345678-1234-5678-9abc-123456789012"
        base_time = int(time.time())

        session_id = session_service.create_user_session(
            user_id=user_id,
            provider="google",
            refresh_token="refresh-123",
            access_token="access-456",
            expires_at=base_time + 3600,
        )

        # Get initial access time
        user_session = session_service.get_user_session(session_id)
        assert user_session is not None
        initial_time = user_session.last_accessed_at

        # Mock time to return later time for next access
        with patch("time.time", return_value=base_time + 2):
            user_session = session_service.get_user_session(session_id)
            assert user_session is not None
            updated_time = user_session.last_accessed_at
            assert updated_time > initial_time

    @pytest.mark.asyncio
    async def test_provision_user_from_claims_new_user(self, populated_session):
        """Test JIT user provisioning for new user."""
        claims = {
            "iss": "https://new-provider.test",
            "sub": "new-user-67890",
            "email": "newuser@example.com",
            "given_name": "New",
            "family_name": "User",
        }

        with patch(
            "src.core.services.session_service.session", return_value=populated_session
        ):
            with patch.object(populated_session, "close", return_value=None):
                user = await session_service.provision_user_from_claims(claims, "test")

                assert isinstance(user, User)
                assert user.email == "newuser@example.com"
                assert user.first_name == "New"
                assert user.last_name == "User"

    @pytest.mark.asyncio
    async def test_provision_user_from_claims_existing_user(
        self, session, test_user, test_user_identity
    ):
        """Test JIT user provisioning returns existing user with updated info."""
        # Populate session with the specific test fixtures
        from src.entities.user import UserRepository
        from src.entities.user_identity import UserIdentityRepository

        user_repo = UserRepository(session)
        identity_repo = UserIdentityRepository(session)

        # Create the test user and identity in the session
        user_repo.create(test_user)
        identity_repo.create(test_user_identity)
        session.commit()

        claims = {
            "iss": test_user_identity.issuer,
            "sub": test_user_identity.subject,
            "email": "updated@example.com",
            "given_name": "Updated",
            "family_name": "User",
        }

        with patch("src.core.services.session_service.session", return_value=session):
            with patch.object(session, "close", return_value=None):
                user = await session_service.provision_user_from_claims(claims, "test")

                # Should return existing user with updated info
                assert user.id == test_user.id
                assert user.email == "updated@example.com"
                assert user.first_name == "Updated"

    def test_csrf_token_generation_and_validation(self):
        """Test CSRF token generation and validation."""
        session_id = "test-session-123"

        # Generate token
        csrf_token = session_service.generate_csrf_token(session_id)
        assert isinstance(csrf_token, str) and len(csrf_token) > 0

        # Should validate correctly
        assert session_service.validate_csrf_token(session_id, csrf_token) is True

        # Should reject invalid token
        assert session_service.validate_csrf_token(session_id, "invalid-token") is False

        # Should reject None
        assert session_service.validate_csrf_token(session_id, None) is False


class TestBFFAuthenticationRouter:
    """Test BFF authentication router endpoints."""

    def test_initiate_login_success(self, auth_test_client):
        """Test successful login initiation."""
        with (
            patch(
                "src.core.services.oidc_client_service.generate_pkce_pair"
            ) as mock_pkce,
            patch("src.core.services.oidc_client_service.generate_state") as mock_state,
            patch(
                "src.core.services.session_service.create_auth_session"
            ) as mock_create_session,
        ):
            mock_pkce.return_value = ("test-verifier", "test-challenge")
            mock_state.return_value = "test-state"
            mock_create_session.return_value = "auth-session-123"

            response = auth_test_client.get("/auth/web/login", follow_redirects=False)

            assert response.status_code == status.HTTP_302_FOUND

            # Verify redirect to OIDC provider
            location = response.headers["Location"]
            parsed = urlparse(location)
            query_params = parse_qs(parsed.query)

            assert parsed.hostname == "mock-provider.test"
            assert query_params["client_id"][0] == "test-client-id"
            assert query_params["response_type"][0] == "code"
            assert query_params["state"][0] == "test-state"
            assert query_params["code_challenge"][0] == "test-challenge"

    def test_callback_success(
        self,
        auth_test_client,
        test_auth_session,
        test_user,
        test_token_response,
        test_user_claims,
    ):
        """Test successful callback handling."""
        with (
            patch(
                "src.core.services.session_service.get_auth_session",
                return_value=test_auth_session,
            ),
            patch(
                "src.core.services.oidc_client_service.exchange_code_for_tokens",
                return_value=test_token_response,
            ),
            patch(
                "src.core.services.oidc_client_service.get_user_claims",
                return_value=test_user_claims,
            ),
            patch(
                "src.core.services.session_service.provision_user_from_claims",
                return_value=test_user,
            ),
            patch(
                "src.core.services.session_service.create_user_session",
                return_value="user-session-456",
            ),
            patch("src.core.services.session_service.delete_auth_session"),
        ):
            # Set auth session cookie
            auth_test_client.cookies.set("auth_session_id", test_auth_session.id)

            response = auth_test_client.get(
                f"/auth/web/callback?code=test-code&state={test_auth_session.state}",
                follow_redirects=False,
            )

            assert response.status_code == status.HTTP_302_FOUND
            assert response.headers["Location"] == test_auth_session.redirect_uri

    def test_callback_invalid_state(self, auth_test_client, test_auth_session):
        """Test callback with invalid state parameter."""
        with patch(
            "src.core.services.session_service.get_auth_session",
            return_value=test_auth_session,
        ):
            auth_test_client.cookies.set("auth_session_id", test_auth_session.id)

            response = auth_test_client.get(
                "/auth/web/callback?code=test-code&state=wrong-state",
                follow_redirects=False,
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_callback_missing_session(self, auth_test_client):
        """Test callback without auth session."""
        response = auth_test_client.get(
            "/auth/web/callback?code=test-code&state=test-state", follow_redirects=False
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_me_endpoint_with_session(
        self, auth_test_client, test_user_session, test_user
    ):
        """Test /me endpoint with valid session."""
        with (
            patch("src.api.http.deps.get_user_session", return_value=test_user_session),
            patch("src.entities.user.UserRepository.get", return_value=test_user),
        ):
            auth_test_client.cookies.set("user_session_id", test_user_session.id)

            response = auth_test_client.get("/auth/web/me")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["user"]["id"] == test_user.id
            assert data["user"]["email"] == test_user.email
            assert data["authenticated"] is True

    def test_me_endpoint_without_session(self, auth_test_client):
        """Test /me endpoint without session."""
        response = auth_test_client.get("/auth/web/me")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["authenticated"] is False
        assert data["user"] is None

    def test_logout_success(self, auth_test_client, test_user_session):
        """Test successful logout."""
        with (
            patch(
                "src.core.services.session_service.get_user_session",
                return_value=test_user_session,
            ),
            patch(
                "src.core.services.session_service.delete_user_session"
            ) as mock_delete,
        ):
            auth_test_client.cookies.set("user_session_id", test_user_session.id)

            response = auth_test_client.post("/auth/web/logout")

            assert response.status_code == status.HTTP_200_OK
            mock_delete.assert_called_once_with(test_user_session.id)


class TestAuthenticationIntegration:
    """Test integrated authentication flows."""

    @pytest.mark.asyncio
    async def test_complete_auth_flow_simulation(
        self, auth_test_client, base_oidc_provider
    ):
        """Test complete authentication flow from login to authenticated access."""
        # This simulates the complete flow but with mocks
        # Step 1: Initiate login
        with (
            patch(
                "src.core.services.oidc_client_service.generate_pkce_pair"
            ) as mock_pkce,
            patch("src.core.services.oidc_client_service.generate_state") as mock_state,
            patch(
                "src.core.services.session_service.create_auth_session"
            ) as mock_create_auth,
        ):
            mock_pkce.return_value = ("verifier", "challenge")
            mock_state.return_value = "state123"
            mock_create_auth.return_value = "auth-session-id"

            login_response = auth_test_client.get(
                "/auth/web/login", follow_redirects=False
            )
            assert login_response.status_code == 302

            # Step 2: Simulate callback
            test_auth_session = AuthSession(
                id="auth-session-id",
                pkce_verifier="verifier",
                state="state123",
                provider="default",
                redirect_uri="/dashboard",
                created_at=int(time.time()),
                expires_at=int(time.time()) + 600,
            )

            test_user = User(
                id="user-123",
                email="test@example.com",
                first_name="Test",
                last_name="User",
            )

            with (
                patch(
                    "src.core.services.session_service.get_auth_session",
                    return_value=test_auth_session,
                ),
                patch(
                    "src.core.services.oidc_client_service.exchange_code_for_tokens"
                ) as mock_exchange,
                patch(
                    "src.core.services.oidc_client_service.get_user_claims"
                ) as mock_claims,
                patch(
                    "src.core.services.session_service.provision_user_from_claims",
                    return_value=test_user,
                ),
                patch(
                    "src.core.services.session_service.create_user_session",
                    return_value="user-session-id",
                ),
                patch("src.core.services.session_service.delete_auth_session"),
            ):
                mock_exchange.return_value = TokenResponse(
                    access_token="access-token",
                    token_type="Bearer",
                    expires_in=3600,
                )
                mock_claims.return_value = {
                    "sub": "user-123",
                    "email": "test@example.com",
                    "given_name": "Test",
                    "family_name": "User",
                }

                auth_test_client.cookies.set("auth_session_id", "auth-session-id")
                callback_response = auth_test_client.get(
                    "/auth/web/callback?code=auth-code&state=state123",
                    follow_redirects=False,
                )
                assert callback_response.status_code == 302

                # Step 3: Access authenticated endpoint
                test_user_session = UserSession(
                    id="user-session-id",
                    user_id="user-123",
                    provider="default",
                    refresh_token=None,
                    access_token="access-token",
                    access_token_expires_at=int(time.time()) + 3600,
                    created_at=int(time.time()),
                    last_accessed_at=int(time.time()),
                    expires_at=int(time.time()) + 86400,
                )

                with (
                    patch(
                        "src.api.http.deps.get_user_session",
                        return_value=test_user_session,
                    ),
                    patch(
                        "src.entities.user.UserRepository.get", return_value=test_user
                    ),
                ):
                    auth_test_client.cookies.set("user_session_id", "user-session-id")
                    me_response = auth_test_client.get("/auth/web/me")

                    assert me_response.status_code == 200
                    data = me_response.json()
                    assert data["authenticated"] is True
                    assert data["user"]["email"] == "test@example.com"
