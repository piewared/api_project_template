import os
from unittest.mock import patch

import pytest

from src.app.runtime.config.config import (
    ApplicationConfig,
    _get_oidc_providers,
    get_config,
    with_context,
)
from src.app.runtime.config.settings import EnvironmentVariables


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
            assert env_vars.secret_key == "dev-secret-key"

    def test_environment_variable_loading(self):
        """Test loading from environment variables."""
        test_env = {
            "ENVIRONMENT": "production",
            "LOG_LEVEL": "DEBUG",
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "BASE_URL": "https://api.example.com",
            "REDIS_URL": "redis://localhost:6379/0",
            "SECRET_KEY": "production-secret",
        }

        with patch.dict(os.environ, test_env, clear=True):
            env_vars = EnvironmentVariables()

            assert env_vars.environment == "production"
            assert env_vars.log_level == "DEBUG"
            assert env_vars.database_url == "postgresql://user:pass@localhost/db"
            assert env_vars.base_url == "https://api.example.com"
            assert env_vars.redis_url == "redis://localhost:6379/0"
            assert env_vars.secret_key == "production-secret"

    def test_oidc_variables_parsing(self):
        """Test OIDC environment variable parsing."""
        test_env = {
            "OIDC_REDIRECT_URI": "https://app.example.com/auth/callback",
            "OIDC_GOOGLE_CLIENT_ID": "google-client-id",
            "OIDC_GOOGLE_CLIENT_SECRET": "google-client-secret",
            "OIDC_MICROSOFT_CLIENT_ID": "ms-client-id",
            "OIDC_CUSTOM_PROVIDER_CLIENT_ID": "custom-client-id",
        }

        with patch.dict(os.environ, test_env, clear=True):
            env_vars = EnvironmentVariables()

            assert env_vars.oidc_redirect_uri == "https://app.example.com/auth/callback"

            oidc_vars = env_vars.oidc_variables
            assert "google" in oidc_vars
            assert oidc_vars["google"]["client_id"] == "google-client-id"
            assert oidc_vars["google"]["client_secret"] == "google-client-secret"

            assert "microsoft" in oidc_vars
            assert oidc_vars["microsoft"]["client_id"] == "ms-client-id"

            assert "custom_provider" in oidc_vars
            assert oidc_vars["custom_provider"]["client_id"] == "custom-client-id"

    def test_environment_validation(self):
        """Test environment validation with invalid values."""
        test_env = {"ENVIRONMENT": "invalid-env"}

        with pytest.raises(ValueError):
            with patch.dict(os.environ, test_env, clear=True):
                EnvironmentVariables()


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

    def test_development_environment_config(self):
        """Test development environment-specific configuration."""
        test_env = {"ENVIRONMENT": "development"}

        with patch.dict(os.environ, test_env, clear=True):
            env_vars = EnvironmentVariables()
            config = ApplicationConfig.from_environment(env_vars)

            assert config.environment == "development"
            # Development defaults
            assert config.session.secure_cookies is False
            # CORS origins should include localhost defaults
            assert "http://localhost:3000" in config.cors.origins
            assert "http://localhost:3001" in config.cors.origins

    def test_production_environment_config(self):
        """Test production environment-specific configuration."""
        test_env = {"ENVIRONMENT": "production"}

        with patch.dict(os.environ, test_env, clear=True):
            env_vars = EnvironmentVariables()
            config = ApplicationConfig.from_environment(env_vars)

            assert config.environment == "production"
            # Production defaults
            assert config.session.secure_cookies is True
            # Production should have empty CORS origins by default
            assert config.cors.origins == []

    def test_test_environment_config(self):
        """Test test environment-specific configuration."""
        test_env = {"ENVIRONMENT": "test"}

        with patch.dict(os.environ, test_env, clear=True):
            env_vars = EnvironmentVariables()
            config = ApplicationConfig.from_environment(env_vars)

            assert config.environment == "test"
            # Test environment should have specific settings
            assert hasattr(config, "session")
            assert hasattr(config, "cors")

    def test_config_property_access(self):
        """Test configuration convenience property access."""
        config = ApplicationConfig()

        # Test property shortcuts exist
        assert hasattr(config, "cors_origins")
        assert hasattr(config, "allowed_algorithms")
        assert hasattr(config, "audiences")
        assert hasattr(config, "uid_claim")
        assert hasattr(config, "session_max_age")
        assert hasattr(config, "oidc_providers")

        # Test property values match nested config
        assert config.cors_origins == config.cors.origins
        assert config.allowed_algorithms == config.jwt.allowed_algorithms
        assert config.audiences == config.jwt.audiences
        assert config.uid_claim == config.jwt.uid_claim
        assert config.session_max_age == config.session.max_age
        assert config.oidc_providers == config.oidc.providers


