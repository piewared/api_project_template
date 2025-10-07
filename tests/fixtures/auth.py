"""Consolidated authentication fixtures for all auth-related testing."""

import time
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.services.jwt_service import (
    generate_access_token,
    generate_id_token,
    generate_refresh_token,
)
from src.app.core.services.oidc_client_service import TokenResponse
from src.app.core.services.session_service import AuthSession, UserSession
from src.app.entities.core.user import User, UserRepository
from src.app.entities.core.user_identity import UserIdentity, UserIdentityRepository
from src.app.runtime.config.config_data import (
    ConfigData,
    OIDCConfig,
    OIDCProviderConfig,
)


# Base Data Fixtures
@pytest.fixture
def base_oidc_provider() -> OIDCProviderConfig:
    """Standard OIDC provider configuration used across tests."""
    return OIDCProviderConfig(
        client_id="test-client-id",
        client_secret="test-client-secret",
        authorization_endpoint="https://mock-provider.test/authorize",
        token_endpoint="https://mock-provider.test/token",
        userinfo_endpoint="https://mock-provider.test/userinfo",
        end_session_endpoint="https://mock-provider.test/logout",
        issuer="https://mock-provider.test",
        jwks_uri="https://mock-provider.test/.well-known/jwks.json",
        scopes=["openid", "profile", "email"],
        redirect_uri="http://localhost:8000/auth/web/callback",
    )


@pytest.fixture
def test_user() -> User:
    """Standard test user used across tests."""
    return User(
        id="12345678-1234-5678-9abc-123456789012",
        email="test@example.com",
        phone='123-456-7890',
        address='123 Main St, Anytown, USA',
        first_name="Test",
        last_name="User",
    )


@pytest.fixture
def test_user_identity(
    test_user: User, base_oidc_provider: OIDCProviderConfig
) -> UserIdentity:
    """Standard user identity mapping."""

    test_user_subject = "user-12345"

    return UserIdentity(
        issuer=base_oidc_provider.issuer,
        subject=test_user_subject,
        uid_claim=f"{base_oidc_provider.issuer}|{test_user_subject}",
        user_id=test_user.id,
    )


@pytest.fixture
def test_user_claims_dict(test_user: User, test_user_identity: UserIdentity) -> dict[str, Any]:
    """Standard user claims from OIDC provider."""
    return {
        "iss": test_user_identity.issuer,
        "sub": test_user_identity.subject,
        "aud": "test-client-id",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "email": test_user.email,
        "email_verified": True,
        "given_name": test_user.first_name,
        "family_name": test_user.last_name,
        "name": f"{test_user.first_name} {test_user.last_name}",
        "picture": "https://example.com/avatar.jpg",
    }



@pytest.fixture
def test_identity_token_jwt(
    secret_for_jwt_generation: str,
    kid_for_jwt: str,
    session_nonce: str,
    test_user_identity: UserIdentity,
    test_user: User,
) -> str:
    """Standard identity token JWT for user identity."""
    return generate_id_token(
        nonce=session_nonce,
        issuer=test_user_identity.issuer,
        user_id=test_user_identity.subject,
        email=test_user.email,
        given_name=test_user.first_name,
        family_name=test_user.last_name,
        secret=secret_for_jwt_generation,
        kid=kid_for_jwt,
    )


@pytest.fixture
def test_token_response(
    secret_for_jwt_generation: str,
    kid_for_jwt: str,
    test_user: User,
    test_identity_token_jwt: str,
) -> TokenResponse:
    """Standard OIDC token response."""
    return TokenResponse(
        access_token=generate_access_token(
            test_user.id, secret=secret_for_jwt_generation, kid=kid_for_jwt
        ),
        token_type="Bearer",
        expires_in=3600,
        refresh_token=generate_refresh_token(
            test_user.id, secret=secret_for_jwt_generation, kid=kid_for_jwt
        ),
        id_token=test_identity_token_jwt,
    )


@pytest.fixture
def test_client_fingerprint() -> str:
    """Standard client fingerprint for test requests.

    This simulates what extract_client_fingerprint() would return
    for TestClient requests in the test environment.
    """
    # TestClient doesn't have real headers or IP, so we simulate
    # what would be hashed in a test environment
    from src.app.core.security import hash_client_fingerprint

    # TestClient typically has these characteristics
    user_agent = "testclient"  # Default TestClient user-agent
    client_ip = "testclient"  # TestClient uses "testclient" as host

    return hash_client_fingerprint(user_agent, client_ip)


@pytest.fixture
def test_auth_session(test_client_fingerprint: str, session_nonce: str) -> AuthSession:
    """Standard auth session for OIDC flow."""
    return AuthSession.create(
        session_id="auth-session-123",
        pkce_verifier="test-pkce-verifier",
        state="test-state-parameter",
        provider="default",
        nonce=session_nonce,
        return_to="/dashboard",
        client_fingerprint_hash=test_client_fingerprint,
    )


