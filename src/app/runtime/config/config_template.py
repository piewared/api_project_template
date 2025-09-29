"""Configuration template substitution utilities."""

import os
import re
from pathlib import Path

import yaml
from pydantic_core import ValidationError

from src.app.runtime.config.config_data import ConfigData


def substitute_env_vars(text: str) -> str:
    """
    Substitute environment variable placeholders in text.

    Supports formats:
    - ${VAR_NAME} - required variable (raises error if missing)
    - ${VAR_NAME:-default} - optional with default value
    - ${VAR_NAME:?error_message} - required with custom error message
    """
    def replacer(match):
        var_expr = match.group(1)

        # Handle default values: ${VAR:-default}
        if ":-" in var_expr:
            var_name, default = var_expr.split(":-", 1)
            return os.getenv(var_name, default)

        # Handle error messages: ${VAR:?message}
        elif ":?" in var_expr:
            var_name, error_msg = var_expr.split(":?", 1)
            value = os.getenv(var_name)
            if value is None:
                raise ValueError(f"Required environment variable {var_name}: {error_msg}")
            return value

        # Handle required variables: ${VAR}
        else:
            var_name = var_expr
            value = os.getenv(var_name)
            if value is None:
                raise ValueError(f"Required environment variable {var_name} not set")
            return value

    # Match ${...} patterns
    pattern = r'\$\{([^}]+)\}'
    return re.sub(pattern, replacer, text)


def load_templated_yaml(file_path: Path) -> ConfigData:
    """
    Load a YAML file with environment variable substitution.

    Args:
        file_path: Path to the YAML file

    Returns:
        Parsed YAML with environment variables substituted

    Raises:
        ValueError: If required environment variables are missing
        FileNotFoundError: If the YAML file doesn't exist
    """
    with open(file_path) as f:
        content = f.read()

    # Substitute environment variables
    substituted_content = substitute_env_vars(content)

    # Parse YAML
    try:
        loaded = yaml.safe_load(substituted_content)
        if not loaded:
            raise ValueError("Failed to parse YAML")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing YAML: {e}") from e

    # Validate and return as ConfigData
    try:
        # Extract the 'config' section from the YAML structure
        config_data = loaded.get('config', {})
        config = ConfigData(**config_data)
    except ValidationError as e:
        raise ValueError(f"Invalid configuration: {e}") from e

    return config


def validate_config_env_vars() -> dict[str, str]:
    """
    Validate that all required environment variables are set.

    Returns:
        Dictionary of missing variables and their descriptions
    """
    required_vars = {
        'OIDC_KEYCLOAK_CLIENT_ID': 'Keycloak OAuth client ID',
        'OIDC_KEYCLOAK_CLIENT_SECRET': 'Keycloak OAuth client secret',
    }

    missing = {}
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing[var] = description

    return missing


# Example usage
if __name__ == "__main__":
    try:
        config_path = Path("config.yaml")

        config = load_templated_yaml(config_path)
        print("Configuration loaded successfully:")
        print(f"Redis URL: {config.redis.url}")
        print(f"Database URL: {config.database.url}")
        print(f"Keycloak Client ID: {config.oidc.providers['keycloak'].client_id}")
    except ValueError as e:
        print(f"Configuration error: {e}")
    except FileNotFoundError:
        print("config.yaml not found")
