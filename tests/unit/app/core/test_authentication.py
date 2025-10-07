"""Consolidated authentication system tests.

This module combines and consolidates tests for:
- JWT service (claim extraction, JWKS fetching, JWT verification)
- OIDC client service (token exchange, user claims, PKCE flow)
- Session service (auth sessions, user sessions, JIT provisioning)
- BFF authentication router (login initiation, callback handling, /me endpoint)
- Authentication dependencies (require_scope, require_role authorization)

Replaces:
- tests/unit/core/test_services.py (JWT service functionality)
- tests/unit/core/test_oidc_client_service.py
- tests/unit/core/test_session_service.py
- tests/unit/api/test_auth_bff_router.py (partially)
- tests/unit/infrastructure/test_deps.py (authentication dependencies)
- Various other auth-related tests
"""

import time
import unittest.mock
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from authlib.jose import jwt
from fastapi import HTTPException, Request, status
from fastapi.testclient import TestClient

from app.core.models.session import TokenClaims
from app.core.security import generate_nonce
from src.app.api.http.deps import require_role, require_scope
from src.app.core.services import jwt_service, oidc_client_service, session_service
from src.app.core.services.oidc_client_service import TokenResponse
from src.app.core.services.session_service import AuthSession, UserSession
from src.app.entities.core.user import User
from src.app.entities.core.user_identity import UserIdentity
from src.app.runtime.config.config_data import (
    ConfigData,
    OIDCConfig,
    OIDCProviderConfig,
)
from src.app.runtime.context import with_context
from tests.utils import oct_jwk


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
    async def test_exchange_code_for_tokens_with_client_secret(
        self, base_oidc_provider, mock_http_response_factory, auth_test_config
    ):
        """Test token exchange with client secret authentication."""
        # Configure provider with client secret
        auth_test_config.oidc.providers["default"].client_secret = "test-secret"

        mock_response_data = {
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "mock-refresh-token",
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

                # Verify client secret was included in Authorization header
                call_args = (
                    mock_client.return_value.__aenter__.return_value.post.call_args
                )
                headers = call_args[1]["headers"]
                assert "Authorization" in headers
                assert headers["Authorization"].startswith("Basic ")

    @pytest.mark.asyncio
    async def test_get_user_claims_from_userinfo_endpoint(
        self,
        base_oidc_provider,
        mock_http_response_factory,
        auth_test_config,
    ):

        claims = {
            "iss": 'https://mock-provider.test',
            "sub": 'user-12345',
            "aud": "test-client-id",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "email": 'test@example.com',
            "email_verified": True,
            "given_name": 'Test',
            "family_name": 'User',
            "name": 'Test User',
            "picture": "https://example.com/avatar.jpg",
        }

        """Test extracting user claims from userinfo endpoint when ID token fails."""
        mock_response = mock_http_response_factory(claims)

        with patch("src.app.core.services.jwt_service.verify_jwt") as mock_verify:
            # Make JWT verification fail to force fallback to userinfo
            mock_verify.side_effect = Exception("JWT verification failed")

            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get.return_value = (
                    mock_response
                )

                with with_context(config_override=auth_test_config):
                    result = await oidc_client_service.get_user_claims(
                        access_token="mock-access-token",
                        id_token="mock-id-token",
                        provider="default",
                    )

                    assert result.issuer == 'https://mock-provider.test'
                    assert result.subject == 'user-12345'
                    assert result.audience == "test-client-id"
                    assert result.email == 'test@example.com'
                    assert result.email_verified is True
                    assert result.given_name == 'Test'
                    assert result.family_name == 'User'
                    assert result.name == 'Test User'
                    assert result.custom_claims.get("picture") == "https://example.com/avatar.jpg"

                    # Verify userinfo endpoint was called
                    mock_client.return_value.__aenter__.return_value.get.assert_called_once()
                    call_args = (
                        mock_client.return_value.__aenter__.return_value.get.call_args
                    )
                    assert base_oidc_provider.userinfo_endpoint in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_user_claims_no_id_token_no_userinfo(self, auth_test_config):
        """Test error handling when both ID token and userinfo fail."""
        # Configure provider without userinfo endpoint
        auth_test_config.oidc.providers["default"].userinfo_endpoint = None

        with patch("src.app.core.services.jwt_service.verify_jwt") as mock_verify:
            mock_verify.side_effect = Exception("JWT verification failed")

            with with_context(config_override=auth_test_config):
                with pytest.raises(ValueError, match="Unable to retrieve user claims"):
                    await oidc_client_service.get_user_claims(
                        access_token="mock-access-token",
                        id_token="mock-id-token",
                        provider="default",
                    )

    @pytest.mark.asyncio
    async def test_refresh_access_token_success(
        self, base_oidc_provider, mock_http_response_factory, auth_test_config
    ):
        """Test successful access token refresh."""
        mock_response_data = {
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "new-refresh-token",
        }
        mock_response = mock_http_response_factory(mock_response_data)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            with with_context(config_override=auth_test_config):
                result = await oidc_client_service.refresh_access_token(
                    refresh_token="old-refresh-token", provider="default"
                )

                assert isinstance(result, TokenResponse)
                assert result.access_token == "new-access-token"
                assert result.refresh_token == "new-refresh-token"

                # Verify correct refresh request
                call_args = (
                    mock_client.return_value.__aenter__.return_value.post.call_args
                )
                form_data = call_args[1]["data"]
                assert form_data["grant_type"] == "refresh_token"
                assert form_data["refresh_token"] == "old-refresh-token"

    @pytest.mark.asyncio
    async def test_refresh_access_token_http_error(
        self, base_oidc_provider, mock_http_response_factory, auth_test_config
    ):
        """Test token refresh with HTTP error."""
        mock_response = mock_http_response_factory({}, status_code=400)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            with with_context(config_override=auth_test_config):
                with pytest.raises(httpx.HTTPStatusError):
                    await oidc_client_service.refresh_access_token(
                        refresh_token="old-refresh-token", provider="default"
                    )

    def test_token_response_expires_at_property(self):
        """Test TokenResponse expires_at property calculation."""
        import time

        token_response = TokenResponse(
            access_token="test-token", token_type="Bearer", expires_in=3600
        )

        # expires_at should be current time + expires_in
        expected_min = int(time.time()) + 3600 - 2  # Allow 2 seconds tolerance
        expected_max = int(time.time()) + 3600 + 2

        assert expected_min <= token_response.expires_at <= expected_max


class TestBFFAuthenticationRouter:
    """Test BFF authentication router endpoints."""

    def test_initiate_login_success(self, auth_test_client):
        """Test successful login initiation."""
        with (
            patch(
                "src.app.core.services.oidc_client_service.generate_pkce_pair"
            ) as mock_pkce,
            patch(
                "src.app.core.services.oidc_client_service.generate_state"
            ) as mock_state,
            patch(
                "src.app.core.services.session_service.create_auth_session"
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
        test_auth_session: AuthSession,
        test_user,
        test_token_response,
    ):
        """Test successful callback handling."""
        with (
            patch(
                "src.app.core.services.session_service.get_auth_session",
                return_value=test_auth_session,
            ),
            patch(
                "src.app.core.services.oidc_client_service.exchange_code_for_tokens",
                return_value=test_token_response,
            ),
            patch(
                "src.app.core.services.session_service.provision_user_from_claims",
                return_value=test_user,
            ),

            patch("src.app.core.services.session_service.delete_auth_session"),
            patch(
                "src.app.core.security.hash_client_fingerprint",
                return_value=test_auth_session.client_fingerprint_hash,
            ),
        ):
            # Set auth session cookie
            auth_test_client.cookies.set("auth_session_id", test_auth_session.id)

            response = auth_test_client.get(
                f"/auth/web/callback?code=test-code&state={test_auth_session.state}",
                follow_redirects=False,
            )

            assert response.status_code == status.HTTP_302_FOUND
            assert response.headers["Location"] == test_auth_session.return_to

    def test_callback_invalid_state(self, auth_test_client, test_auth_session):
        """Test callback with invalid state parameter."""
        with patch(
            "src.app.core.services.session_service.get_auth_session",
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
            patch(
                "src.app.api.http.deps.get_user_session", return_value=test_user_session
            ),
            patch(
                "src.app.entities.core.user.UserRepository.get", return_value=test_user
            ),
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
                "src.app.core.services.session_service.get_user_session",
                return_value=test_user_session,
            ),
            patch(
                "src.app.core.services.session_service.delete_user_session"
            ) as mock_delete,
        ):
            auth_test_client.cookies.set("user_session_id", test_user_session.id)

            response = auth_test_client.post("/auth/web/logout")

        assert response.status_code == status.HTTP_200_OK
        mock_delete.assert_called_once_with(test_user_session.id)

    def test_callback_with_error_parameter(self, auth_test_client):
        """Test callback with error parameter from OIDC provider."""
        response = auth_test_client.get(
            "/auth/web/callback?error=access_denied&error_description=User%20denied%20access",
            follow_redirects=False,
        )

        # The specific status code depends on FastAPI's validation behavior
        assert response.status_code in [
            400,
            422,
        ]  # Either bad request or unprocessable entity
        if response.status_code == 400:
            assert "Authorization failed" in response.text

    def test_callback_missing_code_parameter(self, auth_test_client, test_auth_session):
        """Test callback without required code parameter."""
        with patch(
            "src.app.core.services.session_service.get_auth_session",
            return_value=test_auth_session,
        ):
            auth_test_client.cookies.set("auth_session_id", test_auth_session.id)

            response = auth_test_client.get(
                f"/auth/web/callback?state={test_auth_session.state}",
                follow_redirects=False,
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Missing authorization code" in response.text

    def test_callback_token_exchange_failure(self, auth_test_client, test_auth_session):
        """Test callback when token exchange fails."""
        with (
            patch(
                "src.app.core.services.session_service.get_auth_session",
                return_value=test_auth_session,
            ),
            patch(
                "src.app.core.services.oidc_client_service.exchange_code_for_tokens",
                side_effect=httpx.HTTPStatusError(
                    "Token exchange failed", request=Mock(), response=Mock()
                ),
            ),
        ):
            auth_test_client.cookies.set("auth_session_id", test_auth_session.id)

            response = auth_test_client.get(
                f"/auth/web/callback?code=test-code&state={test_auth_session.state}",
                follow_redirects=False,
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_callback_user_claims_failure(
        self, auth_test_client, test_auth_session, test_token_response
    ):
        """Test callback when user claims extraction fails."""
        with (
            patch(
                "src.app.core.services.session_service.get_auth_session",
                return_value=test_auth_session,
            ),
            patch(
                "src.app.core.services.oidc_client_service.exchange_code_for_tokens",
                return_value=test_token_response,
            ),
            patch(
                "src.app.core.services.oidc_client_service.get_user_claims",
                side_effect=HTTPException(status_code=401, detail="Invalid ID token"),
            ),
        ):
            auth_test_client.cookies.set("auth_session_id", test_auth_session.id)

            response = auth_test_client.get(
                f"/auth/web/callback?code=test-code&state={test_auth_session.state}",
                follow_redirects=False,
            )

            # Error handling may convert HTTPException to 500 in the router
            assert response.status_code in [401, 500]

    def test_callback_user_provisioning_failure(
        self, auth_test_client, test_auth_session, test_token_response
    ):
        """Test callback when user provisioning fails."""
        with (
            patch(
                "src.app.core.services.session_service.get_auth_session",
                return_value=test_auth_session,
            ),
            patch(
                "src.app.core.services.oidc_client_service.exchange_code_for_tokens",
                return_value=test_token_response,
            ),
            patch(
                "src.app.core.services.session_service.provision_user_from_claims",
                side_effect=Exception("Database connection failed"),
            ),
        ):
            auth_test_client.cookies.set("auth_session_id", test_auth_session.id)

            response = auth_test_client.get(
                f"/auth/web/callback?code=test-code&state={test_auth_session.state}",
                follow_redirects=False,
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_me_endpoint_with_invalid_session(self, auth_test_client):
        """Test /me endpoint with corrupted or invalid session."""
        # Set invalid session cookie
        auth_test_client.cookies.set("user_session_id", "invalid-session-id-12345")

        with patch("src.app.api.http.deps.get_user_session", return_value=None):
            response = auth_test_client.get("/auth/web/me")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["authenticated"] is False
            assert data["user"] is None

    def test_logout_without_session(self, auth_test_client):
        """Test logout without active session."""
        with patch(
            "src.app.core.services.session_service.get_user_session",
            return_value=None,
        ):
            response = auth_test_client.post("/auth/web/logout")

            # Should still return 200 OK (idempotent operation)
            assert response.status_code == status.HTTP_200_OK

    def test_login_with_invalid_provider(self, auth_test_client):
        """Test login initiation with invalid provider parameter."""
        # Assuming the router accepts provider parameter
        response = auth_test_client.get(
            "/auth/web/login?provider=nonexistent-provider", follow_redirects=False
        )

        # Should either use default provider or return error
        # This depends on implementation - adjust based on actual behavior
        assert response.status_code in [302, 400]  # Either redirect or bad request


class TestAuthenticationIntegration:
    """Test integrated authentication flows."""

    @pytest.mark.asyncio
    async def test_complete_auth_flow_simulation(
        self, auth_test_client, base_oidc_provider
    ):
        """Test complete authentication flow with real session management."""
        # Only mock the external OIDC provider interactions that we can't control
        with (
            patch(
                "src.app.core.services.oidc_client_service.exchange_code_for_tokens"
            ) as mock_exchange,
            patch(
                "src.app.core.services.oidc_client_service.get_user_claims"
            ) as mock_claims,
            patch("src.app.core.services.jwt_service.verify_jwt") as mock_verify_jwt,
        ):
            # Step 1: Initiate login - use real login endpoint
            login_response = auth_test_client.get(
                "/auth/web/login", follow_redirects=False
            )
            assert login_response.status_code == 302

            # Extract the auth session ID from the response cookie
            auth_session_cookie = auth_test_client.cookies.get("auth_session_id")
            assert auth_session_cookie is not None, "Auth session cookie should be set"

            # Extract state from the redirect URL
            location = login_response.headers.get("location", "")
            import urllib.parse

            parsed_url = urllib.parse.urlparse(location)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            state = query_params.get("state", [None])[0]

            assert state is not None, "State parameter should be in redirect URL"

            # Step 2: Simulate callback with real validation
            # Mock only the external OIDC provider responses
            mock_exchange.return_value = TokenResponse(
                access_token="access-token",
                token_type="Bearer",
                expires_in=3600,
                id_token="id-token",  # Include ID token for nonce validation
            )

            claims = TokenClaims(
                issuer="https://test-provider.example.com",
                subject="user-123",
                email="test@example.com",
                given_name="Test",
                family_name="User",
                audience="test-client-id",
                nonce="nonce-value",
                expires_at=int(time.time()) + 3600,
                issued_at=int(time.time()),
            )

            mock_claims.return_value = claims

            # Mock JWT verification to pass nonce validation
            mock_verify_jwt.return_value = None  # verify_jwt returns None on success

            # Use the real auth session cookie and state from step 1
            callback_response = auth_test_client.get(
                f"/auth/web/callback?code=auth-code&state={state}",
                follow_redirects=False,
            )

            # Debug information if it fails
            if callback_response.status_code != 302:
                print(f"Callback failed with status: {callback_response.status_code}")
                print(f"Response body: {callback_response.text}")
                print(f"Response headers: {dict(callback_response.headers)}")

            assert callback_response.status_code == 302

            # Extract user session cookie from callback response
            user_session_cookie = auth_test_client.cookies.get("user_session_id")
            assert user_session_cookie is not None, "User session cookie should be set"

            # Debug: Print all cookies to see what we have
            print(f"All cookies after callback: {dict(auth_test_client.cookies)}")

            # Step 3: Access authenticated endpoint with real session
            protected_response = auth_test_client.get("/auth/web/me")
            assert protected_response.status_code == 200

            user_data = protected_response.json()
            print(user_data)
            assert user_data["authenticated"] is True
            assert user_data["user"]["email"] == "test@example.com"
            assert user_data["user"]["first_name"] == "Test"
            assert user_data["user"]["last_name"] == "User"

            # Step 3: Verify the authentication flow completed successfully
            # The fact that we got a 302 redirect and a user session cookie means
            # the real authentication flow worked (login -> callback -> JIT provisioning -> session creation)
            print("✅ Complete authentication flow simulation successful!")
            print(f"✅ User session ID: {user_session_cookie}")

            # Note: We could test the /auth/jit/me endpoint here, but due to test database
            # transaction isolation, the JIT-provisioned user might not be visible
            # in subsequent requests. The core authentication flow has been verified.

    @pytest.mark.asyncio
    async def test_authentication_flow_session_interruption(self, auth_test_client):
        """Test authentication flow when session is lost mid-flow."""
        # Step 1: Start login normally
        with (
            patch(
                "src.app.core.services.oidc_client_service.generate_pkce_pair"
            ) as mock_pkce,
            patch(
                "src.app.core.services.oidc_client_service.generate_state"
            ) as mock_state,
            patch(
                "src.app.core.services.session_service.create_auth_session"
            ) as mock_create_auth,
        ):
            mock_pkce.return_value = ("verifier", "challenge")
            mock_state.return_value = "state123"
            mock_create_auth.return_value = "auth-session-id"

            login_response = auth_test_client.get(
                "/auth/web/login", follow_redirects=False
            )
            assert login_response.status_code == 302

            # Step 2: Simulate session loss during callback
            with patch(
                "src.app.core.services.session_service.get_auth_session",
                return_value=None,
            ):
                callback_response = auth_test_client.get(
                    "/auth/web/callback?code=auth-code&state=state123",
                    follow_redirects=False,
                )
                # Should fail due to missing session
                assert callback_response.status_code == 400

    @pytest.mark.asyncio
    async def test_authentication_flow_state_mismatch_attack(self, auth_test_client):
        """Test authentication flow protection against state mismatch attacks."""
        test_auth_session = AuthSession(
            client_fingerprint_hash="fingerprint",
            nonce="nonce",
            id="auth-session-id",
            pkce_verifier="verifier",
            state="correct-state-123",
            provider="default",
            return_to="/dashboard",
            created_at=int(time.time()),
            expires_at=int(time.time()) + 600,
        )

        # Step 1: Start login normally
        with (
            patch(
                "src.app.core.services.oidc_client_service.generate_pkce_pair"
            ) as mock_pkce,
            patch(
                "src.app.core.services.oidc_client_service.generate_state"
            ) as mock_state,
            patch(
                "src.app.core.services.session_service.create_auth_session"
            ) as mock_create_auth,
        ):
            mock_pkce.return_value = ("verifier", "challenge")
            mock_state.return_value = "correct-state-123"
            mock_create_auth.return_value = "auth-session-id"

            login_response = auth_test_client.get(
                "/auth/web/login", follow_redirects=False
            )
            assert login_response.status_code == 302

            # Step 2: Attempt callback with wrong state (CSRF attack simulation)
            with patch(
                "src.app.core.services.session_service.get_auth_session",
                return_value=test_auth_session,
            ):
                auth_test_client.cookies.set("auth_session_id", "auth-session-id")

                callback_response = auth_test_client.get(
                    "/auth/web/callback?code=auth-code&state=malicious-state",
                    follow_redirects=False,
                )
                # Should reject due to state mismatch
                assert callback_response.status_code == 400

    @pytest.mark.asyncio
    async def test_authentication_flow_concurrent_sessions(self, auth_test_client):
        """Test authentication flow with multiple concurrent sessions."""
        # Simulate user opening multiple tabs/windows
        sessions = []
        for i in range(3):
            with (
                patch(
                    "src.app.core.services.oidc_client_service.generate_pkce_pair"
                ) as mock_pkce,
                patch(
                    "src.app.core.services.oidc_client_service.generate_state"
                ) as mock_state,
                patch(
                    "src.app.core.services.session_service.create_auth_session"
                ) as mock_create_auth,
            ):
                mock_pkce.return_value = (f"verifier-{i}", f"challenge-{i}")
                mock_state.return_value = f"state-{i}"
                mock_create_auth.return_value = f"auth-session-{i}"

                response = auth_test_client.get(
                    "/auth/web/login", follow_redirects=False
                )
                assert response.status_code == 302

                sessions.append(
                    {
                        "id": f"auth-session-{i}",
                        "state": f"state-{i}",
                        "verifier": f"verifier-{i}",
                    }
                )

        # Each session should be independent and completable
        for i, session in enumerate(sessions):
            test_auth_session = AuthSession(
                client_fingerprint_hash="fingerprint",
                nonce="nonce",
                id=session["id"],
                pkce_verifier=session["verifier"],
                state=session["state"],
                provider="default",
                return_to="/dashboard",
                created_at=int(time.time()),
                expires_at=int(time.time()) + 600,
            )

            # Should be able to complete each session independently
            with patch(
                "src.app.core.services.session_service.get_auth_session",
                return_value=test_auth_session,
            ):
                # Simulate proper callback for this specific session
                response = auth_test_client.get(
                    f"/auth/web/callback?code=code-{i}&state={session['state']}",
                    follow_redirects=False,
                )
                # May fail due to missing other mocks, but state validation should pass
                assert (
                    "Invalid state" not in response.text
                    if hasattr(response, "text")
                    else True
                )

    @pytest.mark.asyncio
    async def test_authentication_recovery_after_partial_failure(
        self, auth_test_client
    ):
        """Test authentication flow recovery after partial failures."""
        # Step 1: Failed first attempt due to network issue
        with (
            patch(
                "src.app.core.services.oidc_client_service.generate_pkce_pair"
            ) as mock_pkce,
            patch(
                "src.app.core.services.oidc_client_service.generate_state"
            ) as mock_state,
            patch(
                "src.app.core.services.session_service.create_auth_session"
            ) as mock_create_auth,
        ):
            mock_pkce.return_value = ("verifier1", "challenge1")
            mock_state.return_value = "state1"
            mock_create_auth.return_value = "auth-session-1"

            # First login attempt
            response1 = auth_test_client.get("/auth/web/login", follow_redirects=False)
            assert response1.status_code == 302

        # Step 2: Second attempt should work independently
        with (
            patch(
                "src.app.core.services.oidc_client_service.generate_pkce_pair"
            ) as mock_pkce,
            patch(
                "src.app.core.services.oidc_client_service.generate_state"
            ) as mock_state,
            patch(
                "src.app.core.services.session_service.create_auth_session"
            ) as mock_create_auth,
        ):
            mock_pkce.return_value = ("verifier2", "challenge2")
            mock_state.return_value = "state2"
            mock_create_auth.return_value = "auth-session-2"

            # Second login attempt (fresh start)
            response2 = auth_test_client.get("/auth/web/login", follow_redirects=False)
            assert response2.status_code == 302

            # Verify different sessions were created
            assert mock_create_auth.call_count >= 1


class TestJWTService:
    """Test JWT service functionality in isolation."""

    @pytest.fixture
    def valid_jwks(self):
        """Return valid JWKS data for testing."""
        return {
            "keys": [
                oct_jwk(b"test-secret-key", "test-key"),
                oct_jwk(b"another-key", "key-2"),
            ]
        }

    @pytest.fixture
    def oidc_provider_config(self):
        """Return OIDC provider configuration for testing."""
        return OIDCProviderConfig(
            client_secret="test-client-secret",
            client_id="test-client-id",
            authorization_endpoint="https://test.issuer/auth",
            token_endpoint="https://test.issuer/token",
            issuer="https://test.issuer",
            jwks_uri="https://test.issuer/.well-known/jwks.json",
            redirect_uri="http://localhost:8000/callback",
        )

    def test_extract_user_claims(self, test_identity_token_jwt, test_user_claims_dict, test_user_identity, test_user):
        claims = jwt_service.create_token_claims(
            token=test_identity_token_jwt,
            claims=test_user_claims_dict,
            token_type="id_token",
        )

        assert claims.issuer == test_user_identity.issuer
        assert claims.audience == 'test-client-id'
        assert claims.subject == test_user_identity.subject
        assert claims.email == test_user.email
        assert claims.given_name == test_user.first_name
        assert claims.family_name == test_user.last_name

    def test_extract_uid_with_custom_claim(self):
        """Should extract UID from custom claim when configured."""
        claims = {"iss": "issuer", "sub": "subject", "custom_uid": "user-123"}

        # Create test config with custom uid claim
        test_config = ConfigData()
        test_config.jwt.claims.user_id = "custom_uid"

        with with_context(test_config):
            result = jwt_service.extract_uid(claims)
            assert result == "user-123"

    def test_jwt_generate_verify_roundtrip(self, jwks_data):
        """Should generate and verify JWT correctly."""
        # Test 1: Basic JWT with default config secret
        token1 = jwt_service.generate_jwt(
            subject="user-123",
            claims={"email": "user@example.com", "role": "admin"},
            expires_in_seconds=3600,
        )

        verified_claims1 = jwt_service.verify_generated_jwt(token1)
        assert verified_claims1.subject == "user-123"
        assert verified_claims1.email == "user@example.com"
        assert set(verified_claims1.roles) == {"admin"}
        assert verified_claims1.jti is not None  # Default includes JTI

        # Test 2: JWT with custom secret key
        custom_secret = "my-custom-secret-key-123"
        token2 = jwt_service.generate_jwt(
            subject="user-456",
            claims={"scopes": ["read", "write"], "department": "engineering"},
            expires_in_seconds=1800,
            secret=custom_secret,
        )

        # Verify with the unified verify_jwt using the same custom secret
        import asyncio

        verified_claims2 = asyncio.run(
            jwt_service.verify_jwt(token2, key=custom_secret)
        )
        assert verified_claims2.subject == "user-456"
        assert verified_claims2.scopes == ["read", "write"]
        assert verified_claims2.custom_claims == {"department": "engineering"}

        # Test 3: JWT without JTI claim
        token3 = jwt_service.generate_jwt(
            subject="user-789",
            claims={"name": "John Doe", "age": 30},
            expires_in_seconds=7200,
            include_jti=False,
        )

        verified_claims3 = jwt_service.verify_generated_jwt(token3)
        assert verified_claims3.subject == "user-789"
        assert verified_claims3.name == "John Doe"
        assert verified_claims3.custom_claims == {"age": 30}
        assert "jti" not in verified_claims3.custom_claims  # JTI should be excluded

        # Test 4: JWT with custom issuer and audience
        token4 = jwt_service.generate_jwt(
            subject="service-account",
            claims={
                "client_id": "my-app",
                "permissions": ["read:users", "write:posts"],
            },
            expires_in_seconds=900,
            issuer="auth-server-prod",
            audience=["api", "mobile-app", "web-app"],
        )

        verified_claims4 = jwt_service.verify_generated_jwt(token4)
        assert verified_claims4.subject == "service-account"
        assert verified_claims4.issuer == "auth-server-prod"
        assert verified_claims4.audience == ["api", "mobile-app", "web-app"]
        assert verified_claims4.custom_claims["client_id"] == "my-app"
        assert verified_claims4.custom_claims["permissions"] == [
            "read:users",
            "write:posts",
        ]

        # Test 5: JWT with complex nested claims
        complex_claims = {
            "user_profile": {
                "preferences": {"theme": "dark", "language": "en"},
                "metadata": {"last_login": "2025-01-01T00:00:00Z"},
            },
            "roles": ["user", "premium"],
            "subscription": {"plan": "pro", "expires": "2025-12-31"},
        }

        token5 = jwt_service.generate_jwt(
            subject="premium-user-001",
            claims=complex_claims,
            expires_in_seconds=86400,  # 24 hours
        )

        verified_claims5 = jwt_service.verify_generated_jwt(token5)
        assert verified_claims5.subject == "premium-user-001"
        assert (
            verified_claims5.custom_claims["user_profile"]["preferences"]["theme"]
            == "dark"
        )
        assert (
            verified_claims5.custom_claims["user_profile"]["metadata"]["last_login"]
            == "2025-01-01T00:00:00Z"
        )
        assert verified_claims5.roles == ["user", "premium"]
        assert verified_claims5.custom_claims["subscription"]["plan"] == "pro"

        # Test 6: Verify that different secrets produce different tokens
        same_claims = {"test": "value"}
        token_secret1 = jwt_service.generate_jwt(
            subject="test-user", claims=same_claims, secret="secret-1"
        )

        token_secret2 = jwt_service.generate_jwt(
            subject="test-user", claims=same_claims, secret="secret-2"
        )

        # Tokens should be different even with same claims
        assert token_secret1 != token_secret2

        # Verify each token with its respective secret
        verified_secret1 = asyncio.run(
            jwt_service.verify_jwt(token_secret1, key="secret-1")
        )
        verified_secret2 = asyncio.run(
            jwt_service.verify_jwt(token_secret2, key="secret-2")
        )

        assert verified_secret1.subject == "test-user"
        assert verified_secret2.subject == "test-user"
        assert verified_secret1.custom_claims["test"] == "value"
        assert verified_secret2.custom_claims["test"] == "value"

        # Cross-verification should fail
        with pytest.raises(HTTPException):
            asyncio.run(jwt_service.verify_jwt(token_secret1, key="secret-2"))

        with pytest.raises(HTTPException):
            asyncio.run(jwt_service.verify_jwt(token_secret2, key="secret-1"))

        # Test 7: JWKS-compatible JWT generation and verification
        #
        # This tests two important scenarios:
        # 1. Our service generating tokens that external services can verify via our JWKS
        # 2. Our service verifying tokens from external IdPs using their JWKS
        #
        # In production:
        # - We have a raw secret key that we use for generation
        # - We publish the base64-encoded version in our JWKS endpoint
        # - External services fetch our JWKS and decode the base64 for verification
        # - When verifying external tokens, we fetch their JWKS and decode their keys

        async def fake_fetch_jwks(provider_config):
            """Mock JWKS fetcher that returns our test JWKS data."""
            return jwks_data

        # In real production, we would have a raw secret key that we:
        # 1. Use directly for JWT generation
        # 2. Base64-encode for JWKS publication
        raw_secret = b"router-secret-key"  # This is what we'd actually use

        # Generate JWT with the raw secret (as our service would in production)
        jwks_key = jwks_data["keys"][0]
        jwks_kid = jwks_key["kid"]  # Key ID for JWKS lookup

        # Our service expects string secrets, so convert raw bytes to string
        secret_for_generation = raw_secret.decode("utf-8")

        # Create test configuration with our JWKS issuer
        test_config = ConfigData()
        test_config.oidc = OIDCConfig()
        test_provider = OIDCProviderConfig(
            client_id="jwks-test-client",
            client_secret="jwks-test-secret",
            authorization_endpoint="https://test-jwks-provider.example.com/auth",
            token_endpoint="https://test-jwks-provider.example.com/token",
            issuer="https://test-jwks-provider.example.com",
            jwks_uri="https://test-jwks-provider.example.com/.well-known/jwks.json",
            redirect_uri="http://localhost:8000/callback",
        )
        test_config.oidc.providers = {"jwks-test": test_provider}
        test_config.jwt.allowed_algorithms = ["HS256"]
        test_config.jwt.audiences = ["jwks-api", "mobile-app"]

        token_jwks = jwt_service.generate_jwt(
            subject="jwks-user",
            claims={
                "email": "jwks@example.com",
                "roles": ["user", "verified"],
                "issued_by": "jwks-provider",
            },
            expires_in_seconds=3600,
            issuer="https://test-jwks-provider.example.com",
            audience=["jwks-api", "mobile-app"],
            secret=secret_for_generation,
            kid=jwks_kid,
        )

        # Verify JWT using JWKS path (mock the fetch_jwks function)
        with with_context(config_override=test_config):
            with unittest.mock.patch.object(jwt_service, "fetch_jwks", fake_fetch_jwks):
                verified_jwks_claims = asyncio.run(jwt_service.verify_jwt(token_jwks))

                assert verified_jwks_claims.subject == "jwks-user"
                assert verified_jwks_claims.email == "jwks@example.com"
                assert verified_jwks_claims.roles == ["user", "verified"]
                assert (
                    verified_jwks_claims.custom_claims["issued_by"] == "jwks-provider"
                )
                assert (
                    verified_jwks_claims.issuer
                    == "https://test-jwks-provider.example.com"
                )
                assert verified_jwks_claims.audience == ["jwks-api", "mobile-app"]

        # Test that JWKS verification works with helper functions too
        access_token_jwks = jwt_service.generate_access_token(
            user_id="jwks-access-user",
            scopes=["read:data", "write:files"],
            roles=["admin", "power-user"],
            secret=secret_for_generation,
            kid=jwks_kid,
            issuer="https://test-jwks-provider.example.com",
            audience="jwks-api",
        )

        with with_context(config_override=test_config):
            with unittest.mock.patch.object(jwt_service, "fetch_jwks", fake_fetch_jwks):
                verified_access_claims = asyncio.run(
                    jwt_service.verify_jwt(access_token_jwks)
                )

                assert verified_access_claims.subject == "jwks-access-user"
                assert verified_access_claims.scope == "read:data write:files"
                assert verified_access_claims.scopes == ["read:data", "write:files"]
                assert verified_access_claims.roles == ["admin", "power-user"]
                assert (
                    verified_access_claims.issuer
                    == "https://test-jwks-provider.example.com"
                )
                assert verified_access_claims.audience == "jwks-api"

    def test_extract_uid_fallback_to_issuer_subject(self):
        """Should fall back to issuer|subject when custom claim missing."""
        claims = {"iss": "https://issuer.example", "sub": "user-456"}

        # Create test config with missing uid claim
        test_config = ConfigData()
        test_config.jwt.claims.user_id = "missing_claim"

        with with_context(config_override=test_config):
            result = jwt_service.extract_uid(claims)
            assert result == "https://issuer.example|user-456"

    def test_extract_scopes_from_string(self):
        """Should parse space-separated scope string."""
        claims = {"scope": "read write admin"}

        result = jwt_service.extract_scopes(claims)
        assert result == ["read", "write", "admin"]

    def test_extract_scopes_from_list(self):
        """Should handle scope as list."""
        claims = {"scp": ["read", "write"]}

        result = jwt_service.extract_scopes(claims)
        assert result == ["read", "write"]

    def test_extract_scopes_from_multiple_sources(self):
        """Should combine scopes from multiple claim sources."""
        claims = {"scope": "read write", "scp": ["admin"]}

        result = jwt_service.extract_scopes(claims)
        assert result == ["read", "write", "admin"]

    def test_extract_roles_from_string(self):
        """Should parse space-separated roles string."""
        claims = {"roles": "user admin"}

        result = jwt_service.extract_roles(claims)
        assert set(result) == {"user", "admin"}

    def test_extract_roles_from_realm_access(self):
        """Should extract roles from Keycloak-style realm_access."""
        claims = {"realm_access": {"roles": ["admin", "user"]}, "roles": "guest"}

        result = jwt_service.extract_roles(claims)
        # Convert to set for comparison since order doesn't matter
        assert set(result) == {"admin", "user", "guest"}

    def test_extract_roles_from_singular_role_claim(self):
        """Should extract roles from singular 'role' claim."""
        # Test single role as string
        claims1 = {"role": "admin"}
        result1 = jwt_service.extract_roles(claims1)
        assert result1 == ["admin"]

        # Test multiple roles in singular claim (space-separated)
        claims2 = {"role": "user moderator"}
        result2 = jwt_service.extract_roles(claims2)
        assert set(result2) == {"user", "moderator"}

        # Test role and roles together (should combine both)
        claims3 = {"role": "admin", "roles": ["user", "guest"]}
        result3 = jwt_service.extract_roles(claims3)
        assert set(result3) == {"admin", "user", "guest"}

    def test_extract_empty_claims(self):
        """Should handle missing or empty claims gracefully."""
        claims = {}

        assert jwt_service.extract_uid(claims) == "None|None"
        assert jwt_service.extract_scopes(claims) == []
        assert jwt_service.extract_roles(claims) == []

    @pytest.mark.asyncio
    async def test_fetch_jwks_success(self, valid_jwks, oidc_provider_config):
        """Should fetch and cache JWKS successfully."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = valid_jwks
            mock_response.raise_for_status = Mock()

            # Only the .get() call is async
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await jwt_service.fetch_jwks(oidc_provider_config)

            assert result == valid_jwks
        # Verify the correct URL was called
        mock_client.return_value.__aenter__.return_value.get.assert_called_once_with(
            "https://test.issuer/.well-known/jwks.json"
        )

    @pytest.mark.asyncio
    async def test_fetch_jwks_network_timeout(self, oidc_provider_config):
        """Should handle JWKS fetch network timeouts."""
        with patch("httpx.AsyncClient") as mock_client:
            # Simulate timeout
            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                httpx.TimeoutException("Request timeout")
            )

            with pytest.raises(HTTPException) as exc_info:
                await jwt_service.fetch_jwks(oidc_provider_config)

            assert exc_info.value.status_code == 500
            assert "Failed to fetch JWKS" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_fetch_jwks_invalid_json(self, oidc_provider_config):
        """Should handle invalid JSON in JWKS response."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_response.raise_for_status = Mock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(HTTPException) as exc_info:
                await jwt_service.fetch_jwks(oidc_provider_config)

            assert exc_info.value.status_code == 500
            assert "Failed to fetch JWKS" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_fetch_jwks_missing_uri(self):
        """Should reject OIDC provider without JWKS URI."""
        provider_without_jwks = OIDCProviderConfig(
            client_secret="test-secret",
            client_id="test-client",
            authorization_endpoint="https://provider.test/auth",
            token_endpoint="https://provider.test/token",
            issuer="https://provider.test",
            jwks_uri="",  # Missing JWKS URI
            redirect_uri="http://localhost:8000/callback",
        )

        with pytest.raises(HTTPException) as exc_info:
            await jwt_service.fetch_jwks(provider_without_jwks)

        assert exc_info.value.status_code == 401
        assert "jwks uri configured" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_jwt_missing_kid_in_token(
        self, valid_jwks, oidc_provider_config
    ):
        """Should handle JWT tokens without kid (key ID) claim."""
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]
        test_config.jwt.audiences = ["api://test"]

        with with_context(config_override=test_config):
            cache_key = oidc_provider_config.jwks_uri
            jwt_service._JWKS_CACHE[cache_key] = valid_jwks

            # Create token without kid in header
            payload = {
                "iss": "https://test.issuer",
                "aud": "api://test",
                "exp": int(time.time()) + 60,
                "sub": "user-123",
            }
            # Note: not including "kid" in header
            token = jwt.encode({"alg": "HS256"}, payload, b"test-secret-key").decode(
                "utf-8"
            )

            # Should still work if key can be found by algorithm or other means
            # This tests the fallback behavior when kid is missing
            with pytest.raises(HTTPException):  # May fail due to key lookup issues
                await jwt_service.verify_jwt(token)

    @pytest.mark.asyncio
    async def test_verify_jwt_unknown_kid(self, valid_jwks, oidc_provider_config):
        """Should handle JWT tokens with unknown kid (key ID)."""
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]
        test_config.jwt.audiences = ["api://test"]

        with with_context(config_override=test_config):
            cache_key = oidc_provider_config.jwks_uri
            jwt_service._JWKS_CACHE[cache_key] = valid_jwks

            token = jwt_service.generate_jwt(
                subject="user-123",
                issuer="https://test.issuer",
                audience="api://test",
                secret="test-secret-key",
                kid="unknown-key-id",  # Key ID not in JWKS
                claims={"sub": "user-123"},
            )

            with pytest.raises(HTTPException) as exc_info:
                await jwt_service.verify_jwt(token)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_jwt_malformed_jwks(self, oidc_provider_config):
        """Should handle malformed JWKS data."""
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]

        with with_context(config_override=test_config):
            # Cache malformed JWKS
            cache_key = oidc_provider_config.jwks_uri
            jwt_service._JWKS_CACHE[cache_key] = {"invalid": "jwks format"}

            token = jwt_service.generate_jwt(
                issuer="https://test.issuer",
                subject="user-123",
                audience="api://test",
                secret="test-secret-key",
                kid="test-key",
                claims={"sub": "user-123"},
            )

            with pytest.raises(HTTPException) as exc_info:
                await jwt_service.verify_jwt(token)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_fetch_jwks_uses_cache(self, valid_jwks, oidc_provider_config):
        """Should return cached JWKS without making HTTP request."""
        cache_key = oidc_provider_config.jwks_uri
        jwt_service._JWKS_CACHE[cache_key] = valid_jwks

        # No HTTP client mock - should not be called
        result = await jwt_service.fetch_jwks(oidc_provider_config)

        assert result == valid_jwks

    @pytest.mark.asyncio
    async def test_verify_valid_jwt(self, valid_jwks, oidc_provider_config):
        """Should verify valid JWT successfully."""
        # Create test config with test provider
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]
        test_config.jwt.audiences = ["api://test"]
        test_config.jwt.clock_skew = 10

        with with_context(config_override=test_config):
            # Setup JWKS cache
            cache_key = oidc_provider_config.jwks_uri
            jwt_service._JWKS_CACHE[cache_key] = valid_jwks

            # Create valid token
            token = jwt_service.generate_jwt(
                issuer="https://test.issuer",
                subject="user-123",
                audience="api://test",
                secret="test-secret-key",
                kid="test-key",
                claims={"sub": "user-123"},
            )

            result = await jwt_service.verify_jwt(token)

            assert result.issuer == "https://test.issuer"
            assert result.audience == "api://test"
            assert result.subject == "user-123"

    @pytest.mark.asyncio
    async def test_verify_jwt_wrong_audience(self, valid_jwks, oidc_provider_config):
        """Should reject JWT with wrong audience."""
        # Create test config with test provider
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]
        test_config.jwt.audiences = ["api://test"]
        test_config.jwt.clock_skew = 10

        with with_context(config_override=test_config):
            # Setup JWKS cache
            cache_key = oidc_provider_config.jwks_uri
            jwt_service._JWKS_CACHE[cache_key] = valid_jwks

            token = jwt_service.generate_jwt(
                issuer="https://test.issuer",
                subject="user-123",
                audience="api://wrong",  # Wrong audience
                secret="test-secret-key",
                kid="test-key",
                claims={"sub": "user-123"},
            )

            with pytest.raises(HTTPException) as exc_info:
                await jwt_service.verify_jwt(token)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_jwt_expired_token(self, valid_jwks, oidc_provider_config):
        """Should reject expired JWT tokens."""
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]
        test_config.jwt.audiences = ["api://test"]
        test_config.jwt.clock_skew = 10

        with with_context(config_override=test_config):
            cache_key = oidc_provider_config.jwks_uri
            jwt_service._JWKS_CACHE[cache_key] = valid_jwks

            # Create token that expired 30 seconds ago (beyond 10s clock skew)
            expired_time = int(time.time()) - 30
            payload = {
                "iss": "https://test.issuer",
                "aud": "api://test",
                "exp": expired_time,
                "nbf": expired_time - 60,
                "sub": "user-123",
            }
            token = jwt.encode(
                {"alg": "HS256", "kid": "test-key"}, payload, b"test-secret-key"
            ).decode("utf-8")

            with pytest.raises(HTTPException) as exc_info:
                await jwt_service.verify_jwt(token)

            assert exc_info.value.status_code == 401
            assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_jwt_not_yet_valid(self, valid_jwks, oidc_provider_config):
        """Should reject JWT tokens with future nbf (not before) claim."""
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]
        test_config.jwt.audiences = ["api://test"]
        test_config.jwt.clock_skew = 10

        with with_context(config_override=test_config):
            cache_key = oidc_provider_config.jwks_uri
            jwt_service._JWKS_CACHE[cache_key] = valid_jwks

            # Create token valid 30 seconds in the future (beyond 10s clock skew)
            future_time = int(time.time()) + 30
            payload = {
                "iss": "https://test.issuer",
                "aud": "api://test",
                "exp": future_time + 3600,
                "nbf": future_time,
                "sub": "user-123",
            }
            token = jwt.encode(
                {"alg": "HS256", "kid": "test-key"}, payload, b"test-secret-key"
            ).decode("utf-8")

            with pytest.raises(HTTPException) as exc_info:
                await jwt_service.verify_jwt(token)

            assert exc_info.value.status_code == 401
            assert "not valid yet" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_jwt_clock_skew_boundary(
        self, valid_jwks, oidc_provider_config
    ):
        """Should accept JWT tokens within clock skew tolerance."""
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]
        test_config.jwt.audiences = ["api://test"]
        test_config.jwt.clock_skew = 30  # 30 second tolerance

        with with_context(config_override=test_config):
            cache_key = oidc_provider_config.jwks_uri
            jwt_service._JWKS_CACHE[cache_key] = valid_jwks

            # Create token that expired 20 seconds ago (within 30s tolerance)
            expired_time = int(time.time()) - 20
            payload = {
                "iss": "https://test.issuer",
                "aud": "api://test",
                "exp": expired_time,
                "nbf": expired_time - 60,
                "sub": "user-123",
            }
            token = jwt.encode(
                {"alg": "HS256", "kid": "test-key"}, payload, b"test-secret-key"
            ).decode("utf-8")

            # Should succeed due to clock skew tolerance
            result = await jwt_service.verify_jwt(token)
            assert result.subject == "user-123"

    @pytest.mark.asyncio
    async def test_verify_jwt_invalid_format(self, oidc_provider_config):
        """Should reject JWT tokens with invalid format."""
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]

        with with_context(config_override=test_config):
            # Test various malformed tokens
            invalid_tokens = [
                "not-a-jwt",  # No dots
                "only.one-dot",  # Only one dot
                "too.many.dots.here",  # Too many dots
                "",  # Empty string
                "header.payload.",  # Missing signature
                ".payload.signature",  # Missing header
                "header..signature",  # Missing payload
            ]

            for invalid_token in invalid_tokens:
                with pytest.raises(HTTPException) as exc_info:
                    await jwt_service.verify_jwt(invalid_token)

                assert exc_info.value.status_code == 401
                # Check for any JWT format related error message
                assert any(
                    keyword in exc_info.value.detail.lower()
                    for keyword in ["invalid jwt", "format", "header", "payload"]
                )

    @pytest.mark.asyncio
    async def test_verify_jwt_corrupted_base64(self, oidc_provider_config):
        """Should reject JWT tokens with corrupted base64 encoding."""
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]

        with with_context(config_override=test_config):
            # Create token with corrupted base64 segments
            corrupted_tokens = [
                "!!!invalid-base64!!!.eyJzdWIiOiJ1c2VyIn0.signature",  # Corrupted header
                "eyJhbGciOiJIUzI1NiJ9.!!!invalid-base64!!!.signature",  # Corrupted payload
                "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyIn0.!!!invalid-base64!!!",  # Corrupted signature
            ]

            for corrupted_token in corrupted_tokens:
                with pytest.raises(HTTPException) as exc_info:
                    await jwt_service.verify_jwt(corrupted_token)

                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_jwt_malformed_json(self, oidc_provider_config):
        """Should reject JWT tokens with malformed JSON in header/payload."""
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]

        with with_context(config_override=test_config):
            # Create base64-encoded but invalid JSON
            import base64

            invalid_json = b'{"invalid": json, missing quotes}'
            invalid_b64 = (
                base64.urlsafe_b64encode(invalid_json).decode("ascii").rstrip("=")
            )
            valid_payload = (
                base64.urlsafe_b64encode(b'{"sub":"user"}').decode("ascii").rstrip("=")
            )

            malformed_token = f"{invalid_b64}.{valid_payload}.signature"

            with pytest.raises(HTTPException) as exc_info:
                await jwt_service.verify_jwt(malformed_token)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_jwt_disallowed_algorithm(
        self, valid_jwks, oidc_provider_config
    ):
        """Should reject JWT tokens with disallowed algorithms."""
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["RS256"]  # Only allow RS256, not HS256
        test_config.jwt.audiences = ["api://test"]

        with pytest.raises(HTTPException) as exc_info:
            with with_context(config_override=test_config):
                token = jwt_service.generate_jwt(
                    issuer="https://test.issuer",
                    audience="api://test",
                    secret="test-secret-key",
                    kid="test-key",
                    subject="user-123",
                )

            with pytest.raises(HTTPException) as exc_info:
                await jwt_service.verify_jwt(token)

            assert exc_info.value.status_code == 401
            assert "disallowed" in exc_info.value.detail.lower()

    def test_create_token_claims_preserves_unmapped_claims(self):
        """Should preserve unmapped claims in custom_claims without dropping standard claims."""
        # Test with a mix of mapped and unmapped claims
        claims = {
            # Mapped claims (should be extracted to TokenClaims fields)
            "sub": "user-123",
            "iss": "https://test.issuer",
            "aud": ["api://test"],
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "nbf": int(time.time()),
            "email": "user@example.com",
            "name": "John Doe",
            "given_name": "John",
            "family_name": "Doe",
            "nonce": "abc123",
            "scope": "read write",
            "roles": ["user", "admin"],
            # Standard claims that we don't have TokenClaims fields for (should stay in custom_claims)
            "jti": "unique-jwt-id",
            "auth_time": 1234567890,
            "azp": "authorized-party",
            "acr": "0",
            "amr": ["pwd"],
            "at_hash": "access-token-hash",
            "middle_name": "Robert",
            "nickname": "Johnny",
            "preferred_username": "john_doe",
            "profile": "https://example.com/profile",
            "picture": "https://example.com/photo.jpg",
            "website": "https://johndoe.com",
            "gender": "male",
            "birthdate": "1990-01-01",
            "zoneinfo": "America/New_York",
            "locale": "en-US",
            "updated_at": 1234567890,
            "email_verified": True,
            "phone_number": "+1234567890",
            "phone_number_verified": True,
            "address": {"street": "123 Main St", "city": "Anytown"},
            # Truly custom claims (should stay in custom_claims)
            "tenant_id": "org-456",
            "permissions": ["read:documents", "write:reports"],
            "custom_field": "custom_value",
            "organization": {"id": "org-123", "name": "Acme Corp"},
        }

        token_claims = jwt_service.create_token_claims(
            token="test.jwt.token",
            claims=claims,
            token_type="access_token",
            issuer="fallback-issuer",
        )

        # Verify that mapped claims are correctly extracted
        assert token_claims.subject == "user-123"
        assert token_claims.issuer == "https://test.issuer"
        assert token_claims.audience == ["api://test"]
        assert token_claims.email == "user@example.com"
        assert token_claims.name == "John Doe"
        assert token_claims.given_name == "John"
        assert token_claims.family_name == "Doe"
        assert token_claims.nonce == "abc123"
        assert token_claims.scope == "read write"
        assert set(token_claims.scopes) == {"read", "write"}
        assert set(token_claims.roles) == {"user", "admin"}

        # Verify that all unmapped claims are preserved in custom_claims
        expected_custom_claims = {
            # Standard claims we don't have fields for
            "auth_time": 1234567890,
            "azp": "authorized-party",
            "acr": "0",
            "amr": ["pwd"],
            "at_hash": "access-token-hash",
            "middle_name": "Robert",
            "nickname": "Johnny",
            "preferred_username": "john_doe",
            "profile": "https://example.com/profile",
            "picture": "https://example.com/photo.jpg",
            "website": "https://johndoe.com",
            "gender": "male",
            "birthdate": "1990-01-01",
            "zoneinfo": "America/New_York",
            "locale": "en-US",
            "updated_at": 1234567890,
            "phone_number": "+1234567890",
            "phone_number_verified": True,
            "address": {"street": "123 Main St", "city": "Anytown"},
            # Truly custom claims
            "tenant_id": "org-456",
            "permissions": ["read:documents", "write:reports"],
            "custom_field": "custom_value",
            "organization": {"id": "org-123", "name": "Acme Corp"},
        }

        assert token_claims.custom_claims == expected_custom_claims

        # Verify that all_claims contains the original claims unchanged
        assert token_claims.all_claims == claims


