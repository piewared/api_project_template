"""Unit tests for core JWT service."""

import time
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from authlib.jose import jwt

from src.core.services import jwt_service
from src.runtime.config import OIDCProviderConfig
from tests.utils import encode_token, oct_jwk


class TestJWTService:
    """Test the JWT service functions in isolation."""

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
            client_id="test-client-id",
            authorization_endpoint="https://test.issuer/auth",
            token_endpoint="https://test.issuer/token",
            issuer="https://test.issuer",
            jwks_uri="https://test.issuer/.well-known/jwks.json",
            redirect_uri="http://localhost:8000/callback",
        )

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear JWKS cache before each test."""
        jwt_service._JWKS_CACHE.clear()
        yield
        jwt_service._JWKS_CACHE.clear()

    class TestClaimExtraction:
        """Test claim extraction utilities."""

        def test_extract_uid_with_custom_claim(self):
            """Should extract UID from custom claim when configured."""
            claims = {"iss": "issuer", "sub": "subject", "custom_uid": "user-123"}

            with patch("src.core.services.jwt_service.settings") as mock_settings:
                mock_settings.uid_claim = "custom_uid"
                result = jwt_service.extract_uid(claims)
                assert result == "user-123"

        def test_extract_uid_fallback_to_issuer_subject(self):
            """Should fall back to issuer|subject when custom claim missing."""
            claims = {"iss": "https://issuer.example", "sub": "user-456"}

            with patch("src.core.services.jwt_service.settings") as mock_settings:
                mock_settings.uid_claim = "missing_claim"
                result = jwt_service.extract_uid(claims)
                assert result == "https://issuer.example|user-456"

        def test_extract_scopes_from_string(self):
            """Should parse space-separated scope string."""
            claims = {"scope": "read write admin"}

            result = jwt_service.extract_scopes(claims)
            assert result == {"read", "write", "admin"}

        def test_extract_scopes_from_list(self):
            """Should handle scope as list."""
            claims = {"scp": ["read", "write"]}

            result = jwt_service.extract_scopes(claims)
            assert result == {"read", "write"}

        def test_extract_scopes_from_multiple_sources(self):
            """Should combine scopes from multiple claim sources."""
            claims = {"scope": "read write", "scp": ["admin"]}

            result = jwt_service.extract_scopes(claims)
            assert result == {"read", "write", "admin"}

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

        def test_extract_empty_claims(self):
            """Should handle missing or empty claims gracefully."""
            claims = {}

            with patch("src.core.services.jwt_service.settings") as mock_settings:
                mock_settings.uid_claim = None
                assert jwt_service.extract_uid(claims) == "None|None"
                assert jwt_service.extract_scopes(claims) == set()
                assert jwt_service.extract_roles(claims) == []

    class TestJWKSFetching:
        """Test JWKS fetching functionality."""

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
        async def test_fetch_jwks_uses_cache(self, valid_jwks, oidc_provider_config):
            """Should return cached JWKS without making HTTP request."""
            cache_key = oidc_provider_config.jwks_uri
            jwt_service._JWKS_CACHE[cache_key] = valid_jwks

            # No HTTP client mock - should not be called
            result = await jwt_service.fetch_jwks(oidc_provider_config)

            assert result == valid_jwks

        @pytest.mark.asyncio
        async def test_fetch_jwks_http_error(self, oidc_provider_config):
            """Should raise HTTPException on HTTP error."""
            with patch("httpx.AsyncClient") as mock_client:
                mock_response = Mock()
                mock_response.raise_for_status.side_effect = Exception("HTTP error")

                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=mock_response
                )

                with pytest.raises(HTTPException) as exc_info:
                    await jwt_service.fetch_jwks(oidc_provider_config)

                assert exc_info.value.status_code == 500
                assert "Failed to fetch JWKS" in str(exc_info.value.detail)

    class TestJWTVerification:
        """Test JWT verification functionality."""

        @pytest.mark.asyncio
        async def test_verify_valid_jwt(self, valid_jwks, oidc_provider_config):
            """Should verify valid JWT successfully."""
            # Mock settings to return our test provider
            with patch("src.core.services.jwt_service.settings") as mock_settings:
                mock_settings.oidc_providers = {"test": oidc_provider_config}
                mock_settings.allowed_algorithms = ["HS256"]
                mock_settings.audiences = ["api://test"]
                mock_settings.clock_skew = 10

                # Setup JWKS cache
                cache_key = oidc_provider_config.jwks_uri
                jwt_service._JWKS_CACHE[cache_key] = valid_jwks

                # Create valid token
                token = encode_token(
                    issuer="https://test.issuer",
                    audience="api://test",
                    key=b"test-secret-key",
                    kid="test-key",
                    extra_claims={"sub": "user-123"},
                )

                result = await jwt_service.verify_jwt(token)

                assert result["iss"] == "https://test.issuer"
                assert result["aud"] == "api://test"
                assert result["sub"] == "user-123"

        @pytest.mark.asyncio
        async def test_verify_jwt_missing_issuer(self):
            """Should reject JWT without issuer claim."""
            # Manually create token without issuer
            payload = {"sub": "user", "aud": "api://test", "exp": int(time.time()) + 60}
            token = jwt.encode({"alg": "HS256"}, payload, b"test-key").decode("utf-8")

            with patch("src.core.services.jwt_service.settings") as mock_settings:
                mock_settings.allowed_algorithms = ["HS256"]

                with pytest.raises(HTTPException) as exc_info:
                    await jwt_service.verify_jwt(token)

                assert exc_info.value.status_code == 401
                assert "missing iss" in exc_info.value.detail.lower()

        @pytest.mark.asyncio
        async def test_verify_jwt_unknown_issuer(
            self, valid_jwks, oidc_provider_config
        ):
            """Should reject JWT from unknown issuer."""
            with patch("src.core.services.jwt_service.settings") as mock_settings:
                mock_settings.oidc_providers = {"test": oidc_provider_config}
                mock_settings.allowed_algorithms = ["HS256"]

                token = encode_token(
                    issuer="https://unknown.issuer",
                    audience="api://test",
                    key=b"test-secret-key",
                    kid="test-key",
                    extra_claims={"sub": "user-123"},
                )

                with pytest.raises(HTTPException) as exc_info:
                    await jwt_service.verify_jwt(token)

                assert exc_info.value.status_code == 401
                assert "unknown issuer" in exc_info.value.detail.lower()

        @pytest.mark.asyncio
        async def test_verify_jwt_wrong_audience(
            self, valid_jwks, oidc_provider_config
        ):
            """Should reject JWT with wrong audience."""
            with patch("src.core.services.jwt_service.settings") as mock_settings:
                mock_settings.oidc_providers = {"test": oidc_provider_config}
                mock_settings.allowed_algorithms = ["HS256"]
                mock_settings.audiences = ["api://test"]
                mock_settings.clock_skew = 10

                # Setup JWKS cache
                cache_key = oidc_provider_config.jwks_uri
                jwt_service._JWKS_CACHE[cache_key] = valid_jwks

                token = encode_token(
                    issuer="https://test.issuer",
                    audience="api://wrong",  # Wrong audience
                    key=b"test-secret-key",
                    kid="test-key",
                    extra_claims={"sub": "user-123"},
                )

                with pytest.raises(HTTPException) as exc_info:
                    await jwt_service.verify_jwt(token)

                assert exc_info.value.status_code == 401
