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
from src.app.runtime.config.settings import EnvironmentVariables
from src.app.runtime.context import get_config
from tests.utils import oct_jwk

main_config = get_config()

# Models will be imported within fixtures to control timing


_HS_KEY = b"router-secret-key"
_ISSUER = "https://issuer.test"
_AUDIENCE = "api://router"
_KID = "router-key"


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
    session: Session, oidc_provider_config: OIDCProviderConfig
) -> Generator[TestClient]:
    """Yield a TestClient wired to the shared SQLModel session and test-friendly config."""

    def override_get_session():
        yield session

    async def _no_limit(request: Request, response: Response) -> None:
        return None

    jwks_data = {"keys": [oct_jwk(_HS_KEY, _KID)]}

    # Store original values to restore later
    original_requests = main_config.rate_limiter.requests
    original_window = main_config.rate_limiter.window_ms
    original_allowed_algorithms = list(main_config.jwt.allowed_algorithms)
    original_audiences = list(main_config.jwt.audiences)
    original_uid_claim = main_config.jwt.claims.user_id
    original_environment = main_config.app.environment

    async def fake_fetch_jwks(issuer: str):
        return jwks_data

    # Mock the fetch_jwks function
    import unittest.mock

    with unittest.mock.patch.object(jwt_service, "fetch_jwks", fake_fetch_jwks):
        configure_rate_limiter(
            limiter_factory=lambda *_a, **_k: _no_limit
        )  # use local no-op limiter
        app.dependency_overrides[get_session] = override_get_session

        main_config.app.environment = "test"
        main_config.rate_limiter.requests = 1000
        main_config.rate_limiter.window_ms = 60
        main_config.oidc.providers[_ISSUER] = oidc_provider_config

        main_config.jwt.allowed_algorithms = ["HS256"]
        main_config.jwt.audiences = [_AUDIENCE]
        main_config.jwt.claims.user_id = "uid"

        try:
            with TestClient(app) as test_client:
                yield test_client
        finally:
            app.dependency_overrides.clear()
            main_config.rate_limiter.requests = original_requests
            main_config.rate_limiter.window_ms = original_window
            main_config.oidc.providers.pop(_ISSUER)
            main_config.jwt.allowed_algorithms = original_allowed_algorithms
            main_config.jwt.audiences = original_audiences
            main_config.jwt.claims.user_id = original_uid_claim
            main_config.app.environment = original_environment


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
    # Create engine first
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Import models to register them with the metadata
    # This needs to happen after engine creation but before table creation
    from src.app.entities.core.user import UserTable  # noqa: F401
    from src.app.entities.core.user_identity import UserIdentityTable  # noqa: F401

    # Create all tables using the current metadata state
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session
