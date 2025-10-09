"""Integration tests for OIDC BFF router with local Keycloak."""

import os
from unittest.mock import patch

import pytest
import requests
from fastapi.testclient import TestClient

from src.app.api.http.app import app
from src.app.runtime.config.config_data import (
    ConfigData,
    OIDCConfig,
    OIDCProviderConfig,
)
from src.app.runtime.context import with_context


@pytest.fixture
def keycloak_config():
    """Keycloak configuration for local development server."""
    base_url = "http://localhost:8080"
    realm = "test-realm"

    return OIDCProviderConfig(
        client_id="test-client",
        client_secret="test-client-secret",
        authorization_endpoint=f"{base_url}/realms/{realm}/protocol/openid-connect/auth",
        token_endpoint=f"{base_url}/realms/{realm}/protocol/openid-connect/token",
        userinfo_endpoint=f"{base_url}/realms/{realm}/protocol/openid-connect/userinfo",
        end_session_endpoint=f"{base_url}/realms/{realm}/protocol/openid-connect/logout",
        issuer=f"{base_url}/realms/{realm}",
        jwks_uri=f"{base_url}/realms/{realm}/protocol/openid-connect/certs",
        scopes=["openid", "profile", "email"],
        redirect_uri="http://localhost:8000/auth/web/callback",
    )


@pytest.fixture
def integration_client(keycloak_config):
    """Test client configured for integration tests with local Keycloak."""
    config = ConfigData()
    config.app.environment = "test"
    config.oidc = OIDCConfig()
    config.oidc.providers = {"default": keycloak_config}

    # Also patch the module-level configs that are imported at startup
    with with_context(config_override=config):
        with TestClient(app) as client:
            yield client


def keycloak_available() -> bool:
    """Check if local Keycloak is running and configured."""
    try:
        response = requests.get("http://localhost:8080/realms/test-realm", timeout=5)
        return response.status_code == 200
    except (requests.exceptions.RequestException, requests.exceptions.Timeout):
        return False


@pytest.mark.skipif(
    not keycloak_available(),
    reason="Local Keycloak not available. Run ./dev/setup_dev.sh first",
)
class TestOIDCIntegration:
    """Integration tests with local Keycloak instance."""

    def test_keycloak_is_configured(self):
        """Verify that Keycloak is properly configured."""
        # Test realm exists
        response = requests.get("http://localhost:8080/realms/test-realm", timeout=10)
        assert response.status_code == 200

        realm_data = response.json()
        assert realm_data["realm"] == "test-realm"

        # Test OIDC configuration endpoint
        response = requests.get(
            "http://localhost:8080/realms/test-realm/.well-known/openid-configuration",
            timeout=10,
        )
        assert response.status_code == 200

        config = response.json()
        assert "authorization_endpoint" in config
        assert "token_endpoint" in config
        assert "userinfo_endpoint" in config
        assert "jwks_uri" in config
        assert "issuer" in config
        assert config["issuer"] == "http://localhost:8080/realms/test-realm"

        # Test JWKS endpoint (required for token validation)
        response = requests.get(
            "http://localhost:8080/realms/test-realm/protocol/openid-connect/certs",
            timeout=10,
        )
        assert response.status_code == 200

        jwks = response.json()
        assert "keys" in jwks
        assert len(jwks["keys"]) > 0

        # Verify key has required fields for OIDC
        key = jwks["keys"][0]
        assert "kty" in key  # Key Type
        assert "use" in key  # Public Key Use
        assert "kid" in key  # Key ID

    def test_login_initiates_oidc_flow(self, integration_client):
        """Test that /login redirects to Keycloak authorization endpoint."""
        response = integration_client.get(
            "/auth/web/login", params={"provider": "default"}, follow_redirects=False
        )

        assert response.status_code == 302

        location = response.headers["location"]
        assert (
            "localhost:8080/realms/test-realm/protocol/openid-connect/auth" in location
        )
        assert "client_id=test-client" in location
        assert "response_type=code" in location
        assert "code_challenge=" in location
        assert "code_challenge_method=S256" in location
        assert "state=" in location

    def test_login_with_redirect_uri(self, integration_client):
        """Test login with custom redirect URI."""
        response = integration_client.get(
            "/auth/web/login",
            params={"provider": "default", "redirect_uri": "/dashboard"},
            follow_redirects=False,
        )

        assert response.status_code == 302

        # Check that auth session cookie is set
        cookies = response.cookies
        assert "auth_session_id" in cookies

    def test_callback_without_session_fails(self, integration_client):
        """Test that callback fails without proper auth session."""
        response = integration_client.get(
            "/auth/web/callback",
            params={"code": "test-code", "state": "test-state"},
            follow_redirects=False,
        )

        assert response.status_code == 400
        assert "Missing auth session" in response.json()["detail"]

    def test_me_endpoint_without_session(self, integration_client):
        """Test /me endpoint without session returns unauthenticated state."""
        response = integration_client.get("/auth/web/me")

        assert response.status_code == 200
        result = response.json()
        assert result["authenticated"] is False
        assert result["user"] is None
        assert result["csrf_token"] is None

    def test_logout_without_session(self, integration_client):
        """Test logout without session returns 401."""
        response = integration_client.post("/auth/web/logout")

        # Should fail with 401 because no session/CSRF token provided
        assert response.status_code == 401
        result = response.json()
        assert "No session found" in result["detail"]

    @pytest.mark.manual
    def test_full_oidc_flow_manual(self, integration_client):
        """Manual test for full OIDC flow - requires manual intervention.

        This test demonstrates the full flow but requires manual browser interaction.
        Run this test manually to verify end-to-end functionality.
        """
        # Step 1: Initiate login
        response = integration_client.get(
            "/auth/web/login", params={"provider": "default"}, follow_redirects=False
        )

        assert response.status_code == 302
        auth_url = response.headers["location"]
        auth_session_cookie = response.cookies.get("auth_session_id")

        print(f"\n🔗 Authorization URL: {auth_url}")
        print(f"🍪 Auth Session Cookie: {auth_session_cookie}")
        print("\n📋 Manual Steps:")
        print("1. Open the authorization URL in a browser")
        print("2. Log in with testuser1@example.com / password123")
        print("3. Copy the callback URL with code and state parameters")
        print("4. Extract the code and state to complete the test")

        # Note: In a real integration test, you would:
        # 1. Use a headless browser (Selenium/Playwright) to automate the login
        # 2. Handle the callback automatically
        # 3. Verify the user session is created
        # 4. Test the protected endpoints

        # For now, we just verify the setup is correct
        assert auth_url.startswith("http://localhost:8080/realms/test-realm")
        assert auth_session_cookie is not None


@pytest.mark.skipif(
    keycloak_available(),
    reason="Keycloak is available - these tests are for when it's not running",
)
class TestWithoutKeycloak:
    """Tests that verify behavior when Keycloak is not available."""

    def test_login_fails_gracefully_without_keycloak(self, integration_client):
        """Test that login fails gracefully when Keycloak is not available."""
        # This test runs when Keycloak is NOT available
        # It verifies that the application handles OIDC provider unavailability

        with patch(
            "src.app.core.services.oidc_client_service.httpx.AsyncClient"
        ) as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = (
                Exception("Connection error")
            )

            response = integration_client.get(
                "/auth/web/login",
                params={"provider": "default"},
                follow_redirects=False,
            )

            # The login should still redirect (to create auth session)
            # The actual failure happens during token exchange
            assert response.status_code == 302
