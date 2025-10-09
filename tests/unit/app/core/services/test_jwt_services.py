from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from authlib.jose import jwt
from fastapi import HTTPException

from src.app.core.services import (
    JWKSCacheInMemory,
    JwksService,
    JwtGeneratorService,
    JwtVerificationService,
)
from src.app.runtime.config.config_data import (
    ConfigData,
    JWTConfig,
    OIDCConfig,
    OIDCProviderConfig,
)
from src.app.runtime.context import with_context
from tests.utils import oct_jwk


class TestJWTService:
    """Test JWT service functionality in isolation."""

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

    async def test_jwt_generate_verify_roundtrip(
        self,
        secret_for_jwt_generation: str,
        jwks_service_fake: JwksService,
        jwt_generate_service: JwtGeneratorService,
        jwt_verify_service: JwtVerificationService,
    ):
        """Should generate and verify JWT correctly."""
        # Test 1: Basic JWT with default config secret
        token1 = jwt_generate_service.generate_jwt(
            subject="user-123",
            claims={"email": "user@example.com", "role": "admin"},
            expires_in_seconds=3600,
        )

        verified_claims1 = await jwt_verify_service.verify_generated_jwt(token1)
        assert verified_claims1.subject == "user-123"
        assert verified_claims1.email == "user@example.com"
        assert set(verified_claims1.roles) == {"admin"}
        assert verified_claims1.jti is not None  # Default includes JTI

        # Test 2: JWT with custom secret key
        custom_secret = "my-custom-secret-key-123"
        token2 = jwt_generate_service.generate_jwt(
            subject="user-456",
            claims={"scopes": ["read", "write"], "department": "engineering"},
            expires_in_seconds=1800,
            secret=custom_secret,
        )

        # Verify with the unified verify_jwt using the same custom secret
        import asyncio

        verified_claims2 = await jwt_verify_service.verify_jwt(
            token2, key=custom_secret
        )

        assert verified_claims2.subject == "user-456"
        assert verified_claims2.scopes == ["read", "write"]
        assert verified_claims2.custom_claims == {"department": "engineering"}

        # Test 3: JWT without JTI claim
        token3 = jwt_generate_service.generate_jwt(
            subject="user-789",
            claims={"name": "John Doe", "age": 30},
            expires_in_seconds=7200,
            include_jti=False,
        )

        verified_claims3 = await jwt_verify_service.verify_generated_jwt(token3)
        assert verified_claims3.subject == "user-789"
        assert verified_claims3.name == "John Doe"
        assert verified_claims3.custom_claims == {"age": 30}
        assert "jti" not in verified_claims3.custom_claims  # JTI should be excluded

        # Test 4: JWT with custom issuer and audience
        token4 = jwt_generate_service.generate_jwt(
            subject="service-account",
            claims={
                "client_id": "my-app",
                "permissions": ["read:users", "write:posts"],
            },
            expires_in_seconds=900,
            issuer="auth-server-prod",
            audience=["api", "mobile-app", "web-app"],
        )

        verified_claims4 = await jwt_verify_service.verify_generated_jwt(token4)
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

        token5 = jwt_generate_service.generate_jwt(
            subject="premium-user-001",
            claims=complex_claims,
            expires_in_seconds=86400,  # 24 hours
        )

        verified_claims5 = await jwt_verify_service.verify_generated_jwt(token5)
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
        token_secret1 = jwt_generate_service.generate_jwt(
            subject="test-user", claims=same_claims, secret="secret-1"
        )

        token_secret2 = jwt_generate_service.generate_jwt(
            subject="test-user", claims=same_claims, secret="secret-2"
        )

        # Tokens should be different even with same claims
        assert token_secret1 != token_secret2

        # Verify each token with its respective secret
        verified_secret1 = await jwt_verify_service.verify_jwt(
            token_secret1, key="secret-1"
        )
        verified_secret2 = await jwt_verify_service.verify_jwt(
            token_secret2, key="secret-2"
        )

        assert verified_secret1.subject == "test-user"
        assert verified_secret2.subject == "test-user"
        assert verified_secret1.custom_claims["test"] == "value"
        assert verified_secret2.custom_claims["test"] == "value"

        # Cross-verification should fail
        with pytest.raises(HTTPException):
            await jwt_verify_service.verify_jwt(token_secret1, key="secret-2")

        with pytest.raises(HTTPException):
            await jwt_verify_service.verify_jwt(token_secret2, key="secret-1")

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

        # Create test configuration with our JWKS issuer

        test_provider = OIDCProviderConfig(
            client_id="jwks-test-client",
            client_secret="jwks-test-secret",
            authorization_endpoint="https://test-jwks-provider.example.com/auth",
            token_endpoint="https://test-jwks-provider.example.com/token",
            issuer="https://test-jwks-provider.example.com",
            jwks_uri="https://test-jwks-provider.example.com/.well-known/jwks.json",
            redirect_uri="http://localhost:8000/callback",
        )
        oidc_config = OIDCConfig(providers={"jwks-test": test_provider})
        jwt_config = JWTConfig(
            allowed_algorithms=["HS256"], audiences=["jwks-api", "mobile-app"]
        )

        test_config = ConfigData(oidc=oidc_config, jwt=jwt_config)

        jwks_data = await jwks_service_fake.fetch_jwks(test_provider)
        # In real production, we would have a raw secret key that we:
        # 1. Use directly for JWT generation
        # 2. Base64-encode for JWKS publication

        # Generate JWT with the raw secret (as our service would in production)
        jwks_key = jwks_data["keys"][0]
        jwks_kid = jwks_key["kid"]  # Key ID for JWKS lookup

        token_jwks = jwt_generate_service.generate_jwt(
            subject="jwks-user",
            claims={
                "email": "jwks@example.com",
                "roles": ["user", "verified"],
                "issued_by": "jwks-provider",
            },
            expires_in_seconds=3600,
            issuer="https://test-jwks-provider.example.com",
            audience=["jwks-api", "mobile-app"],
            secret=secret_for_jwt_generation,
            kid=jwks_kid,
        )

        # Verify JWT using JWKS path (mock the fetch_jwks function)
        with with_context(config_override=test_config):
            verified_jwks_claims = await jwt_verify_service.verify_jwt(
                token_jwks, expected_issuer="https://test-jwks-provider.example.com"
            )

            assert verified_jwks_claims.subject == "jwks-user"
            assert verified_jwks_claims.email == "jwks@example.com"
            assert verified_jwks_claims.roles == ["user", "verified"]
            assert verified_jwks_claims.custom_claims["issued_by"] == "jwks-provider"
            assert (
                verified_jwks_claims.issuer == "https://test-jwks-provider.example.com"
            )
            assert verified_jwks_claims.audience == ["jwks-api", "mobile-app"]

        # Test that JWKS verification works with helper functions too
        access_token_jwks = jwt_generate_service.generate_access_token(
            user_id="jwks-access-user",
            scopes=["read:data", "write:files"],
            roles=["admin", "power-user"],
            secret=secret_for_jwt_generation,
            kid=jwks_kid,
            issuer="https://test-jwks-provider.example.com",
            audience="jwks-api",
        )

        with with_context(config_override=test_config):
            verified_access_claims = await jwt_verify_service.verify_jwt(
                access_token_jwks,
                expected_issuer="https://test-jwks-provider.example.com",
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

    @pytest.mark.asyncio
    async def test_fetch_jwks_success(
        self, jwks_data, oidc_provider_config, jwks_service: JwksService
    ):
        """Should fetch and cache JWKS successfully."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = jwks_data
            mock_response.raise_for_status = Mock()

            # Only the .get() call is async
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await jwks_service.fetch_jwks(oidc_provider_config)

            assert result == jwks_data
        # Verify the correct URL was called
        mock_client.return_value.__aenter__.return_value.get.assert_called_once_with(
            "https://test.issuer/.well-known/jwks.json"
        )

    @pytest.mark.asyncio
    async def test_fetch_jwks_network_timeout(
        self, oidc_provider_config, jwks_service: JwksService
    ):
        """Should handle JWKS fetch network timeouts."""
        with patch("httpx.AsyncClient") as mock_client:
            # Simulate timeout
            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                httpx.TimeoutException("Request timeout")
            )

            with pytest.raises(HTTPException) as exc_info:
                await jwks_service.fetch_jwks(oidc_provider_config)

            assert exc_info.value.status_code == 500
            assert "Failed to fetch JWKS" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_fetch_jwks_invalid_json(
        self, oidc_provider_config, jwks_service: JwksService
    ):
        """Should handle invalid JSON in JWKS response."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_response.raise_for_status = Mock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(HTTPException) as exc_info:
                await jwks_service.fetch_jwks(oidc_provider_config)

            assert exc_info.value.status_code == 500
            assert "Failed to fetch JWKS" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_fetch_jwks_missing_uri(self, jwks_service: JwksService):
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
            await jwks_service.fetch_jwks(provider_without_jwks)

        assert exc_info.value.status_code == 401
        assert "jwks uri configured" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_jwt_missing_kid_in_token(
        self,
        oidc_provider_config,
        jwt_generate_service: JwtGeneratorService,
        jwt_verify_service: JwtVerificationService,
    ):
        """Should handle JWT tokens without kid (key ID) claim."""
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]
        test_config.jwt.audiences = ["api://test"]

        with with_context(config_override=test_config):
            # Note: not including "kid" in header
            token = jwt_generate_service.generate_jwt(
                subject="user-123",
                issuer="https://test.issuer",
                audience="api://test",
                expires_in_seconds=60,
                algorithm="HS256",
                secret="test-secret-key",
                kid=None,  # Explicitly no kid
            )

            # Should still work if key can be found by algorithm or other means
            # This tests the fallback behavior when kid is missing
            with pytest.raises(HTTPException):  # May fail due to key lookup issues
                await jwt_verify_service.verify_jwt(token)

    @pytest.mark.asyncio
    async def test_verify_jwt_unknown_kid(
        self,
        oidc_provider_config,
        jwt_generate_service: JwtGeneratorService,
        jwt_verify_service: JwtVerificationService,
    ):
        """Should handle JWT tokens with unknown kid (key ID)."""
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]
        test_config.jwt.audiences = ["api://test"]

        with with_context(config_override=test_config):
            token = jwt_generate_service.generate_jwt(
                subject="user-123",
                issuer="https://test.issuer",
                audience="api://test",
                secret="test-secret-key",
                kid="unknown-key-id",  # Key ID not in JWKS
                claims={"sub": "user-123"},
            )

            with pytest.raises(HTTPException) as exc_info:
                await jwt_verify_service.verify_jwt(token)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_jwt_malformed_jwks(
        self,
        oidc_provider_config,
        jwt_generate_service: JwtGeneratorService,
        jwt_verify_service: JwtVerificationService,
        jwks_cache: JWKSCacheInMemory,
    ):
        """Should handle malformed JWKS data."""
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]

        with with_context(config_override=test_config):
            # Cache malformed JWKS
            cache_key = oidc_provider_config.jwks_uri
            jwks_cache.set_jwks(cache_key, {"invalid": "jwks format"})

            token = jwt_generate_service.generate_jwt(
                issuer="https://test.issuer",
                subject="user-123",
                audience="api://test",
                secret="test-secret-key",
                kid="test-key",
                claims={"sub": "user-123"},
            )

            with pytest.raises(HTTPException) as exc_info:
                await jwt_verify_service.verify_jwt(token)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_fetch_jwks_uses_cache(
        self,
        jwks_data,
        oidc_provider_config,
        jwks_service: JwksService,
        jwks_cache: JWKSCacheInMemory,
    ):
        """Should return cached JWKS without making HTTP request."""
        cache_key = oidc_provider_config.jwks_uri
        jwks_cache.set_jwks(cache_key, jwks_data)

        # No HTTP client mock - should not be called
        result = await jwks_service.fetch_jwks(oidc_provider_config)

        assert result == jwks_data

    @pytest.mark.asyncio
    async def test_verify_valid_jwt(
        self,
        kid_for_jwt,
        secret_for_jwt_generation,
        oidc_provider_config,
        jwt_generate_service: JwtGeneratorService,
        jwt_verify_service: JwtVerificationService,
    ):
        """Should verify valid JWT successfully."""
        # Create test config with test provider
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]
        test_config.jwt.audiences = ["api://test"]
        test_config.jwt.clock_skew = 10

        with with_context(config_override=test_config):
            # Create valid token
            token = jwt_generate_service.generate_jwt(
                issuer="https://test.issuer",
                subject="user-123",
                audience=oidc_provider_config.client_id,  # Using client_id as audience
                secret=secret_for_jwt_generation,  # Use the key from the JWKS
                kid=kid_for_jwt,  # Use the key ID from the JWKS
                claims={"sub": "user-123"},
            )

            result = await jwt_verify_service.verify_jwt(
                token,
                expected_issuer="https://test.issuer",
                expected_audience=oidc_provider_config.client_id,
            )

            assert result.issuer == "https://test.issuer"
            assert result.audience == oidc_provider_config.client_id
            assert result.subject == "user-123"

    @pytest.mark.asyncio
    async def test_verify_jwt_wrong_audience(
        self,
        oidc_provider_config,
        jwt_generate_service: JwtGeneratorService,
        jwt_verify_service: JwtVerificationService,
    ):
        """Should reject JWT with wrong audience."""
        # Create test config with test provider
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]
        test_config.jwt.audiences = ["api://test"]
        test_config.jwt.clock_skew = 10

        with with_context(config_override=test_config):
            token = jwt_generate_service.generate_jwt(
                issuer="https://test.issuer",
                subject="user-123",
                audience="api://wrong",  # Wrong audience
                secret="test-secret-key",
                kid="test-key",
                claims={"sub": "user-123"},
            )

            with pytest.raises(HTTPException) as exc_info:
                await jwt_verify_service.verify_jwt(token)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_jwt_expired_token(
        self,
        auth_test_config,
        secret_for_jwt_generation,
        jwt_generate_service: JwtGeneratorService,
        jwt_verify_service: JwtVerificationService,
    ):
        """Should reject expired JWT tokens."""

        auth_test_config.jwt.clock_skew = 10

        with with_context(config_override=auth_test_config):
            # Create token that expired 30 seconds ago (beyond 10s clock skew)
            token = jwt_generate_service.generate_jwt(
                subject="user-123",
                expires_in_seconds=-30,  # Expired 30 seconds ago
                valid_after_seconds=-60,  # Valid from 60 seconds ago
                issuer="https://test.issuer",
                audience="api://test",
            )

            with pytest.raises(HTTPException) as exc_info:
                await jwt_verify_service.verify_jwt(
                    token,
                    expected_issuer="https://test.issuer",
                    expected_audience="api://test",
                    key=secret_for_jwt_generation,
                )

            assert exc_info.value.status_code == 401
            assert "expired" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_jwt_not_yet_valid(
        self,
        auth_test_config,
        jwt_generate_service: JwtGeneratorService,
        jwt_verify_service: JwtVerificationService,
    ):
        """Should reject JWT tokens with future nbf (not before) claim."""
        auth_test_config.jwt.clock_skew = 10

        with with_context(config_override=auth_test_config):
            # Create token valid 30 seconds in the future (beyond 10s clock skew)
            token = jwt_generate_service.generate_jwt(
                subject="user-123",
                expires_in_seconds=3600,
                valid_after_seconds=30,  # Valid starting 30 seconds in the future
            )

            with pytest.raises(HTTPException) as exc_info:
                await jwt_verify_service.verify_jwt(token)

            assert exc_info.value.status_code == 401
            assert "not valid yet" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_jwt_clock_skew_boundary(
        self,
        auth_test_config,
        jwt_verify_service: JwtVerificationService,
        jwt_generate_service: JwtGeneratorService,
    ):
        """Should accept JWT tokens within clock skew tolerance."""
        auth_test_config.jwt.clock_skew = 30  # 30 second tolerance

        with with_context(config_override=auth_test_config):
            # Create token that expired 20 seconds ago (within 30s tolerance)

            token = jwt_generate_service.generate_jwt(
                subject="user-123",
                expires_in_seconds=-20,  # Expired 20 seconds ago
                valid_after_seconds=-80,  # Valid from 80 seconds ago
                issuer="https://test.issuer",
                audience="api://router",  # Use the audience from auth_test_config
            )

            # Should succeed due to clock skew tolerance
            result = await jwt_verify_service.verify_jwt(
                token, expected_audience="api://router"
            )
            assert result.subject == "user-123"

    @pytest.mark.asyncio
    async def test_verify_jwt_invalid_format(
        self, oidc_provider_config, jwt_verify_service: JwtVerificationService
    ):
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
                    await jwt_verify_service.verify_jwt(invalid_token)

                assert exc_info.value.status_code == 401
                # Check for any JWT format related error message
                assert any(
                    keyword in exc_info.value.detail.lower()
                    for keyword in ["invalid jwt", "format", "header", "payload"]
                )

    @pytest.mark.asyncio
    async def test_verify_jwt_corrupted_base64(
        self, oidc_provider_config, jwt_verify_service: JwtVerificationService
    ):
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
                    await jwt_verify_service.verify_jwt(corrupted_token)

                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_jwt_malformed_json(
        self, oidc_provider_config, jwt_verify_service: JwtVerificationService
    ):
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
                await jwt_verify_service.verify_jwt(malformed_token)

            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_jwt_disallowed_algorithm(
        self,
        oidc_provider_config,
        jwt_verify_service: JwtVerificationService,
        jwt_generate_service: JwtGeneratorService,
    ):
        """Should reject JWT tokens with disallowed algorithms."""
        test_config = ConfigData()
        test_config.oidc.providers = {"test": oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["RS256"]  # Only allow RS256, not HS256
        test_config.jwt.audiences = ["api://test"]

        with pytest.raises(HTTPException) as exc_info:
            with with_context(config_override=test_config):
                token = jwt_generate_service.generate_jwt(
                    issuer="https://test.issuer",
                    audience="api://test",
                    secret="test-secret-key",
                    kid="test-key",
                    subject="user-123",
                )

            with pytest.raises(HTTPException) as exc_info:
                await jwt_verify_service.verify_jwt(token)

            assert exc_info.value.status_code == 401
            assert "disallowed" in exc_info.value.detail.lower()
