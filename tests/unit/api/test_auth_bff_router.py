"""Unit tests for BFF authentication router."""

from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from src.core.services.oidc_client_service import TokenResponse
from src.entities.user import User
from src.runtime.config import ApplicationConfig, with_context


class TestBFFRouter:
    """Test BFF authentication router endpoints."""

    @pytest.fixture
    def test_config(self, mock_oidc_provider):
        """Test configuration with mock OIDC provider."""
        config = ApplicationConfig()
        config.oidc.providers = {"default": mock_oidc_provider}
        config.environment = "test"
        return config

    @pytest.fixture
    def test_client_with_mocks(self, client, test_config):
        """Test client with mocked services and configuration."""
        with patch('src.api.http.routers.auth_bff.main_config', test_config):
            yield client

    def test_initiate_login_success(self, test_client_with_mocks, mock_oidc_provider):
        """Test successful login initiation."""
        with patch('src.core.services.oidc_client_service.generate_pkce_pair') as mock_pkce:
            with patch('src.core.services.oidc_client_service.generate_state') as mock_state:
                with patch('src.core.services.session_service.create_auth_session') as mock_create_session:
                    
                    # Setup mocks
                    mock_pkce.return_value = ("test-verifier", "test-challenge")
                    mock_state.return_value = "test-state"
                    mock_create_session.return_value = "auth-session-123"
                    
                    # Make request
                    response = test_client_with_mocks.get("/auth/web/login")
                    
                    # Should redirect
                    assert response.status_code == status.HTTP_302_FOUND
                    
                    # Check redirect URL
                    redirect_url = response.headers["location"]
                    parsed_url = urlparse(redirect_url)
                    query_params = parse_qs(parsed_url.query)
                    
                    assert parsed_url.netloc == "mock-provider.test"
                    assert parsed_url.path == "/authorize"
                    assert query_params["client_id"] == [mock_oidc_provider.client_id]
                    assert query_params["response_type"] == ["code"]
                    assert query_params["state"] == ["test-state"]
                    assert query_params["code_challenge"] == ["test-challenge"]
                    assert query_params["code_challenge_method"] == ["S256"]
                    
                    # Check session cookie was set
                    assert "auth_session_id=auth-session-123" in response.headers.get("set-cookie", "")

    def test_initiate_login_with_provider_and_redirect(self, test_client_with_mocks):
        """Test login initiation with specific provider and redirect URI."""
        with patch('src.core.services.oidc_client_service.generate_pkce_pair') as mock_pkce:
            with patch('src.core.services.oidc_client_service.generate_state') as mock_state:
                with patch('src.core.services.session_service.create_auth_session') as mock_create_session:
                    
                    mock_pkce.return_value = ("test-verifier", "test-challenge")
                    mock_state.return_value = "test-state"
                    mock_create_session.return_value = "auth-session-123"
                    
                    response = test_client_with_mocks.get(
                        "/auth/web/login?provider=default&redirect_uri=/dashboard"
                    )
                    
                    assert response.status_code == status.HTTP_302_FOUND
                    
                    # Verify session was created with correct redirect URI
                    mock_create_session.assert_called_once_with(
                        pkce_verifier="test-verifier",
                        state="test-state",
                        provider="default",
                        redirect_uri="/dashboard"
                    )

    def test_initiate_login_unknown_provider(self, test_client_with_mocks):
        """Test login with unknown provider returns 400."""
        response = test_client_with_mocks.get("/auth/web/login?provider=unknown")
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Unknown provider" in response.json()["detail"]

    def test_callback_success(self, test_client_with_mocks):
        """Test successful callback handling."""
        with patch('src.core.services.session_service.get_auth_session') as mock_get_auth:
            with patch('src.core.services.session_service.delete_auth_session') as mock_delete_auth:
                with patch('src.core.services.oidc_client_service.exchange_code_for_tokens') as mock_exchange:
                    with patch('src.core.services.oidc_client_service.get_user_claims') as mock_get_claims:
                        with patch('src.core.services.session_service.provision_user_from_claims') as mock_provision:
                            with patch('src.core.services.session_service.create_user_session') as mock_create_user_session:
                                
                                # Setup mocks
                                from uuid import UUID
                                
                                from src.core.services.session_service import AuthSession
                                
                                mock_auth_session = AuthSession(
                                    id="auth-session-123",
                                    pkce_verifier="test-verifier",
                                    state="callback-state",
                                    provider="default",
                                    redirect_uri="/dashboard",
                                    created_at=1234567890,
                                    expires_at=1234567890 + 600
                                )
                                
                                mock_get_auth.return_value = mock_auth_session
                                mock_exchange.return_value = TokenResponse(
                                    access_token="access-token",
                                    token_type="Bearer",
                                    expires_in=3600,
                                    refresh_token="refresh-token",
                                    id_token="id-token"
                                )
                                mock_get_claims.return_value = {
                                    "sub": "user-123",
                                    "email": "test@example.com"
                                }
                                mock_user = User(
                                    id="user-456",
                                    first_name="Test",
                                    last_name="User",
                                    email="test@example.com"
                                )
                                mock_provision.return_value = mock_user
                                mock_create_user_session.return_value = "user-session-789"
                                
                                # Create test client with auth session cookie
                                test_client_with_mocks.cookies = {"auth_session_id": "auth-session-123"}
                                
                                # Make callback request
                                response = test_client_with_mocks.get(
                                    "/auth/web/callback?code=auth-code&state=callback-state"
                                )
                                
                                # Should redirect to dashboard
                                assert response.status_code == status.HTTP_302_FOUND
                                assert response.headers["location"] == "/dashboard"
                                
                                # Check that user session cookie was set
                                set_cookie = response.headers.get("set-cookie", "")
                                assert "user_session_id=user-session-789" in set_cookie
                                
                                # Verify service calls
                                mock_exchange.assert_called_once_with(
                                    code="auth-code",
                                    pkce_verifier="test-verifier",
                                    provider="default"
                                )
                                mock_provision.assert_called_once_with(
                                    {"sub": "user-123", "email": "test@example.com"},
                                    "default"
                                )
                                mock_delete_auth.assert_called_once_with("auth-session-123")

    def test_callback_missing_auth_session_cookie(self, test_client_with_mocks):
        """Test callback without auth session cookie."""
        response = test_client_with_mocks.get(
            "/auth/web/callback?code=auth-code&state=test-state"
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Missing auth session" in response.json()["detail"]

    def test_callback_invalid_state(self, test_client_with_mocks):
        """Test callback with mismatched state parameter."""
        with patch('src.core.services.session_service.get_auth_session') as mock_get_auth:
            from src.core.services.session_service import AuthSession
            
            mock_auth_session = AuthSession(
                id="auth-session-123",
                pkce_verifier="test-verifier",
                state="expected-state",
                provider="default",
                redirect_uri="/dashboard",
                created_at=1234567890,
                expires_at=1234567890 + 600
            )
            mock_get_auth.return_value = mock_auth_session
            
            test_client_with_mocks.cookies = {"auth_session_id": "auth-session-123"}
            
            response = test_client_with_mocks.get(
                "/auth/web/callback?code=auth-code&state=wrong-state"
            )
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid state parameter" in response.json()["detail"]

    def test_callback_with_error_parameter(self, test_client_with_mocks):
        """Test callback with error parameter."""
        response = test_client_with_mocks.get(
            "/auth/web/callback?error=access_denied&state=test-state"
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Authorization failed: access_denied" in response.json()["detail"]

    def test_logout_with_session(self, test_client_with_mocks):
        """Test logout with active session."""
        with patch('src.core.services.session_service.get_user_session') as mock_get_session:
            with patch('src.core.services.session_service.delete_user_session') as mock_delete_session:
                from uuid import UUID
                
                from src.core.services.session_service import UserSession
                
                mock_user_session = UserSession(
                    id="user-session-123",
                    user_id=UUID("12345678-1234-5678-9abc-123456789012"),
                    provider="default",
                    refresh_token="refresh-token",
                    access_token="access-token",
                    access_token_expires_at=1234567890,
                    created_at=1234567890,
                    last_accessed_at=1234567890,
                    expires_at=1234567890 + 86400
                )
                mock_get_session.return_value = mock_user_session
                
                test_client_with_mocks.cookies = {"user_session_id": "user-session-123"}
                
                response = test_client_with_mocks.post("/auth/web/logout")
                
                assert response.status_code == status.HTTP_200_OK
                result = response.json()
                assert result["message"] == "Logged out"
                
                # Should delete session
                mock_delete_session.assert_called_once_with("user-session-123")

    def test_logout_without_session(self, test_client_with_mocks):
        """Test logout without active session."""
        response = test_client_with_mocks.post("/auth/web/logout")
        
        assert response.status_code == status.HTTP_200_OK
        result = response.json()
        assert result["message"] == "Logged out"

    def test_get_auth_state_authenticated(self, test_client_with_mocks):
        """Test getting auth state for authenticated user."""
        with patch('src.api.http.deps.get_session_only_user') as mock_get_user:
            with patch('src.core.services.session_service.generate_csrf_token') as mock_csrf:
                
                mock_user = User(
                    id="user-123",
                    first_name="Test",
                    last_name="User",
                    email="test@example.com"
                )
                mock_get_user.return_value = mock_user
                mock_csrf.return_value = "csrf-token-456"
                
                test_client_with_mocks.cookies = {"user_session_id": "session-123"}
                
                response = test_client_with_mocks.get("/auth/web/me")
                
                assert response.status_code == status.HTTP_200_OK
                result = response.json()
                
                assert result["authenticated"] is True
                assert result["user"]["id"] == "user-123"
                assert result["user"]["email"] == "test@example.com"
                assert result["csrf_token"] == "csrf-token-456"

    def test_get_auth_state_unauthenticated(self, test_client_with_mocks):
        """Test getting auth state for unauthenticated user."""
        with patch('src.api.http.deps.get_session_only_user') as mock_get_user:
            mock_get_user.return_value = None
            
            response = test_client_with_mocks.get("/auth/web/me")
            
            assert response.status_code == status.HTTP_200_OK
            result = response.json()
            
            assert result["authenticated"] is False
            assert result["user"] is None
            assert result["csrf_token"] is None

    def test_refresh_session_success(self, test_client_with_mocks):
        """Test successful session refresh."""
        with patch('src.core.services.session_service.refresh_user_session') as mock_refresh:
            
            mock_refresh.return_value = "new-session-456"
            test_client_with_mocks.cookies = {"user_session_id": "old-session-123"}
            
            response = test_client_with_mocks.get("/auth/web/refresh")
            
            assert response.status_code == status.HTTP_200_OK
            result = response.json()
            assert result["message"] == "Session refreshed"
            
            # Check that new session cookie was set
            set_cookie = response.headers.get("set-cookie", "")
            assert "user_session_id=new-session-456" in set_cookie
            
            mock_refresh.assert_called_once_with("old-session-123")

    def test_refresh_session_missing_session(self, test_client_with_mocks):
        """Test refresh without session cookie."""
        response = test_client_with_mocks.get("/auth/web/refresh")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "No session found" in response.json()["detail"]

    def test_refresh_session_refresh_fails(self, test_client_with_mocks):
        """Test refresh when session refresh fails."""
        with patch('src.core.services.session_service.refresh_user_session') as mock_refresh:
            
            mock_refresh.side_effect = Exception("Refresh token expired")
            test_client_with_mocks.cookies = {"user_session_id": "session-123"}
            
            response = test_client_with_mocks.get("/auth/web/refresh")
            
            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Session refresh failed" in response.json()["detail"]