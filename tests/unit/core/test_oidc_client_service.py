"""Unit tests for OIDC client service."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.core.services import oidc_client_service
from src.core.services.oidc_client_service import TokenResponse
from src.runtime.config import get_config, with_context


class TestOIDCClientService:
    """Test OIDC client service functions in isolation."""

    def test_generate_pkce_pair(self):
        """Test PKCE verifier and challenge generation."""
        verifier, challenge = oidc_client_service.generate_pkce_pair()
        
        # Both should be non-empty strings
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)
        assert len(verifier) > 0
        assert len(challenge) > 0
        
        # Verifier should be URL-safe base64 without padding
        assert verifier.replace('-', '+').replace('_', '/').isalnum() or '=' not in verifier
        
        # Challenge should be URL-safe base64 without padding
        assert challenge.replace('-', '+').replace('_', '/').isalnum() or '=' not in challenge
        
        # Generate another pair - should be different
        verifier2, challenge2 = oidc_client_service.generate_pkce_pair()
        assert verifier != verifier2
        assert challenge != challenge2

    def test_generate_state(self):
        """Test state parameter generation."""
        state = oidc_client_service.generate_state()
        
        # Should be a non-empty URL-safe string
        assert isinstance(state, str)
        assert len(state) > 0
        
        # Should be different each time
        state2 = oidc_client_service.generate_state()
        assert state != state2

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_success(self, mock_oidc_provider, mock_httpx_response):
        """Test successful token exchange with PKCE."""
        # Mock the HTTP response
        mock_response_data = {
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "mock-refresh-token",
            "id_token": "mock-id-token"
        }
        mock_response = mock_httpx_response(mock_response_data)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            # Use test config with mock provider
            with with_context({"oidc": {"providers": {"test": mock_oidc_provider}}}):
                result = await oidc_client_service.exchange_code_for_tokens(
                    code="test-auth-code",
                    pkce_verifier="test-verifier",
                    provider="test"
                )
                
                # Verify response
                assert isinstance(result, TokenResponse)
                assert result.access_token == "mock-access-token"
                assert result.token_type == "Bearer"
                assert result.expires_in == 3600
                assert result.refresh_token == "mock-refresh-token"
                assert result.id_token == "mock-id-token"
                
                # Verify the HTTP call was made correctly
                mock_client.return_value.__aenter__.return_value.post.assert_called_once()
                call_args = mock_client.return_value.__aenter__.return_value.post.call_args
                
                # Check endpoint
                assert call_args[0][0] == mock_oidc_provider.token_endpoint
                
                # Check form data
                form_data = call_args[1]['data']
                assert form_data['grant_type'] == 'authorization_code'
                assert form_data['code'] == 'test-auth-code'
                assert form_data['code_verifier'] == 'test-verifier'
                assert form_data['client_id'] == mock_oidc_provider.client_id

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_with_client_secret(self, mock_oidc_provider, mock_httpx_response):
        """Test token exchange with client secret authentication."""
        mock_oidc_provider.client_secret = "test-secret"
        
        mock_response_data = {
            "access_token": "mock-access-token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        mock_response = mock_httpx_response(mock_response_data)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            with with_context({"oidc": {"providers": {"test": mock_oidc_provider}}}):
                await oidc_client_service.exchange_code_for_tokens(
                    code="test-auth-code",
                    pkce_verifier="test-verifier",
                    provider="test"
                )
                
                # Check that Basic Auth header was added
                call_args = mock_client.return_value.__aenter__.return_value.post.call_args
                headers = call_args[1]['headers']
                assert 'Authorization' in headers
                assert headers['Authorization'].startswith('Basic ')

    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_http_error(self, mock_oidc_provider, mock_httpx_response):
        """Test token exchange with HTTP error."""
        mock_response = mock_httpx_response({}, status_code=400)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            with with_context({"oidc": {"providers": {"test": mock_oidc_provider}}}):
                with pytest.raises(httpx.HTTPStatusError):
                    await oidc_client_service.exchange_code_for_tokens(
                        code="test-auth-code",
                        pkce_verifier="test-verifier",
                        provider="test"
                    )

    @pytest.mark.asyncio
    async def test_get_user_claims_from_id_token(self, mock_oidc_provider, mock_user_claims):
        """Test extracting user claims from ID token."""
        with patch('src.core.services.jwt_service.verify_jwt') as mock_verify:
            mock_verify.return_value = mock_user_claims
            
            with with_context({"oidc": {"providers": {"test": mock_oidc_provider}}}):
                result = await oidc_client_service.get_user_claims(
                    access_token="mock-access-token",
                    id_token="mock-id-token",
                    provider="test"
                )
                
                # Should return the decoded claims
                assert result == mock_user_claims
                mock_verify.assert_called_once_with("mock-id-token")

    @pytest.mark.asyncio
    async def test_get_user_claims_from_userinfo_endpoint(self, mock_oidc_provider, mock_user_claims, mock_httpx_response):
        """Test extracting user claims from userinfo endpoint."""
        mock_response = mock_httpx_response(mock_user_claims)
        
        with patch('src.core.services.jwt_service.verify_jwt') as mock_verify:
            # Make JWT verification fail to force fallback to userinfo
            mock_verify.side_effect = Exception("JWT verification failed")
            
            with patch('httpx.AsyncClient') as mock_client:
                mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
                
                with with_context({"oidc": {"providers": {"test": mock_oidc_provider}}}):
                    result = await oidc_client_service.get_user_claims(
                        access_token="mock-access-token",
                        id_token="mock-id-token",
                        provider="test"
                    )
                    
                    # Should return userinfo claims
                    assert result == mock_user_claims
                    
                    # Verify userinfo endpoint was called with Bearer token
                    call_args = mock_client.return_value.__aenter__.return_value.get.call_args
                    assert call_args[0][0] == mock_oidc_provider.userinfo_endpoint
                    assert call_args[1]['headers']['Authorization'] == "Bearer mock-access-token"

    @pytest.mark.asyncio
    async def test_get_user_claims_no_id_token_no_userinfo(self, mock_oidc_provider):
        """Test user claims when neither ID token nor userinfo endpoint available."""
        # Remove userinfo endpoint
        mock_oidc_provider.userinfo_endpoint = None
        
        with with_context({"oidc": {"providers": {"test": mock_oidc_provider}}}):
            result = await oidc_client_service.get_user_claims(
                access_token="mock-access-token",
                id_token=None,
                provider="test"
            )
            
            # Should return empty dict when no sources available
            assert result == {}

    @pytest.mark.asyncio
    async def test_refresh_access_token_success(self, mock_oidc_provider, mock_httpx_response):
        """Test successful token refresh."""
        mock_response_data = {
            "access_token": "new-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "refresh_token": "new-refresh-token"
        }
        mock_response = mock_httpx_response(mock_response_data)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            with with_context({"oidc": {"providers": {"test": mock_oidc_provider}}}):
                result = await oidc_client_service.refresh_access_token(
                    refresh_token="old-refresh-token",
                    provider="test"
                )
                
                # Verify response
                assert isinstance(result, TokenResponse)
                assert result.access_token == "new-access-token"
                assert result.refresh_token == "new-refresh-token"
                
                # Verify the HTTP call
                call_args = mock_client.return_value.__aenter__.return_value.post.call_args
                form_data = call_args[1]['data']
                assert form_data['grant_type'] == 'refresh_token'
                assert form_data['refresh_token'] == 'old-refresh-token'
                assert form_data['client_id'] == mock_oidc_provider.client_id

    @pytest.mark.asyncio
    async def test_refresh_access_token_http_error(self, mock_oidc_provider, mock_httpx_response):
        """Test token refresh with HTTP error."""
        mock_response = mock_httpx_response({}, status_code=400)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            with with_context({"oidc": {"providers": {"test": mock_oidc_provider}}}):
                with pytest.raises(httpx.HTTPStatusError):
                    await oidc_client_service.refresh_access_token(
                        refresh_token="old-refresh-token",
                        provider="test"
                    )

    def test_token_response_expires_at_property(self):
        """Test TokenResponse expires_at property calculation."""
        token_response = TokenResponse(
            access_token="test-token",
            token_type="Bearer",
            expires_in=3600
        )
        
        # expires_at should be current time + expires_in
        import time
        expected_min = int(time.time()) + 3600 - 1  # Allow 1 second tolerance
        expected_max = int(time.time()) + 3600 + 1
        
        assert expected_min <= token_response.expires_at <= expected_max