@pytest.fixture
def test_user_session(test_user: User, test_client_fingerprint: str) -> UserSession:
    """Standard user session."""
    return UserSession(
        id="user-session-456",
        user_id=test_user.id,
        provider="default",
        refresh_token="mock-refresh-token",
        access_token="mock-access-token",
        access_token_expires_at=int(time.time()) + 3600,
        created_at=int(time.time()),
        last_accessed_at=int(time.time()),
        expires_at=int(time.time()) + 86400,
        client_fingerprint=test_client_fingerprint,
    )


# Configuration Fixtures
@pytest.fixture
def auth_test_config(base_oidc_provider: OIDCProviderConfig) -> ConfigData:
    """Application configuration for authentication testing."""
    config = ConfigData()
    config.app.environment = "test"
    config.oidc = OIDCConfig()
    config.oidc.providers = {"default": base_oidc_provider}
    config.jwt.allowed_algorithms = ["HS256"]
    config.jwt.audiences = ["test-client-id"]
    config.jwt.claims.user_id = "app_uid"
    return config


# Database Fixtures with Test Data
@pytest.fixture
def populated_session(session: Session) -> Session:
    """Session populated with test user and identity data."""
    user_repo = UserRepository(session)
    identity_repo = UserIdentityRepository(session)

    # Create test user
    test_user = User(
        first_name="Test",
        last_name="User",
        email="test@example.com",
    )
    user_repo.create(test_user)

    # Create test identity
    test_identity = UserIdentity(
        issuer="https://test.example.com",
        subject="test-subject-123",
        uid_claim="test.example.com|test-subject-123",
        user_id=test_user.id,
    )
    identity_repo.create(test_identity)

    return session


# Service Mocks
@pytest.fixture
def mock_oidc_client_service():
    """Mock OIDC client service with standard responses."""
    mock_service = AsyncMock()
    mock_service.generate_pkce_pair.return_value = ("test-verifier", "test-challenge")
    mock_service.generate_state.return_value = "test-state"
    mock_service.exchange_code_for_tokens.return_value = TokenResponse(
        access_token="mock-access-token",
        token_type="Bearer",
        expires_in=3600,
        refresh_token="mock-refresh-token",
        id_token="mock-id-token",
    )
    mock_service.get_user_claims.return_value = {
        "iss": "https://mock-provider.test",
        "sub": "user-12345",
        "email": "test@example.com",
        "given_name": "Test",
        "family_name": "User",
    }
    mock_service.refresh_access_token.return_value = TokenResponse(
        access_token="new-access-token",
        token_type="Bearer",
        expires_in=3600,
        refresh_token="new-refresh-token",
    )
    return mock_service


@pytest.fixture
def mock_session_service(
    test_user: User, test_auth_session: AuthSession, test_user_session: UserSession
):
    """Mock session service with standard responses."""
    mock_service = AsyncMock()
    mock_service.create_auth_session.return_value = test_auth_session.id
    mock_service.get_auth_session.return_value = test_auth_session
    mock_service.delete_auth_session.return_value = None
    mock_service.provision_user_from_claims.return_value = test_user
    mock_service.create_user_session.return_value = test_user_session.id
    mock_service.get_user_session.return_value = test_user_session
    mock_service.delete_user_session.return_value = None
    mock_service.refresh_user_session.return_value = "new-user-session-789"
    mock_service.generate_csrf_token.return_value = "csrf-token-123"
    mock_service.validate_csrf_token.return_value = True
    return mock_service


# HTTP Client Fixtures
@pytest.fixture
def auth_test_client(client: TestClient, auth_test_config) -> Generator[TestClient]:
    """Test client configured with authentication setup."""
    from src.app.runtime.context import with_context

    with with_context(config_override=auth_test_config):
        yield client


# Mock Response Factories
@pytest.fixture
def mock_http_response_factory():
    """Factory for creating mock HTTP responses."""
    from unittest.mock import Mock

    import httpx

    def create_response(json_data: dict, status_code: int = 200) -> Mock:
        mock_response = Mock()
        mock_response.json.return_value = json_data
        mock_response.status_code = status_code

        def raise_for_status():
            if status_code >= 400:
                mock_request = Mock(spec=httpx.Request)
                mock_response_obj = Mock(spec=httpx.Response)
                mock_response_obj.status_code = status_code
                raise httpx.HTTPStatusError(
                    f"HTTP {status_code}",
                    request=mock_request,
                    response=mock_response_obj,
                )

        mock_response.raise_for_status = raise_for_status
        return mock_response

    return create_response