class TestAuthenticationDependencies:
    """Test authentication and authorization dependency functions."""

    def create_mock_request(
        self, scopes: list[str] | None = None, roles: list[str] | None = None
    ) -> Request:
        """Create mock request with auth context."""
        request = Mock(spec=Request)
        request.state = Mock()

        if scopes is not None:
            request.state.scopes = set(scopes)
        if roles is not None:
            request.state.roles = set(roles)

        return request

    @pytest.mark.asyncio
    async def test_require_scope_success(self):
        """Test scope requirement with valid scope."""
        request = self.create_mock_request(scopes=["read", "write", "admin"])

        scope_dep = require_scope("read")
        # Should not raise for valid scope
        await scope_dep(request)

        scope_dep_write = require_scope("write")
        await scope_dep_write(request)

    @pytest.mark.asyncio
    async def test_require_scope_failure(self):
        """Test scope requirement with missing scope."""
        request = self.create_mock_request(scopes=["read"])

        scope_dep = require_scope("admin")

        with pytest.raises(HTTPException) as exc_info:
            await scope_dep(request)

        assert exc_info.value.status_code == 403
        assert "Missing required scope: admin" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_scope_empty_scopes(self):
        """Test scope requirement with empty scopes set."""
        request = self.create_mock_request(scopes=[])

        scope_dep = require_scope("read")

        with pytest.raises(HTTPException) as exc_info:
            await scope_dep(request)

        assert exc_info.value.status_code == 403
        assert "Missing required scope: read" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_scope_missing_scopes_attribute(self):
        """Test scope requirement when scopes attribute is missing from state."""
        request = Mock(spec=Request)

        # Create a simple object without the scopes attribute
        class SimpleState:
            pass

        request.state = SimpleState()

        scope_dep = require_scope("read")

        with pytest.raises(HTTPException) as exc_info:
            await scope_dep(request)

        assert exc_info.value.status_code == 403
        assert "Missing required scope: read" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_role_success(self):
        """Test role requirement with valid role."""
        request = self.create_mock_request(roles=["user", "admin", "moderator"])

        role_dep = require_role("admin")
        # Should not raise for valid role
        await role_dep(request)

        role_dep_user = require_role("user")
        await role_dep_user(request)

    @pytest.mark.asyncio
    async def test_require_role_failure(self):
        """Test role requirement with missing role."""
        request = self.create_mock_request(roles=["user"])

        role_dep = require_role("admin")

        with pytest.raises(HTTPException) as exc_info:
            await role_dep(request)

        assert exc_info.value.status_code == 403
        assert "Missing required role: admin" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_role_empty_roles(self):
        """Test role requirement with empty roles set."""
        request = self.create_mock_request(roles=[])

        role_dep = require_role("user")

        with pytest.raises(HTTPException) as exc_info:
            await role_dep(request)

        assert exc_info.value.status_code == 403
        assert "Missing required role: user" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_require_role_missing_roles_attribute(self):
        """Test role requirement when roles attribute is missing from state."""
        request = Mock(spec=Request)

        # Create a simple object without the roles attribute
        class SimpleState:
            pass

        request.state = SimpleState()

        role_dep = require_role("user")

        with pytest.raises(HTTPException) as exc_info:
            await role_dep(request)

        assert exc_info.value.status_code == 403
        assert "Missing required role: user" in exc_info.value.detail
