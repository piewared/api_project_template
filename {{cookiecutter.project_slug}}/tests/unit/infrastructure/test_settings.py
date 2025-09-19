"""Unit tests for runtime settings configuration."""

import pytest
import os
from unittest.mock import patch

from {{cookiecutter.package_name}}.runtime.settings import Settings, _parse_list


class TestParseListHelper:
    """Tests for the _parse_list helper function."""

    def test_empty_values(self):
        """Should handle empty values correctly."""
        assert _parse_list("") == []
        assert _parse_list([]) == []

    def test_string_input(self):
        """Should parse comma-separated strings."""
        assert _parse_list("one,two,three") == ["one", "two", "three"]
        assert _parse_list("one, two, three") == ["one", "two", "three"]
        assert _parse_list("one") == ["one"]

    def test_list_input(self):
        """Should handle list input correctly."""
        assert _parse_list(["one", "two", "three"]) == ["one", "two", "three"]
        assert _parse_list(["1", "2", "3"]) == ["1", "2", "3"]

    def test_json_input(self):
        """Should parse JSON arrays."""
        assert _parse_list('["one", "two", "three"]') == ["one", "two", "three"]
        
    def test_strips_whitespace(self):
        """Should strip whitespace from values."""
        assert _parse_list("  one  ,  two  ,  three  ") == ["one", "two", "three"]
        assert _parse_list(["  one  ", "  two  ", "  three  "]) == ["one", "two", "three"]

    def test_filters_empty_items(self):
        """Should filter out empty items."""
        assert _parse_list("one,,three,") == ["one", "three"]
        assert _parse_list(["one", "", "three", " "]) == ["one", "three"]


class TestSettings:
    """Tests for the Settings class."""

    def test_can_instantiate_with_no_env(self):
        """Should be able to create settings without environment variables."""
        # Mock environment to clear any existing values
        with patch.dict(os.environ, {}, clear=True):
            # Disable .env file loading for this test
            from pydantic_settings import SettingsConfigDict
            
            class TestSettings(Settings):
                model_config = SettingsConfigDict(
                    env_file=None,
                    env_file_encoding="utf-8",
                    env_ignore_empty=True,
                )
            
            settings = TestSettings()
            
            assert settings.environment == "development"
            assert settings.log_level == "INFO"
            assert settings.database_url == "sqlite:///./database.db"
            assert settings.rate_limit_requests == 5
            assert settings.rate_limit_window == 60

    def test_computed_properties(self):
        """Should provide computed properties correctly."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            
            # These are computed from string fields
            assert isinstance(settings.allowed_algorithms, list)
            assert isinstance(settings.audiences, list)
            assert isinstance(settings.cors_origins, list)
            
            # Should have defaults
            assert "RS256" in settings.allowed_algorithms
            assert "api://default" in settings.audiences

    def test_setting_computed_properties(self):
        """Should allow setting computed properties."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            
            # Set algorithms as list
            settings.allowed_algorithms = ["HS256", "RS256"]
            assert settings.allowed_algorithms_str == "HS256,RS256"
            
            # Set audiences as string
            settings.audiences = "api://app,api://admin"
            assert settings.audiences == ["api://app", "api://admin"]

    def test_environment_variable_loading(self):
        """Should load values from environment variables."""
        env_vars = {
            'ENVIRONMENT': 'production',
            'LOG_LEVEL': 'DEBUG',
            'DATABASE_URL': 'postgresql://user:pass@localhost/db',
            'RATE_LIMIT_REQUESTS': '10',
            'RATE_LIMIT_WINDOW': '120'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            from pydantic_settings import SettingsConfigDict
            
            class TestSettings(Settings):
                model_config = SettingsConfigDict(
                    env_file=None,
                    env_file_encoding="utf-8",
                    env_ignore_empty=True,
                )
            
            settings = TestSettings()
            
            assert settings.environment == "production"
            assert settings.log_level == "DEBUG"
            assert settings.database_url == "postgresql://user:pass@localhost/db"
            assert settings.rate_limit_requests == 10
            assert settings.rate_limit_window == 120

    def test_issuer_jwks_map_validation(self):
        """Should validate issuer JWKS map correctly."""
        # Test with JSON string
        env_vars = {
            'JWT_ISSUER_JWKS_MAP': '{"https://issuer.example.com": "https://issuer.example.com/.well-known/jwks.json"}'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            from pydantic_settings import SettingsConfigDict
            
            class TestSettings(Settings):
                model_config = SettingsConfigDict(
                    env_file=None,
                    env_file_encoding="utf-8",
                    env_ignore_empty=True,
                )
            
            settings = TestSettings()
            assert "https://issuer.example.com" in settings.issuer_jwks_map
            assert settings.issuer_jwks_map["https://issuer.example.com"] == "https://issuer.example.com/.well-known/jwks.json"

    def test_validate_runtime_production(self):
        """Should validate production configuration correctly."""
        # Test production requirements - must disable .env file loading
        env_vars = {
            'ENVIRONMENT': 'production',
            'JWT_ISSUER_JWKS_MAP': '{}',  # Empty map should fail
            'JWT_AUDIENCES': 'api://default',
            'DATABASE_URL': 'postgresql://user:pass@localhost/db'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            # Create settings with no env file to avoid interference
            from pydantic_settings import SettingsConfigDict
            
            class TestSettings(Settings):
                model_config = SettingsConfigDict(
                    env_file=None,  # Disable .env file
                    env_file_encoding="utf-8",
                    env_ignore_empty=True,
                )
            
            settings = TestSettings()
            
            with pytest.raises(ValueError, match="JWT_ISSUER_JWKS_MAP must be configured"):
                settings.validate_runtime()

    def test_validate_runtime_redis_url(self):
        """Should validate Redis URL format."""
        env_vars = {
            'REDIS_URL': 'invalid-url'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            # Create settings with no env file to avoid interference
            from pydantic_settings import SettingsConfigDict
            
            class TestSettings(Settings):
                model_config = SettingsConfigDict(
                    env_file=None,  # Disable .env file
                    env_file_encoding="utf-8",
                    env_ignore_empty=True,
                )
            
            settings = TestSettings()
            
            with pytest.raises(ValueError, match="REDIS_URL must be a redis"):
                settings.validate_runtime()

    def test_redis_url_validation_success(self):
        """Should accept valid Redis URLs."""
        from pydantic_settings import SettingsConfigDict
        
        class TestSettings(Settings):
            model_config = SettingsConfigDict(
                env_file=None,  # Disable .env file
                env_file_encoding="utf-8",
                env_ignore_empty=True,
            )
        
        env_vars = {
            'REDIS_URL': 'redis://localhost:6379/0'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = TestSettings()
            settings.validate_runtime()  # Should not raise
            
        env_vars = {
            'REDIS_URL': 'rediss://localhost:6379/0'
        }
        
        with patch.dict(os.environ, env_vars, clear=True):
            settings = TestSettings()
            settings.validate_runtime()  # Should not raise