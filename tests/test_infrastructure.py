"""Consolidated infrastructure and configuration tests.

This module combines and consolidates tests for:
- Settings and environment variable handling
- Context manager and configuration management
- Dependencies and dependency injection
- Rate limiting functionality
- Application startup and infrastructure components

Replaces:
- tests/unit/infrastructure/test_settings.py (most critical parts)
- tests/unit/runtime/test_context_manager.py (key functionality)
- tests/unit/infrastructure/test_deps.py
- tests/unit/infrastructure/test_rate_limiter.py (core functionality)
- tests/integration/test_application_startup.py
"""

import os
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from src.api.http.deps import require_role, require_scope
from src.api.http.middleware.limiter import DefaultLocalRateLimiter
from src.runtime.config import (
    ApplicationConfig,
    get_config,
    with_context,
)
from src.runtime.settings import EnvironmentVariables


class TestEnvironmentSettings:
    """Test environment variable handling and settings."""

    def test_default_settings(self):
        """Test default environment variable values."""
        with patch.dict(os.environ, {}, clear=True):
            env_vars = EnvironmentVariables()

            assert env_vars.environment == "development"
            assert env_vars.log_level == "INFO"
            assert env_vars.database_url == "sqlite:///./database.db"
            assert env_vars.redis_url is None
            assert env_vars.base_url == "http://localhost:8000"

    def test_environment_variable_loading(self):
        """Test loading from environment variables."""
        test_env = {
            "ENVIRONMENT": "production",
            "LOG_LEVEL": "DEBUG",
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "BASE_URL": "https://api.example.com",
        }

        with patch.dict(os.environ, test_env, clear=True):
            env_vars = EnvironmentVariables()

            assert env_vars.environment == "production"
            assert env_vars.log_level == "DEBUG"
            assert env_vars.database_url == "postgresql://user:pass@localhost/db"
            assert env_vars.base_url == "https://api.example.com"


class TestConfigurationManagement:
    """Test application configuration and context management."""

    def test_default_config_available(self):
        """Test that default configuration is available."""
        config = get_config()
        assert isinstance(config, ApplicationConfig)
        assert config.environment == "development"

    def test_config_context_override(self):
        """Test configuration override with context manager."""
        original_config = get_config()
        original_env = original_config.environment

        # Create test config
        test_config = ApplicationConfig()
        test_config.environment = "test"

        with with_context(config_override=test_config):
            override_config = get_config()
            assert override_config.environment == "test"
            assert override_config is not original_config

        # Should revert after context
        after_config = get_config()
        assert after_config.environment == original_env

    def test_nested_config_overrides(self):
        """Test nested configuration overrides."""
        test_config1 = ApplicationConfig()
        test_config1.environment = "test"

        test_config2 = ApplicationConfig()
        test_config2.environment = "production"

        with with_context(config_override=test_config1):
            assert get_config().environment == "test"

            with with_context(config_override=test_config2):
                assert get_config().environment == "production"

            # Should revert to first override
            assert get_config().environment == "test"


