#!/usr/bin/env python3
"""Development utilities for OIDC testing and management."""

import argparse
import json
import subprocess
import sys
from urllib.parse import urljoin

import requests


def check_keycloak_status():
    """Check if Keycloak is running and configured."""
    try:
        # Check if Keycloak is running
        response = requests.get("http://localhost:8080/health", timeout=5)
        if response.status_code != 200:
            print("❌ Keycloak is not responding")
            return False
            
        # Check if test realm exists
        response = requests.get("http://localhost:8080/realms/test-realm", timeout=5)
        if response.status_code != 200:
            print("⚠️  Keycloak is running but test-realm is not configured")
            return False
            
        print("✅ Keycloak is running and configured")
        return True
        
    except requests.exceptions.RequestException:
        print("❌ Keycloak is not running")
        return False


def get_access_token(username: str, password: str, realm: str = "test-realm") -> str:
    """Get access token for a test user."""
    token_url = f"http://localhost:8080/realms/{realm}/protocol/openid-connect/token"
    
    data = {
        "grant_type": "password",
        "client_id": "test-client",
        "client_secret": "test-client-secret",
        "username": username,
        "password": password,
        "scope": "openid profile email",
    }
    
    try:
        response = requests.post(token_url, data=data, timeout=10)
        response.raise_for_status()
        
        tokens = response.json()
        return tokens["access_token"]
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to get access token: {e}")
        return None


def decode_token(token: str):
    """Decode and display JWT token (unsafe - for development only)."""
    import base64
    
    try:
        # Split token into parts
        parts = token.split(".")
        if len(parts) != 3:
            print("❌ Invalid JWT format")
            return
            
        # Decode header
        header_b64 = parts[0]
        # Add padding if needed
        header_b64 += "=" * (4 - len(header_b64) % 4)
        header = json.loads(base64.b64decode(header_b64))
        
        # Decode payload
        payload_b64 = parts[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        
        print("🔍 JWT Token Information:")
        print(f"Header: {json.dumps(header, indent=2)}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        print("\n⚠️  Note: Signature verification skipped (development only)")
        
    except Exception as e:
        print(f"❌ Failed to decode token: {e}")


def test_userinfo(token: str, realm: str = "test-realm"):
    """Test userinfo endpoint with access token."""
    userinfo_url = f"http://localhost:8080/realms/{realm}/protocol/openid-connect/userinfo"
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(userinfo_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        userinfo = response.json()
        print("👤 User Info:")
        print(json.dumps(userinfo, indent=2))
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to get user info: {e}")


def run_integration_tests():
    """Run integration tests with Keycloak."""
    if not check_keycloak_status():
        print("❌ Keycloak is not properly configured. Run ./dev/setup_dev.sh first")
        return False
        
    try:
        result = subprocess.run([
            "python", "-m", "pytest", 
            "tests/integration/test_oidc_keycloak.py", 
            "-v"
        ], check=False)
        
        return result.returncode == 0
        
    except subprocess.SubprocessError as e:
        print(f"❌ Failed to run tests: {e}")
        return False


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="OIDC Development Utilities")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Status command
    subparsers.add_parser("status", help="Check Keycloak status")
    
    # Token command
    token_parser = subparsers.add_parser("token", help="Get access token for test user")
    token_parser.add_argument("--username", default="testuser1", help="Username")
    token_parser.add_argument("--password", default="password123", help="Password")
    token_parser.add_argument("--realm", default="test-realm", help="Keycloak realm")
    
    # Decode command
    decode_parser = subparsers.add_parser("decode", help="Decode JWT token")
    decode_parser.add_argument("token", help="JWT token to decode")
    
    # Userinfo command
    userinfo_parser = subparsers.add_parser("userinfo", help="Get user info with token")
    userinfo_parser.add_argument("token", help="Access token")
    userinfo_parser.add_argument("--realm", default="test-realm", help="Keycloak realm")
    
    # Test command
    subparsers.add_parser("test", help="Run integration tests")
    
    args = parser.parse_args()
    
    if args.command == "status":
        check_keycloak_status()
        
    elif args.command == "token":
        token = get_access_token(args.username, args.password, args.realm)
        if token:
            print(f"🔑 Access Token: {token}")
            
    elif args.command == "decode":
        decode_token(args.token)
        
    elif args.command == "userinfo":
        test_userinfo(args.token, args.realm)
        
    elif args.command == "test":
        success = run_integration_tests()
        sys.exit(0 if success else 1)
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()