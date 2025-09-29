#!/usr/bin/env python3
"""Keycloak setup script for development environment."""

import sys
import time
from urllib.parse import urljoin

import requests


class KeycloakSetup:
    """Keycloak configuration setup for development."""

    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url
        self.admin_username = "admin"
        self.admin_password = "admin"
        self.access_token = None

    def get_admin_token(self):
        """Get admin access token."""
        token_url = urljoin(
            self.base_url, "/realms/master/protocol/openid-connect/token"
        )

        data = {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": self.admin_username,
            "password": self.admin_password,
        }

        response = requests.post(token_url, data=data, timeout=30)
        response.raise_for_status()

        token_data = response.json()
        self.access_token = token_data["access_token"]
        return self.access_token

    def create_realm(self, realm_name="test-realm"):
        """Create a test realm."""
        url = urljoin(self.base_url, "/admin/realms")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        realm_config = {
            "realm": realm_name,
            "enabled": True,
            "displayName": "Test Realm for OIDC Development",
            "loginWithEmailAllowed": True,
            "duplicateEmailsAllowed": False,
            "rememberMe": True,
            "verifyEmail": False,
            "resetPasswordAllowed": True,
            "editUsernameAllowed": True,
            "bruteForceProtected": False,
        }

        # Check if realm already exists
        check_url = urljoin(self.base_url, f"/admin/realms/{realm_name}")
        check_response = requests.get(check_url, headers=headers)

        if check_response.status_code == 200:
            print(f"✅ Realm '{realm_name}' already exists")
            return

        response = requests.post(url, json=realm_config, headers=headers, timeout=30)

        if response.status_code == 201:
            print(f"✅ Created realm '{realm_name}'")
        else:
            print(
                f"❌ Failed to create realm: {response.status_code} - {response.text}"
            )
            sys.exit(1)

    def create_client(self, realm_name="test-realm", client_id="test-client"):
        """Create a test client for OIDC flows."""
        url = urljoin(self.base_url, f"/admin/realms/{realm_name}/clients")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        client_config = {
            "clientId": client_id,
            "enabled": True,
            "protocol": "openid-connect",
            "publicClient": False,
            "standardFlowEnabled": True,  # Authorization Code Flow
            "implicitFlowEnabled": False,
            "directAccessGrantsEnabled": True,  # Resource Owner Password Credentials
            "serviceAccountsEnabled": True,
            "authorizationServicesEnabled": False,
            "redirectUris": [
                "http://localhost:8000/auth/web/callback",
                "http://localhost:3000/*",
                "http://localhost:3001/*",
            ],
            "webOrigins": [
                "http://localhost:8000",
                "http://localhost:3000",
                "http://localhost:3001",
            ],
            "attributes": {
                "pkce.code.challenge.method": "S256",
                "post.logout.redirect.uris": "http://localhost:8000/*",
            },
        }

        # Check if client already exists
        check_response = requests.get(
            url, headers=headers, params={"clientId": client_id}
        )
        if check_response.status_code == 200 and check_response.json():
            print(f"✅ Client '{client_id}' already exists")
            return

        response = requests.post(url, json=client_config, headers=headers, timeout=30)

        if response.status_code == 201:
            print(f"✅ Created client '{client_id}'")

            # Get the created client to set the secret
            clients_response = requests.get(
                url, headers=headers, params={"clientId": client_id}
            )
            clients = clients_response.json()

            if clients:
                client_uuid = clients[0]["id"]
                self.set_client_secret(realm_name, client_uuid, "test-client-secret")

        else:
            print(
                f"❌ Failed to create client: {response.status_code} - {response.text}"
            )
            sys.exit(1)

    def set_client_secret(self, realm_name, client_uuid, secret):
        """Set client secret."""
        url = urljoin(
            self.base_url, f"/admin/realms/{realm_name}/clients/{client_uuid}"
        )

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        update_config = {"secret": secret}

        response = requests.put(url, json=update_config, headers=headers, timeout=30)

        if response.status_code == 204:
            print(f"✅ Set client secret")
        else:
            print(f"❌ Failed to set client secret: {response.status_code}")

    def create_test_users(self, realm_name="test-realm"):
        """Create test users."""
        url = urljoin(self.base_url, f"/admin/realms/{realm_name}/users")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        test_users = [
            {
                "username": "testuser1",
                "email": "testuser1@example.com",
                "firstName": "Test",
                "lastName": "User One",
                "enabled": True,
                "emailVerified": True,
                "credentials": [
                    {
                        "type": "password",
                        "value": "password123",
                        "temporary": False,
                    }
                ],
            },
            {
                "username": "testuser2",
                "email": "testuser2@example.com",
                "firstName": "Test",
                "lastName": "User Two",
                "enabled": True,
                "emailVerified": True,
                "credentials": [
                    {
                        "type": "password",
                        "value": "password123",
                        "temporary": False,
                    }
                ],
            },
        ]

        for user in test_users:
            # Check if user exists
            check_response = requests.get(
                url, headers=headers, params={"username": user["username"]}
            )
            if check_response.status_code == 200 and check_response.json():
                print(f"✅ User '{user['username']}' already exists")
                continue

            response = requests.post(url, json=user, headers=headers, timeout=30)

            if response.status_code == 201:
                print(f"✅ Created user '{user['username']}'")
            else:
                print(
                    f"❌ Failed to create user '{user['username']}': {response.status_code}"
                )

    def print_configuration(self, realm_name="test-realm", client_id="test-client"):
        """Print the configuration details."""
        print("\n" + "=" * 60)
        print("🔧 KEYCLOAK CONFIGURATION")
        print("=" * 60)
        print(f"Issuer URL: {self.base_url}/realms/{realm_name}")
        print(
            f"Authorization Endpoint: {self.base_url}/realms/{realm_name}/protocol/openid-connect/auth"
        )
        print(
            f"Token Endpoint: {self.base_url}/realms/{realm_name}/protocol/openid-connect/token"
        )
        print(
            f"Userinfo Endpoint: {self.base_url}/realms/{realm_name}/protocol/openid-connect/userinfo"
        )
        print(
            f"JWKS URI: {self.base_url}/realms/{realm_name}/protocol/openid-connect/certs"
        )
        print(
            f"End Session Endpoint: {self.base_url}/realms/{realm_name}/protocol/openid-connect/logout"
        )
        print("")
        print(f"Client ID: {client_id}")
        print(f"Client Secret: test-client-secret")
        print(f"Redirect URI: http://localhost:8000/auth/web/callback")
        print("")
        print("Environment Variables for .env:")
        print(f"OIDC_DEFAULT_CLIENT_ID={client_id}")
        print(f"OIDC_DEFAULT_CLIENT_SECRET=test-client-secret")
        print(f"OIDC_DEFAULT_ISSUER={self.base_url}/realms/{realm_name}")
        print(
            f"OIDC_DEFAULT_AUTHORIZATION_ENDPOINT={self.base_url}/realms/{realm_name}/protocol/openid-connect/auth"
        )
        print(
            f"OIDC_DEFAULT_TOKEN_ENDPOINT={self.base_url}/realms/{realm_name}/protocol/openid-connect/token"
        )
        print(
            f"OIDC_DEFAULT_USERINFO_ENDPOINT={self.base_url}/realms/{realm_name}/protocol/openid-connect/userinfo"
        )
        print(
            f"OIDC_DEFAULT_JWKS_URI={self.base_url}/realms/{realm_name}/protocol/openid-connect/certs"
        )
        print(
            f"OIDC_DEFAULT_END_SESSION_ENDPOINT={self.base_url}/realms/{realm_name}/protocol/openid-connect/logout"
        )
        print(f"OIDC_DEFAULT_REDIRECT_URI=http://localhost:8000/auth/web/callback")
        print("=" * 60)

    def setup_all(self):
        """Run the complete setup."""
        try:
            print("🔐 Getting admin token...")
            self.get_admin_token()

            print("🏢 Creating test realm...")
            self.create_realm()

            print("📱 Creating test client...")
            self.create_client()

            print("👥 Creating test users...")
            self.create_test_users()

            self.print_configuration()

        except requests.exceptions.RequestException as e:
            print(f"❌ Error communicating with Keycloak: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            sys.exit(1)


def main():
    """Main entry point."""
    print("🔧 Configuring Keycloak for development...")

    setup = KeycloakSetup()

    # Wait a bit for Keycloak to be fully ready
    time.sleep(5)

    setup.setup_all()

    print("\n✅ Keycloak configuration complete!")


if __name__ == "__main__":
    main()
