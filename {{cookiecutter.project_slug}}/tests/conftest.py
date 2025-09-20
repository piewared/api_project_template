"""Test configuration and fixtures for {{cookiecutter.project_name}}."""

import pytest
from fastapi.testclient import TestClient

from {{cookiecutter.package_name}}.api.http.app import app


@pytest.fixture(name="client")
def client_fixture():
    """Create a test client."""
    return TestClient(app)