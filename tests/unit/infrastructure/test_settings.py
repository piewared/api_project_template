"""Unit tests for runtime settings configuration."""

import pytest
import os
from unittest.mock import patch

from src.runtime.settings import settings, Settings, EnvironmentSettings
from src.runtime.config import ApplicationConfig


class TestApplicationConfig:
    """Tests for the ApplicationConfig class."""

    def test_default_config(self):
        """Should have sensible defaults."""
        config = ApplicationConfig()

        assert config.jwt.allowed_algorithms == ["RS256", "RS512", "ES256", "ES384"]
        assert config.jwt.audiences == ["api://default"]
        assert config.jwt.uid_claim == "sub"
        assert config.cors.origins == ["http://localhost:3000", "http://localhost:3001"]
        assert config.rate_limit.requests == 100
        assert config.session.max_age == 86400

    def test_environment_specific_config(self):
        """Should apply environment-specific overrides."""
        config = ApplicationConfig()

        # Production config
        prod_config = config.for_environment("production")
        assert prod_config.session.secure_cookies is True
        assert prod_config.cors.origins == []  # Must be explicitly configured

        # Development config
        dev_config = config.for_environment("development")
        assert dev_config.rate_limit.enabled is False

        # Test config
        test_config = config.for_environment("test")
        assert test_config.rate_limit.enabled is False
        assert test_config.session.max_age == 300


class TestEnvironmentSettings:
    """Tests for environment variable-based settings."""

    def test_can_instantiate_with_no_env(self):
        """Should be able to create settings without environment variables."""
        with patch.dict(os.environ, {}, clear=True):
            env_settings = EnvironmentSettings()

            assert env_settings.environment == "development"
            assert env_settings.log_level == "INFO"
            assert env_settings.database_url == "sqlite:///./database.db"
            assert env_settings.base_url == "http://localhost:8000"

    def test_environment_variable_loading(self):
        """Should load values from environment variables."""
        env_vars = {
            "ENVIRONMENT": "production",
            "LOG_LEVEL": "DEBUG",
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "BASE_URL": "https://api.example.com",
            "SECRET_KEY": "super-secret-key",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            env_settings = EnvironmentSettings()

            assert env_settings.environment == "production"
            assert env_settings.log_level == "DEBUG"
            assert env_settings.database_url == "postgresql://user:pass@localhost/db"
            assert env_settings.base_url == "https://api.example.com"
            assert env_settings.secret_key == "super-secret-key"

    def test_oidc_provider_configuration(self):
        """Should configure OIDC providers from environment variables."""
        env_vars = {
            "OIDC_GOOGLE_CLIENT_ID": "google-client-id",
            "OIDC_GOOGLE_CLIENT_SECRET": "google-client-secret",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            env_settings = EnvironmentSettings()
            providers = env_settings.get_oidc_providers()

            assert "google" in providers
            assert providers["google"].client_id == "google-client-id"
            assert providers["google"].client_secret == "google-client-secret"

    def test_validate_runtime_production(self):
        """Should validate production configuration correctly."""
        s = EnvironmentSettings()
        s.environment = "production"

        with pytest.raises(ValueError, match=".*SECRET_KEY.*"):
            s.validate_runtime()

        s.secret_key = "test-secret-key"
        with pytest.raises(ValueError, match=".*SQLite.*"):
            s.validate_runtime()

        s.database_url = "postgresql://user:pass@localhost/dbname"
        with pytest.raises(ValueError, match=".*REDIS.*"):
            s.validate_runtime()

    def test_validate_runtime_redis_url(self):
        """Should validate Redis URL format."""
        env_vars = {"REDIS_URL": "invalid-url"}

        with patch.dict(os.environ, env_vars, clear=True):
            env_settings = EnvironmentSettings()

            with pytest.raises(ValueError, match="REDIS_URL must be a redis"):
                env_settings.validate_runtime()


class TestUnifiedSettings:
    """Tests for the unified settings interface."""

    def test_backward_compatibility(self):
        """Should maintain backward compatibility with existing code."""
        # These should all work as before
        assert hasattr(settings, "environment")
        assert hasattr(settings, "database_url")
        assert hasattr(settings, "allowed_algorithms")
        assert hasattr(settings, "cors_origins")
        assert hasattr(settings, "session_max_age")
        assert hasattr(settings, "oidc_providers")

    def test_settings_values(self):
        """Should provide expected values."""
        assert settings.environment in ["development", "production", "test"]
        assert isinstance(settings.allowed_algorithms, list)
        assert isinstance(settings.cors_origins, list)
        assert isinstance(settings.oidc_providers, dict)

    def test_validation_method(self):
        """Should provide validation method."""
        # Should not raise with default development settings
        settings.validate_runtime()
