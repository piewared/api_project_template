"""Template testing configuration."""

import pytest


@pytest.fixture
def template_path():
    """Path to the template directory."""
    from pathlib import Path
    return Path(__file__).parent.parent