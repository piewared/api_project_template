"""Integration tests for application lifecycle and startup behavior."""

import pytest

from src.runtime.settings import EnvironmentSettings
from src.runtime.settings import settings as config


class TestApplicationStartup:
    """Test application startup and configuration validation."""

    @pytest.mark.asyncio
    async def test_startup_initializes_rate_limiter_with_redis(self, monkeypatch):
        """Startup should initialize rate limiter when Redis is configured."""
        # Import app module late to allow monkeypatching
        import src.api.http.app as application

        # Ensure no JWKS checks by clearing issuer map
        original_issuer_map = config.oidc_providers
        original_environment = config.environment
        original_redis_url = config.redis_url

        try:
            config.oidc_providers.clear()
            config.environment = "development"

            # Prepare fake Redis and limiter classes
            class DummyRedis:
                pass

            async def fake_from_url(url, encoding=None, decode_responses=None):
                return DummyRedis()

            # Track if init was called
            init_called = {"called": False}

            class DummyLimiter:
                @staticmethod
                async def init(redis):
                    init_called["called"] = True

            # Monkeypatch dependencies
            monkeypatch.setattr(application, "FastAPILimiter", DummyLimiter)
            monkeypatch.setattr(application, "redis_async", type("_m", (), {"from_url": staticmethod(fake_from_url)}))

            config.redis_url = "redis://localhost:6379/0"

            # Call startup
            await application.startup()

            assert init_called["called"] is True

        finally:
            # Restore original settings
            config.oidc_providers.update(original_issuer_map)
            config.environment = original_environment
            config.redis_url = original_redis_url

    @pytest.mark.asyncio
    async def test_startup_fails_when_dependencies_missing_in_production(self, monkeypatch, oidc_provider_config):
        """Startup should fail in production when rate limiter dependencies are missing."""
        import src.api.http.app as application

        # Store original values
        original_environment = config.environment
        original_redis_url = config.redis_url

        try:
            # Provide valid issuer map so config validation doesn't fail
            config.oidc_providers["https://issuer.example.com"] = oidc_provider_config
            config.environment = "production"

            # Mock JWKS fetching to succeed
            async def fake_fetch_jwks(issuer: str):
                return {"keys": []}

            monkeypatch.setattr("src.core.services.jwt_service.fetch_jwks", fake_fetch_jwks)

            # Simulate missing dependencies
            monkeypatch.setattr(application, "FastAPILimiter", None)
            monkeypatch.setattr(application, "redis_async", None)

            config.redis_url = "redis://localhost:6379/0"

            with pytest.raises(RuntimeError, match=".*dependencies.*"):
                await application.startup()

        finally:
            # Restore original settings
            config.oidc_providers.pop("https://issuer.example.com", None)
            config.environment = original_environment
            config.redis_url = original_redis_url
