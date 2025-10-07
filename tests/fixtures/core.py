from __future__ import annotations

from collections.abc import Callable, Generator
from copy import deepcopy
from typing import Any

import pytest
from fastapi import Response
from fastapi.testclient import TestClient
from sqlalchemy import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from starlette.requests import Request

from src.app.api.http.app import app
from src.app.api.http.deps import get_session
from src.app.api.http.middleware.limiter import configure_rate_limiter
from src.app.core.services import jwt_service
from src.app.runtime.config.config_data import OIDCProviderConfig
from src.app.runtime.context import get_config, with_context
from tests.fixtures.auth import ConfigData
from tests.utils import oct_jwk

main_config = get_config()

# Models will be imported within fixtures to control timing


_HS_KEY = b"router-secret-key"
_ISSUER = "https://issuer.test"
_AUDIENCE = "api://router"
_KID = "router-key"
_NONCE = "test-nonce-value"


@pytest.fixture
def session_nonce() -> str:
    return _NONCE


@pytest.fixture
def secret_for_jwt_generation() -> str:
    return _HS_KEY.decode("utf-8")


@pytest.fixture
def secret_for_jwt_verification() -> str:
    return _HS_KEY.decode("utf-8")


@pytest.fixture
def kid_for_jwt() -> str:
    return _KID


@pytest.fixture
def jwks_data(secret_for_jwt_generation: str, kid_for_jwt: str) -> dict[str, Any]:
    """Mock JWKS data for testing."""
    return {"keys": [oct_jwk(secret_for_jwt_generation.encode("utf-8"), kid_for_jwt)]}


@pytest.fixture(autouse=True)
def clear_jwks_cache() -> Generator[None]:
    jwt_service._JWKS_CACHE.clear()
    yield
    jwt_service._JWKS_CACHE.clear()


@pytest.fixture
def oidc_provider_config() -> OIDCProviderConfig:
    return OIDCProviderConfig(
        issuer=_ISSUER,
        client_id="test-client-id",
        client_secret="test-client-secret",
        authorization_endpoint=f"{_ISSUER}/authorize",
        token_endpoint=f"{_ISSUER}/token",
        userinfo_endpoint=f"{_ISSUER}/userinfo",
        jwks_uri=f"{_ISSUER}/.well-known/jwks.json",
        scopes=["openid", "profile", "email"],
        redirect_uri="http://localhost/callback",
    )


@pytest.fixture
def request_factory() -> Callable[[dict[str, str]], Request]:
    def _make_request(headers: dict[str, str]) -> Request:
        scope = {
            "type": "http",
            "headers": [
                (name.lower().encode("ascii"), value.encode("latin-1"))
                for name, value in headers.items()
            ],
            "method": "GET",
            "path": "/",
            "query_string": b"",
        }
        return Request(scope)

    return _make_request


@pytest.fixture
def response_factory() -> Callable[[], Any]:
    def _make_response() -> Response:
        return Response(content="", status_code=200)

    return _make_response


@pytest.fixture
def client(
    jwks_data: dict[str, Any],
    session: Session,
    oidc_provider_config: OIDCProviderConfig,
) -> Generator[TestClient]:
    """Yield a TestClient wired to the shared SQLModel session and test-friendly config."""

    def override_get_session():
        yield session

    async def _no_limit(request: Request, response: Response) -> None:
        return None

    async def fake_fetch_jwks(issuer: str):
        return jwks_data

    # Mock the fetch_jwks function
    import unittest.mock

    with unittest.mock.patch.object(jwt_service, "fetch_jwks", fake_fetch_jwks):
        configure_rate_limiter(
            limiter_factory=lambda *_a, **_k: _no_limit
        )  # use local no-op limiter
        app.dependency_overrides[get_session] = override_get_session

        # Create a test configuration with proper overrides
        test_config = ConfigData()
        test_config.app.environment = "test"
        test_config.rate_limiter.requests = 1000
        test_config.rate_limiter.window_ms = 60
        test_config.oidc.providers = {_ISSUER: oidc_provider_config}
        test_config.jwt.allowed_algorithms = ["HS256"]
        test_config.jwt.audiences = [_AUDIENCE]
        test_config.jwt.claims.user_id = "uid"

        try:
            with with_context(config_override=test_config):
                with TestClient(app) as test_client:
                    yield test_client
        finally:
            app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def persistent_session() -> Generator[Session]:
    """Create a persistent database session for session-scoped testing."""
    # Create engine first
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Import models to register them with the metadata
    from src.app.entities.core.user import UserTable  # noqa: F401
    from src.app.entities.core.user_identity import UserIdentityTable  # noqa: F401

    # Create all tables using the current metadata state
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


@pytest.fixture
def session() -> Generator[Session]:
    """Create a fresh database session for testing."""
    # Create a unique engine for each test to avoid metadata conflicts
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Import models to register them with the metadata
    # This needs to happen after engine creation but before table creation
    from src.app.entities.core.user import UserTable  # noqa: F401
    from src.app.entities.core.user_identity import UserIdentityTable  # noqa: F401

    # Create all tables - each test gets a fresh database
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        try:
            yield session
        finally:
            # Explicit cleanup
            session.rollback()
            session.close()
            engine.dispose()


@pytest.fixture(autouse=True)
def reset_session_storage():
    """Reset session storage before each test to avoid Redis connection conflicts."""
    from src.app.core.storage.session_storage import _reset_storage

    _reset_storage()
    yield
    # Reset again after test to clean up
    _reset_storage()


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset all global state before each test to prevent test interference."""
    # Clear JWKS cache (redundant with clear_jwks_cache but ensures it's cleared)
    from src.app.core.services import jwt_service

    jwt_service._JWKS_CACHE.clear()

    # Reset context module global state
    from src.app.runtime import context

    context._default_config = None
    context._default_context = None

    # Clear any context variable state
    try:
        # Get the current context token and reset it
        context._app_context.get()
        # If we got here, there's a context set - we need to clear it
        # We'll let it naturally expire since we can't directly reset ContextVar
    except LookupError:
        # No context set, which is what we want
        pass

    yield

    # Clean up after test
    jwt_service._JWKS_CACHE.clear()
    context._default_config = None
    context._default_context = None
