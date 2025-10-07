"""Integration tests for application lifecycle and startup behavior."""

import pytest

from src.app.runtime.context import get_config

config = get_config()


class TestApplicationStartup:
    """Test application startup and configuration validation."""

    @pytest.mark.asyncio
    async def test_startup_initializes_rate_limiter_with_redis(self, monkeypatch):
        """Startup should initialize rate limiter when Redis is configured."""
        from copy import deepcopy

        # Import app module late to allow monkeypatching
        import src.app.api.http.app as application
        from src.app.runtime.context import with_context

        # Create test config with cleared OIDC providers and development environment
        test_config = deepcopy(config)
        test_config.oidc.providers = {}
        test_config.app.environment = "development"
        test_config.redis.url = "redis://localhost:6379/0"

        # Prepare fake Redis and limiter classes
        class DummyRedis:
            pass

        def fake_from_url(url, encoding=None, decode_responses=None):
            # Return the Redis client directly (not a coroutine)
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

        # Call startup within the test context
        with with_context(config_override=test_config):
            await application.startup()

        assert init_called["called"] is True

    @pytest.mark.asyncio
    async def test_startup_fails_when_dependencies_missing_in_production(
        self, monkeypatch, oidc_provider_config
    ):
        """Startup should fail in production when rate limiter dependencies are missing."""
        from copy import deepcopy

        import src.app.api.http.app as application
        from src.app.runtime.context import with_context

        # Create test config based on current config
        test_config = deepcopy(config)
        test_config.app.environment = "production"
        test_config.redis.url = "redis://localhost:6379/0"

        # Simulate missing dependencies
        monkeypatch.setattr(application, "FastAPILimiter", None)
        monkeypatch.setattr(application, "redis_async", None)

        with pytest.raises(RuntimeError, match=".*dependencies.*"):
            with with_context(config_override=test_config):
                await application.startup()
