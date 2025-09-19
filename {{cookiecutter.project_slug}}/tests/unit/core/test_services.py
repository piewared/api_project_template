"""Unit tests for core JWT service."""

import time
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from authlib.jose import jwt

from {{cookiecutter.package_name}}.core.services import jwt_service
from tests.utils import encode_token, oct_jwk


class TestJWTService:
    """Test the JWT service functions in isolation."""

    @pytest.fixture
    def valid_jwks(self):
        """Return valid JWKS data for testing."""
        return {
            "keys": [
                oct_jwk(b"test-secret-key", "test-key"),
                oct_jwk(b"another-key", "key-2")
            ]
        }

    @pytest.fixture
    def jwt_config(self):
        """Return JWT configuration for testing."""
        return {
            "issuer_jwks_map": {"https://test.issuer": "https://test.issuer/.well-known/jwks.json"},
            "allowed_algorithms": ["HS256"],
            "audiences": ["api://test"],
            "clock_skew": 10
        }

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
            claims = {
                "iss": "issuer",
                "sub": "subject", 
                "custom_uid": "user-123"
            }
            
            with patch('{{cookiecutter.package_name}}.core.services.jwt_service.settings') as mock_settings:
                mock_settings.uid_claim = "custom_uid"
                result = jwt_service.extract_uid(claims)
                assert result == "user-123"

        def test_extract_uid_fallback_to_issuer_subject(self):
            """Should fall back to issuer|subject when custom claim missing."""
            claims = {
                "iss": "https://issuer.example",
                "sub": "user-456"
            }
            
            with patch('{{cookiecutter.package_name}}.core.services.jwt_service.settings') as mock_settings:
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
            claims = {
                "scope": "read write",
                "scp": ["admin"]
            }
            
            result = jwt_service.extract_scopes(claims)
            assert result == {"read", "write", "admin"}

        def test_extract_roles_from_string(self):
            """Should parse space-separated roles string."""
            claims = {"roles": "user admin"}
            
            result = jwt_service.extract_roles(claims)
            assert result == {"user", "admin"}

        def test_extract_roles_from_realm_access(self):
            """Should extract roles from Keycloak-style realm_access."""
            claims = {
                "realm_access": {"roles": ["admin", "user"]},
                "roles": "guest"
            }
            
            result = jwt_service.extract_roles(claims)
            assert result == {"admin", "user", "guest"}

        def test_extract_empty_claims(self):
            """Should handle missing or empty claims gracefully."""
            claims = {}
            
            with patch('{{cookiecutter.package_name}}.core.services.jwt_service.settings') as mock_settings:
                mock_settings.uid_claim = None
                assert jwt_service.extract_uid(claims) == "None|None"
                assert jwt_service.extract_scopes(claims) == set()
                assert jwt_service.extract_roles(claims) == set()

    class TestJWKSFetching:
        """Test JWKS fetching functionality."""

        @pytest.mark.asyncio
        async def test_fetch_jwks_success(self, valid_jwks):
            """Should fetch and cache JWKS successfully."""
            with patch('{{cookiecutter.package_name}}.core.services.jwt_service.settings') as mock_settings:
                mock_settings.issuer_jwks_map = {"https://test.issuer": "https://test.jwks.url"}
                
                with patch('httpx.AsyncClient') as mock_client:
                    mock_response = Mock()  # Use regular Mock, not AsyncMock
                    mock_response.json.return_value = valid_jwks  # .json() is synchronous
                    mock_response.raise_for_status = Mock()  # .raise_for_status() is synchronous
                    
                    # Only the .get() call is async
                    mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
                    
                    result = await jwt_service.fetch_jwks("https://test.issuer")
                    
                    assert result == valid_jwks
                    # Verify caching
                    assert jwt_service._JWKS_CACHE["https://test.jwks.url"] == valid_jwks

        @pytest.mark.asyncio
        async def test_fetch_jwks_uses_cache(self, valid_jwks):
            """Should return cached JWKS without making HTTP request."""
            jwks_url = "https://test.jwks.url"
            jwt_service._JWKS_CACHE[jwks_url] = valid_jwks
            
            with patch('{{cookiecutter.package_name}}.core.services.jwt_service.settings') as mock_settings:
                mock_settings.issuer_jwks_map = {"https://test.issuer": jwks_url}
                
                # No HTTP client mock - should not be called
                result = await jwt_service.fetch_jwks("https://test.issuer")
                
                assert result == valid_jwks

        @pytest.mark.asyncio
        async def test_fetch_jwks_unknown_issuer(self):
            """Should raise HTTPException for unknown issuer."""
            with patch('{{cookiecutter.package_name}}.core.services.jwt_service.settings') as mock_settings:
                mock_settings.issuer_jwks_map = {}
                
                with pytest.raises(HTTPException) as exc_info:
                    await jwt_service.fetch_jwks("https://unknown.issuer")
                
                assert exc_info.value.status_code == 401
                assert "unknown issuer" in exc_info.value.detail.lower()

    class TestJWTVerification:
        """Test JWT verification functionality."""

        @pytest.mark.asyncio
        async def test_verify_valid_jwt(self, valid_jwks, jwt_config):
            """Should verify valid JWT successfully."""
            # Setup JWKS cache
            jwks_url = jwt_config["issuer_jwks_map"]["https://test.issuer"]
            jwt_service._JWKS_CACHE[jwks_url] = valid_jwks
            
            # Create valid token
            token = encode_token(
                issuer="https://test.issuer",
                audience="api://test",
                key=b"test-secret-key",
                kid="test-key",
                extra_claims={"sub": "user-123"}
            )
            
            with patch('{{cookiecutter.package_name}}.core.services.jwt_service.settings') as mock_settings:
                mock_settings.issuer_jwks_map = jwt_config["issuer_jwks_map"]
                mock_settings.allowed_algorithms = jwt_config["allowed_algorithms"]
                mock_settings.audiences = jwt_config["audiences"]
                mock_settings.clock_skew = jwt_config["clock_skew"]
                
                result = await jwt_service.verify_jwt(token)
                
                assert result["iss"] == "https://test.issuer"
                assert result["aud"] == "api://test"
                assert result["sub"] == "user-123"

        @pytest.mark.asyncio
        async def test_verify_jwt_missing_issuer(self):
            """Should reject JWT without issuer claim."""
            # Manually create token without issuer
            payload = {"sub": "user", "aud": "api://test", "exp": int(time.time()) + 60}
            token = jwt.encode({"alg": "HS256"}, payload, b"test-key").decode('utf-8')
            
            with patch('{{cookiecutter.package_name}}.core.services.jwt_service.settings') as mock_settings:
                mock_settings.allowed_algorithms = ["HS256"]
                
                with pytest.raises(HTTPException) as exc_info:
                    await jwt_service.verify_jwt(token)
                
                assert exc_info.value.status_code == 401
                assert "missing iss" in exc_info.value.detail.lower()

        @pytest.mark.asyncio  
        async def test_verify_jwt_wrong_audience(self, valid_jwks, jwt_config):
            """Should reject JWT with wrong audience."""
            jwks_url = jwt_config["issuer_jwks_map"]["https://test.issuer"]
            jwt_service._JWKS_CACHE[jwks_url] = valid_jwks
            
            token = encode_token(
                issuer="https://test.issuer",
                audience="api://wrong",  # Wrong audience
                key=b"test-secret-key",
                kid="test-key",
                extra_claims={"sub": "user-123"}
            )
            
            with patch('{{cookiecutter.package_name}}.core.services.jwt_service.settings') as mock_settings:
                mock_settings.issuer_jwks_map = jwt_config["issuer_jwks_map"]
                mock_settings.allowed_algorithms = jwt_config["allowed_algorithms"]
                mock_settings.audiences = jwt_config["audiences"]
                mock_settings.clock_skew = jwt_config["clock_skew"]
                
                with pytest.raises(HTTPException) as exc_info:
                    await jwt_service.verify_jwt(token)
                
                assert exc_info.value.status_code == 401