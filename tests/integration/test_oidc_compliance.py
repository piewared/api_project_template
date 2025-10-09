"""Integration tests for OIDC Relying Party (client) functionality."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.app.api.http.app import app
from src.app.runtime.config.config_data import ConfigData
from src.app.runtime.context import with_context


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


class TestOIDCRelyingParty:
    """Test OIDC Relying Party (client) functionality."""

    def test_me_endpoint_returns_user_auth_state(self, client):
        """Test that /me endpoint returns current user's authentication state."""
        response = client.get("/auth/jit/me")

        assert response.status_code == 200
        result = response.json()

        # Check expected fields in authentication state response
        assert "user_id" in result
        assert "email" in result
        assert "scopes" in result
        assert "roles" in result
        assert "claims" in result

        # In development mode, should have mock data
        assert result["email"] == "dev@example.com"
        assert "read:all" in result["scopes"]
        assert "admin" in result["roles"]

    def test_scope_based_authorization(self, client):
        """Test that scope-based authorization works correctly."""
        # This endpoint requires 'read:protected' scope but dev user has 'read:all'
        response = client.get("/auth/jit/protected-scope")

        # Should return 403 since dev user doesn't have the specific 'read:protected' scope
        assert response.status_code == 403
        result = response.json()
        assert "Missing required scope" in result["detail"]

    def test_role_based_authorization(self, client):
        """Test that role-based authorization works correctly."""
        # This endpoint requires 'admin' role and dev user has 'admin' role
        response = client.get("/auth/jit/protected-role")

        assert response.status_code == 200
        result = response.json()
        assert "You have the required role!" in result["message"]
        assert "user_id" in result

    def test_production_mode_requires_valid_tokens(self, client):
        """Test that production mode requires valid Bearer tokens."""

        mock_config = ConfigData()
        mock_config.app.environment = "production"
        with with_context(config_override=mock_config):
            # Without Authorization header
            response = client.get("/auth/jit/me")

            assert response.status_code == 401
            assert "Authentication required" in response.json()["detail"]

            # With invalid Bearer token format
            response = client.get(
                "/auth/jit/me", headers={"Authorization": "Invalid token"}
            )
        assert response.status_code == 401

    def test_development_mode_provides_mock_authentication(self, client):
        """Test that development mode provides mock authentication for easier testing."""
        response = client.get("/auth/jit/me")

        assert response.status_code == 200
        result = response.json()

        # Should have development user data
        assert result["user_id"] == "93743658555595339"
        assert result["email"] == "dev@example.com"

        # Should have mock claims
        claims = result["claims"]
        assert claims["iss"] == "local-dev"
        assert claims["sub"] == "dev-user"

    def test_authentication_state_structure(self, client):
        """Test that authentication state has proper structure for OIDC client."""
        response = client.get("/auth/jit/me")

        assert response.status_code == 200
        result = response.json()

        # Verify structure matches OIDC client expectations
        assert isinstance(result["user_id"], str)
        assert isinstance(result["email"], str)
        assert isinstance(result["scopes"], list)
        assert isinstance(result["roles"], list)
        assert isinstance(result["claims"], dict)

        # Claims should have OIDC standard structure
        claims = result["claims"]
        assert "iss" in claims  # Issuer
        assert "sub" in claims  # Subject

    def test_authorization_dependencies_work_correctly(self, client):
        """Test that authorization dependencies properly extract and validate claims."""
        # Test scope requirement
        scope_response = client.get("/auth/jit/protected-scope")
        assert scope_response.status_code == 403  # Missing required scope

        # Test role requirement
        role_response = client.get("/auth/jit/protected-role")
        assert role_response.status_code == 200  # Has required role

        role_result = role_response.json()
        assert "user_id" in role_result
        assert role_result["user_id"] == "93743658555595339"  # Dev user ID

    def test_bearer_token_extraction_in_production(self, client):
        """Test Bearer token extraction logic."""
        mock_config = ConfigData()
        mock_config.app.environment = "production"
        with with_context(config_override=mock_config):
            # Test missing Authorization header
            response = client.get("/auth/jit/me")
            assert response.status_code == 401

            # Test invalid Authorization header format
            response = client.get(
                "/auth/jit/me", headers={"Authorization": "NotBearer token"}
            )
            assert response.status_code == 401

            # Test malformed Bearer header
            response = client.get("/auth/jit/me", headers={"Authorization": "Bearer"})
            assert response.status_code == 401

    def test_endpoints_accessible_without_oidc_provider_functionality(self, client):
        """Test that client endpoints don't expose OIDC provider functionality."""
        # These endpoints should NOT exist (were incorrectly implemented as provider endpoints)

        # Discovery endpoint should not exist
        response = client.get("/auth/jit/.well-known/openid-configuration")
        assert response.status_code == 404

        # UserInfo endpoint should not exist
        response = client.get("/auth/jit/userinfo")
        assert response.status_code == 404

        # Token introspection should not exist
        response = client.post("/auth/jit/introspect")
        assert response.status_code == 404
