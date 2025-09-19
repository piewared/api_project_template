from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Generator

from fastapi import Response
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from starlette.requests import Request

from {{cookiecutter.package_name}}.core.services import jwt_service
from {{cookiecutter.package_name}}.runtime.settings import settings
from {{cookiecutter.package_name}}.api.http.app import app
from {{cookiecutter.package_name}}.api.http.deps import get_session
from {{cookiecutter.package_name}}.api.http.middleware.limiter import configure_rate_limiter
from tests.utils import oct_jwk
# Ensure models are registered with SQLModel metadata before creating tables
from {{cookiecutter.package_name}}.core.rows import user_row, user_identity_row  # noqa: F401


_HS_KEY = b"router-secret-key"
_ISSUER = "https://issuer.test"
_AUDIENCE = "api://router"
_KID = "router-key"


@pytest.fixture(autouse=True)
def clear_jwks_cache() -> Generator[None, None, None]:
    jwt_service._JWKS_CACHE.clear()
    yield
    jwt_service._JWKS_CACHE.clear()


@pytest.fixture(autouse=True)
def snapshot_config() -> Generator[None, None, None]:
    tracked_attrs = (
        "issuer_jwks_map",
        "allowed_algorithms",
        "audiences",
        "clock_skew",
        "uid_claim",
        "redis_url",
    )
    snapshot = {attr: deepcopy(getattr(settings, attr)) for attr in tracked_attrs}
    try:
        yield
    finally:
        for attr, value in snapshot.items():
            setattr(settings, attr, value)


@pytest.fixture
def request_factory() -> Callable[[Dict[str, str]], Request]:
    def _make_request(headers: Dict[str, str]) -> Request:
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
def client(session: Session):
    """Yield a TestClient wired to the shared SQLModel session and test-friendly config."""

    def override_get_session():
        yield session

    async def _no_limit(request: Request) -> None:
        return None

    jwks_data = {"keys": [oct_jwk(_HS_KEY, _KID)]}

    # Store original values to restore later
    original_requests = settings.rate_limit_requests
    original_window = settings.rate_limit_window
    original_jwks_map = dict(settings.issuer_jwks_map)
    original_allowed_algorithms = list(settings.allowed_algorithms)
    original_audiences = list(settings.audiences)
    original_uid_claim = settings.uid_claim
    original_environment = settings.environment

    async def fake_fetch_jwks(issuer: str):
        return jwks_data

    # Mock the fetch_jwks function
    import unittest.mock
    with unittest.mock.patch.object(jwt_service, 'fetch_jwks', fake_fetch_jwks):
        configure_rate_limiter(
            use_external=False, local_factory=lambda *_a, **_k: _no_limit
        )
        app.dependency_overrides[get_session] = override_get_session

        settings.environment = "test"
        settings.rate_limit_requests = 1000
        settings.rate_limit_window = 60
        settings.issuer_jwks_map = {_ISSUER: "https://issuer.test/.well-known/jwks.json"}
        settings.allowed_algorithms = ["HS256"]
        settings.audiences = [_AUDIENCE]
        settings.uid_claim = "uid"

        try:
            with TestClient(app) as test_client:
                yield test_client
        finally:
            app.dependency_overrides.clear()
            settings.rate_limit_requests = original_requests
            settings.rate_limit_window = original_window
            settings.issuer_jwks_map = original_jwks_map
            settings.allowed_algorithms = original_allowed_algorithms
            settings.audiences = original_audiences
            settings.uid_claim = original_uid_claim
            settings.environment = original_environment


@pytest.fixture(scope="session")
def persistent_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
