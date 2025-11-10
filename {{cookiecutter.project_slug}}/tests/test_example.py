"""Example test for your {{cookiecutter.project_name}} application.

This is a starter test file to show you how to structure tests for your project.
Add your own business logic tests here.
"""

from fastapi.testclient import TestClient

from {{cookiecutter.package_name}}.app.api.http.app import app


def test_health_endpoint():
    """Test that the health endpoint is working."""
    client = TestClient(app)
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "api"


def test_readiness_endpoint():
    """Test that the readiness endpoint is working."""
    client = TestClient(app)
    
    response = client.get("/health/ready")
    # Note: May return 503 if services aren't running (database, redis, etc.)
    # In a real test environment, you'd mock these dependencies
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data
    assert "checks" in data


# Add your own business logic tests here
# Example:
# 
# def test_my_business_logic():
#     """Test your custom business logic."""
#     # Arrange
#     # Act  
#     # Assert
#     pass


class TestExample:
    """Example test class for organizing related tests."""
    
    def test_example_functionality(self):
        """Example test method."""
        # This is where you'd test your actual business logic
        # Remove this example and add your real tests
        assert True  # Replace with real assertions
        
    # Add more test methods here...