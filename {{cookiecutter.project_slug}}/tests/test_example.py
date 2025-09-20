"""Example test for your {{cookiecutter.project_name}} application.

This is a starter test file to show you how to structure tests for your project.
Add your own business logic tests here.
"""

from fastapi.testclient import TestClient

from {{cookiecutter.package_name}}.api.http.app import app


def test_health_endpoint():
    """Test that the health endpoint is working."""
    client = TestClient(app)
    
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_readiness_endpoint():
    """Test that the readiness endpoint is working."""
    client = TestClient(app)
    
    response = client.get("/ready")
    assert response.status_code == 200
    assert "status" in response.json()


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