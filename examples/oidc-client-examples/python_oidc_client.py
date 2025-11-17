"""
Python OIDC Client Example for API Forge

This example demonstrates how to authenticate with an API Forge backend using OIDC.
It handles the authorization code flow with PKCE for secure authentication.

Dependencies:
    pip install requests authlib
"""

import base64
import hashlib
import secrets
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import requests

# from authlib.integrations.requests_client import OAuth2Session


class APIForgeClient:
    """
    OIDC client for authenticating with API Forge backend.

    This client implements the Authorization Code Flow with PKCE (Proof Key for Code Exchange)
    for secure authentication without exposing client secrets.
    """

    def __init__(
        self,
        api_base_url: str,
        client_id: str,
        redirect_uri: str = "http://localhost:8080/callback",
        provider: str = "google",
    ):
        """
        Initialize the API Forge client.

        Args:
            api_base_url: Base URL of your API Forge backend (e.g., "https://api.example.com")
            client_id: OAuth client ID from your OIDC provider
            redirect_uri: Redirect URI registered with your OIDC provider
            provider: OIDC provider name ("google", "microsoft", or "keycloak")
        """
        self.api_base_url = api_base_url.rstrip("/")
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.provider = provider
        self.session = requests.Session()
        self.access_token: str | None = None
        self.refresh_token: str | None = None

    def _generate_pkce_pair(self) -> tuple[str, str]:
        """Generate PKCE code verifier and challenge."""
        # Generate code verifier (43-128 characters)
        code_verifier = (
            base64.urlsafe_b64encode(secrets.token_bytes(32))
            .decode("utf-8")
            .rstrip("=")
        )

        # Generate code challenge (SHA256 hash of verifier)
        challenge_bytes = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = (
            base64.urlsafe_b64encode(challenge_bytes).decode("utf-8").rstrip("=")
        )

        return code_verifier, code_challenge

    def get_authorization_url(self) -> tuple[str, str]:
        """
        Get the authorization URL to redirect the user to.

        Returns:
            Tuple of (authorization_url, code_verifier)
            Store the code_verifier securely - you'll need it to exchange the code for tokens.
        """
        code_verifier, code_challenge = self._generate_pkce_pair()
        state = secrets.token_urlsafe(32)

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": "openid profile email",
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        auth_url = f"{self.api_base_url}/auth/web/login?provider={self.provider}&{urlencode(params)}"

        return auth_url, code_verifier

    def exchange_code_for_tokens(self, code: str, code_verifier: str) -> dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            code: Authorization code from the callback
            code_verifier: PKCE code verifier from get_authorization_url()

        Returns:
            Dictionary containing access_token, refresh_token, and token metadata
        """
        token_url = f"{self.api_base_url}/auth/web/token"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": code_verifier,
        }

        response = self.session.post(token_url, data=data)
        response.raise_for_status()

        tokens = response.json()
        self.access_token = tokens.get("access_token")
        self.refresh_token = tokens.get("refresh_token")

        return tokens

    def refresh_access_token(self) -> dict[str, Any]:
        """
        Refresh the access token using the refresh token.

        Returns:
            Dictionary containing new access_token and metadata
        """
        if not self.refresh_token:
            raise ValueError("No refresh token available")

        token_url = f"{self.api_base_url}/auth/web/token"

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
        }

        response = self.session.post(token_url, data=data)
        response.raise_for_status()

        tokens = response.json()
        self.access_token = tokens.get("access_token")
        if "refresh_token" in tokens:
            self.refresh_token = tokens["refresh_token"]

        return tokens

    def get_user_info(self) -> dict[str, Any]:
        """
        Get user information from the /auth/me endpoint.

        Returns:
            Dictionary containing user information (email, name, etc.)
        """
        if not self.access_token:
            raise ValueError("No access token available. Please authenticate first.")

        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = self.session.get(f"{self.api_base_url}/auth/me", headers=headers)
        response.raise_for_status()

        return response.json()

    def make_authenticated_request(
        self, method: str, endpoint: str, **kwargs
    ) -> requests.Response:
        """
        Make an authenticated API request.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: API endpoint (e.g., "/api/users")
            **kwargs: Additional arguments to pass to requests

        Returns:
            Response object
        """
        if not self.access_token:
            raise ValueError("No access token available. Please authenticate first.")

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token}"

        url = f"{self.api_base_url}{endpoint}"
        response = self.session.request(method, url, headers=headers, **kwargs)

        # Try to refresh token if we get 401
        if response.status_code == 401 and self.refresh_token:
            try:
                self.refresh_access_token()
                headers["Authorization"] = f"Bearer {self.access_token}"
                response = self.session.request(method, url, headers=headers, **kwargs)
            except Exception:
                pass  # Let the original 401 bubble up

        return response

    def logout(self) -> None:
        """Logout and clear tokens."""
        if self.access_token:
            try:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                self.session.post(
                    f"{self.api_base_url}/auth/web/logout", headers=headers
                )
            except Exception:
                pass  # Ignore errors during logout

        self.access_token = None
        self.refresh_token = None


# Example usage
if __name__ == "__main__":
    import threading
    import webbrowser
    from http.server import BaseHTTPRequestHandler, HTTPServer

    # Configuration
    API_BASE_URL = "http://localhost:8000"
    CLIENT_ID = "your-client-id"
    REDIRECT_URI = "http://localhost:8080/callback"
    PROVIDER = "google"  # or "microsoft", "keycloak"

    # Store code_verifier globally for the callback handler
    code_verifier_storage = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        """Simple HTTP server to handle OAuth callback."""

        def do_GET(self):
            # Parse query parameters
            query = urlparse(self.path).query
            params = parse_qs(query)

            if "code" in params:
                code = params["code"][0]

                # Exchange code for tokens
                client = APIForgeClient(API_BASE_URL, CLIENT_ID, REDIRECT_URI, PROVIDER)
                try:
                    tokens = client.exchange_code_for_tokens(
                        code, code_verifier_storage["verifier"]
                    )

                    # Get user info
                    user_info = client.get_user_info()

                    # Send success response
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"""
                        <html>
                            <body>
                                <h1>Authentication Successful!</h1>
                                <p>You can close this window.</p>
                                <script>window.close();</script>
                            </body>
                        </html>
                    """)

                    print("\n✅ Authentication successful!")
                    print(f"User: {user_info.get('email')}")
                    print(f"Access Token: {tokens.get('access_token', '')[:50]}...")

                    # Example API call
                    response = client.make_authenticated_request("GET", "/api/health")
                    print(f"\n📡 API Health Check: {response.status_code}")

                except Exception as e:
                    print(f"\n❌ Authentication failed: {e}")
                    self.send_response(500)
                    self.end_headers()
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, format, *args):
            pass  # Suppress logging

    # Initialize client
    client = APIForgeClient(API_BASE_URL, CLIENT_ID, REDIRECT_URI, PROVIDER)

    # Get authorization URL
    auth_url, code_verifier = client.get_authorization_url()
    code_verifier_storage["verifier"] = code_verifier

    print("🔐 Starting OAuth authentication flow...")
    print(f"Opening browser to: {auth_url[:100]}...")

    # Start callback server
    server = HTTPServer(("localhost", 8080), CallbackHandler)
    server_thread = threading.Thread(target=server.handle_request)
    server_thread.start()

    # Open browser
    webbrowser.open(auth_url)

    # Wait for callback
    server_thread.join()
    server.server_close()