class TestOIDCConfiguration:
    """Test OIDC configuration and YAML loading."""

    @pytest.fixture(autouse=True)
    def mock_yaml_loading(self):
        """Mock YAML loading to prevent interference."""
        with patch("src.app.runtime.config._load_oidc_yaml_config", return_value={}):
            yield

    def test_default_oidc_providers(self):
        """Test default OIDC providers are available."""
        with patch.dict(os.environ, {}, clear=True):
            providers = _get_oidc_providers()

            assert "google" in providers
            assert "microsoft" in providers

            google = providers["google"]
            assert (
                google.authorization_endpoint
                == "https://accounts.google.com/o/oauth2/v2/auth"
            )
            assert google.issuer == "https://accounts.google.com"

    def test_yaml_overrides_default_provider(self):
        """Test YAML config overrides default providers."""
        yaml_content = {
            "google": {
                "scopes": ["openid", "profile"],
                "issuer": "https://custom.google.com",
            }
        }

        with patch(
            "src.app.runtime.config._load_oidc_yaml_config", return_value=yaml_content
        ):
            providers = _get_oidc_providers()

            google = providers["google"]
            assert google.scopes == ["openid", "profile"]
            assert google.issuer == "https://custom.google.com"
            # Other fields should remain from defaults
            assert (
                google.authorization_endpoint
                == "https://accounts.google.com/o/oauth2/v2/auth"
            )

    def test_yaml_adds_custom_provider(self):
        """Test YAML can add new providers."""
        yaml_content = {
            "custom_provider": {
                "authorization_endpoint": "https://auth.custom.com/authorize",
                "token_endpoint": "https://auth.custom.com/token",
                "issuer": "https://auth.custom.com",
                "scopes": ["openid", "email"],
            }
        }

        with patch(
            "src.app.runtime.config._load_oidc_yaml_config", return_value=yaml_content
        ):
            providers = _get_oidc_providers()

            assert "custom_provider" in providers
            custom = providers["custom_provider"]
            assert custom.authorization_endpoint == "https://auth.custom.com/authorize"
            assert custom.issuer == "https://auth.custom.com"
            assert custom.scopes == ["openid", "email"]

    def test_yaml_invalid_provider_ignored(self):
        """Test invalid provider configs are ignored."""
        yaml_content = {
            "invalid_provider": {"missing_required_fields": True},
            "google": {"scopes": ["openid", "profile"]},
        }

        with patch(
            "src.app.runtime.config._load_oidc_yaml_config", return_value=yaml_content
        ):
            providers = _get_oidc_providers()

            # Should have google (valid override)
            assert "google" in providers
            # Invalid provider should be ignored
            assert "invalid_provider" not in providers

    def test_environment_overrides_oidc_credentials(self):
        """Test environment variables override OIDC credentials."""
        test_env = {
            "OIDC_GOOGLE_CLIENT_ID": "my-google-client-id",
            "OIDC_GOOGLE_CLIENT_SECRET": "my-google-secret",
            "OIDC_GOOGLE_REDIRECT_URI": "https://myapp.com/auth/google",
        }

        with patch.dict(os.environ, test_env, clear=True):
            env_vars = EnvironmentVariables()
            config = ApplicationConfig.from_environment(env_vars)

            google_provider = config.oidc.providers["google"]
            assert google_provider.client_id == "my-google-client-id"
            assert google_provider.client_secret == "my-google-secret"
            assert google_provider.redirect_uri == "https://myapp.com/auth/google"

    def test_complete_oidc_configuration_flow(self):
        """Test complete OIDC configuration with YAML + environment."""
        yaml_content = {
            "custom_provider": {
                "authorization_endpoint": "https://auth.custom.com/authorize",
                "token_endpoint": "https://auth.custom.com/token",
                "issuer": "https://auth.custom.com",
            }
        }

        test_env = {
            "OIDC_REDIRECT_URI": "https://api.myapp.com/auth/callback",
            "OIDC_GOOGLE_CLIENT_ID": "prod-google-client-id",
            "OIDC_CUSTOM_PROVIDER_CLIENT_ID": "custom-client-id",
        }

        with patch(
            "src.app.runtime.config._load_oidc_yaml_config", return_value=yaml_content
        ):
            with patch.dict(os.environ, test_env, clear=True):
                env_vars = EnvironmentVariables()
                config = ApplicationConfig.from_environment(env_vars)

                # Global config
                assert (
                    config.oidc.global_redirect_uri
                    == "https://api.myapp.com/auth/callback"
                )

                # Google provider with env credentials
                google_provider = config.oidc.providers["google"]
                assert google_provider.client_id == "prod-google-client-id"

                # Custom provider from YAML + env
                custom_provider = config.oidc.providers["custom_provider"]
                assert (
                    custom_provider.authorization_endpoint
                    == "https://auth.custom.com/authorize"
                )
                assert custom_provider.client_id == "custom-client-id"

