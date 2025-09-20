"""Integration tests for application lifecycle and startup behavior."""

import pytest

from src.runtime.settings import Settings, settings as config


class TestApplicationStartup:
    """Test application startup and configuration validation."""

    def test_production_config_validation_requires_jwks_map(self):
        """Production environment should require issuer JWKS map configuration."""
        s = Settings()
        s.environment = "production"
        s.issuer_jwks_map = {}
        
        with pytest.raises(ValueError, match=".*JWKS.*"):
            s.validate_runtime()

    @pytest.mark.asyncio
    async def test_startup_initializes_rate_limiter_with_redis(self, monkeypatch):
        """Startup should initialize rate limiter when Redis is configured."""
        # Import app module late to allow monkeypatching
        import src.api.http.app as application

        # Ensure no JWKS checks by clearing issuer map
        original_issuer_map = dict(config.issuer_jwks_map)
        original_environment = config.environment
        original_redis_url = config.redis_url

        try:
            config.issuer_jwks_map = {}
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
            config.issuer_jwks_map = original_issuer_map
            config.environment = original_environment
            config.redis_url = original_redis_url

    @pytest.mark.asyncio
    async def test_startup_fails_when_dependencies_missing_in_production(self, monkeypatch):
        """Startup should fail in production when rate limiter dependencies are missing."""
        import src.api.http.app as application

        # Store original values
        original_issuer_map = dict(config.issuer_jwks_map)
        original_environment = config.environment
        original_redis_url = config.redis_url

        try:
            # Provide valid issuer map so config validation doesn't fail
            config.issuer_jwks_map = {
                "https://issuer.example.com": "https://issuer.example.com/.well-known/jwks.json"
            }
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
            config.issuer_jwks_map = original_issuer_map
            config.environment = original_environment
            config.redis_url = original_redis_url