from __future__ import annotations


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:  # pragma: no cover - defensive helper
        return None

    def json(self):
        return self._payload


class DummyAsyncClient:
    def __init__(self, expected_url: str, payload, *args, **kwargs):
        self._expected_url = expected_url
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str):
        assert url == self._expected_url
        return DummyResponse(self._payload)


class FailingAsyncClient(DummyAsyncClient):
    async def __aenter__(self):  # pragma: no cover - defensive helper
        raise AssertionError("Should not fetch when JWKS is cached")