class TestAuthenticationDependencies:
    """Test FastAPI authentication dependencies."""

    def create_mock_request(self, scopes: list[str] | None = None, roles: list[str] | None = None) -> Request:
        """Create mock request with auth context."""
        scopes = scopes or []
        roles = roles or []

        request = Mock(spec=Request)
        request.state = Mock()
        request.state.scopes = set(scopes)
        request.state.roles = set(roles)
        return request

    @pytest.mark.asyncio
    async def test_require_scope_success(self):
        """Test scope requirement with valid scope."""
        request = self.create_mock_request(scopes=["read", "write"])

        # Should not raise for valid scope
        await require_scope("read")(request)
        await require_scope("write")(request)

    @pytest.mark.asyncio
    async def test_require_scope_failure(self):
        """Test scope requirement with missing scope."""
        request = self.create_mock_request(scopes=["read"])

        with pytest.raises(HTTPException) as exc_info:
            await require_scope("admin")(request)

        assert exc_info.value.status_code == 403
        assert "admin" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_require_role_success(self):
        """Test role requirement with valid role."""
        request = self.create_mock_request(roles=["user", "admin"])

        # Should not raise for valid roles
        await require_role("user")(request)
        await require_role("admin")(request)

    @pytest.mark.asyncio
    async def test_require_role_failure(self):
        """Test role requirement with missing role."""
        request = self.create_mock_request(roles=["user"])

        with pytest.raises(HTTPException) as exc_info:
            await require_role("admin")(request)

        assert exc_info.value.status_code == 403
        assert "admin" in str(exc_info.value.detail)


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_local_rate_limiter_creation(self):
        """Test creating local rate limiter."""
        limiter = DefaultLocalRateLimiter()
        assert limiter._hits is not None
        assert limiter._lock is not None

    @pytest.mark.asyncio
    async def test_rate_limiting_within_limits(self):
        """Test rate limiting allows requests within limits."""
        limiter = DefaultLocalRateLimiter()

        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.state = Mock()
        request.scope = {"route": None}
        request.method = "GET"
        request.url = Mock()
        request.url.path = "/test"

        # Create rate limit dependency
        rate_dep = limiter.dependency(times=5, seconds=60)

        # Should allow first few requests
        for _ in range(5):
            await rate_dep(request)

    @pytest.mark.asyncio
    async def test_rate_limiting_exceeds_limits(self):
        """Test rate limiting blocks requests exceeding limits."""
        limiter = DefaultLocalRateLimiter()

        request = Mock(spec=Request)
        request.client = Mock()
        request.client.host = "127.0.0.1"
        request.state = Mock()
        request.scope = {"route": None}
        request.method = "GET"
        request.url = Mock()
        request.url.path = "/test"

        # Create rate limit dependency with very low limit
        rate_dep = limiter.dependency(times=1, seconds=60)

        # First request should pass
        await rate_dep(request)

        # Second request should be blocked
        with pytest.raises(HTTPException) as exc_info:
            await rate_dep(request)

        assert exc_info.value.status_code == 429


class TestApplicationStartup:
    """Test application startup and initialization."""

    def test_app_creation(self):
        """Test that the FastAPI app can be created."""
        from src.api.http.app import app

        assert app is not None
        assert hasattr(app, "routes")
        assert len(app.routes) > 0

    def test_middleware_configuration(self):
        """Test that middleware is properly configured."""
        from src.api.http.app import app

        # Check that middleware is applied
        middleware_types = [type(middleware.cls).__name__ for middleware in app.user_middleware]

        # Should have CORS and potentially other middleware
        assert len(middleware_types) > 0

    def test_environment_configuration_loaded(self):
        """Test that environment-specific configuration is loaded."""
        config = get_config()

        # Basic configuration should be loaded
        assert config.environment in ["development", "test", "production"]
        assert isinstance(config.jwt.allowed_algorithms, list)
        assert len(config.jwt.allowed_algorithms) > 0


class TestInfrastructureIntegration:
    """Test integrated infrastructure functionality."""

    def test_dependency_injection_chain(self):
        """Test that dependency injection works for complex chains."""
        from src.api.http.deps import get_session

        # Should be able to get session factory
        assert get_session is not None
        assert callable(get_session)

    def test_configuration_environment_integration(self):
        """Test that configuration properly integrates with environment."""
        test_env = {
            "ENVIRONMENT": "development",
            "LOG_LEVEL": "DEBUG",
        }

        with patch.dict(os.environ, test_env, clear=True):
            # Create new config instance to pick up env vars
            env_vars = EnvironmentVariables()

            assert env_vars.environment == "development"
            assert env_vars.log_level == "DEBUG"

    def test_error_handling_integration(self, client: TestClient):
        """Test that error handling works across the system."""
        # Try to access non-existent endpoint
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404
