"""Integration tests for application lifecycle and startup behavior."""

import pytest

from src.app.runtime.context import get_config

config = get_config()


class TestApplicationStartup:
    """Test application startup and configuration validation."""

    @pytest.mark.asyncio
    async def test_startup_initializes_rate_limiter_with_redis(self, monkeypatch):
        """Startup should initialize rate limiter when Redis is configured."""
        # Import app module late to allow monkeypatching
        import src.app.api.http.app as application

        # Ensure no JWKS checks by clearing issuer map
        original_issuer_map = config.oidc.providers
        original_environment = config.app.environment
        original_redis_url = config.redis.url

        try:
            config.oidc.providers.clear()
            config.app.environment = "development"

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
            monkeypatch.setattr(
                application,
                "redis_async",
                type("_m", (), {"from_url": staticmethod(fake_from_url)}),
            )

            config.redis.url = "redis://localhost:6379/0"

            # Call startup
            await application.startup()

            assert init_called["called"] is True

        finally:
            # Restore original settings
            config.oidc.providers.update(original_issuer_map)
            config.app.environment = original_environment
            config.redis.url = original_redis_url

    @pytest.mark.asyncio
    async def test_startup_fails_when_dependencies_missing_in_production(
        self, monkeypatch, oidc_provider_config
    ):
        """Startup should fail in production when rate limiter dependencies are missing."""
        import src.app.api.http.app as application

        # Store original values
        original_environment = config.app.environment
        original_redis_url = config.redis.url

        try:
            # Provide valid issuer map so config validation doesn't fail
            config.oidc.providers["https://issuer.example.com"] = oidc_provider_config
            config.app.environment = "production"

            # Mock JWKS fetching to succeed
            async def fake_fetch_jwks(issuer: str):
                return {"keys": []}

            monkeypatch.setattr(
                "src.app.core.services.jwt_service.fetch_jwks", fake_fetch_jwks
            )

            # Simulate missing dependencies
            monkeypatch.setattr(application, "FastAPILimiter", None)
            monkeypatch.setattr(application, "redis_async", None)

            config.redis.url = "redis://localhost:6379/0"

            with pytest.raises(RuntimeError, match=".*dependencies.*"):
                await application.startup()

        finally:
            # Restore original settings
            config.oidc.providers.pop("https://issuer.example.com", None)
            config.app.environment = original_environment
            config.redis.url = original_redis_url
