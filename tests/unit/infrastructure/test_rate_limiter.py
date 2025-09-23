"""Unit tests for rate limiting infrastructure."""

import asyncio

import pytest
from fastapi import HTTPException

from src.api.http.app import _activate_local_rate_limiter, app
from src.api.http.middleware.limiter import (
    DefaultLocalRateLimiter,
    configure_rate_limiter,
    rate_limit,
)
from src.runtime.config import main_config


class TestDefaultLocalRateLimiter:
    """Test the in-memory rate limiter implementation."""

    @pytest.fixture(autouse=True)
    def restore_limiter_state(self):
        """Ensure clean state for each test."""

        def _reset_limiter_state():
            configure_rate_limiter(use_external=False, local_factory=None)
            if hasattr(app.state, "local_rate_limiter"):
                app.state.local_rate_limiter = None

        snapshot = {
            "redis_url": getattr(main_config, "redis_url", None),
        }
        _reset_limiter_state()
        try:
            yield
        finally:
            _reset_limiter_state()
            main_config.redis_url = snapshot["redis_url"]

    @pytest.mark.asyncio
    async def test_allows_requests_within_limit(self, request_factory):
        """Should allow requests that don't exceed the rate limit."""
        limiter = DefaultLocalRateLimiter()
        guard = limiter.dependency(times=2, seconds=10)

        request = request_factory({})
        await guard(request)
        await guard(request)

    @pytest.mark.asyncio
    async def test_blocks_requests_when_limit_exceeded(self, request_factory):
        """Should raise HTTPException when rate limit is exceeded."""
        limiter = DefaultLocalRateLimiter()
        times = 2
        seconds = 5

        guard = limiter.dependency(times=times, seconds=seconds)
        request = request_factory({})

        # First requests should pass
        for _ in range(times):
            await guard(request)

        # Next request should be blocked
        with pytest.raises(HTTPException) as exc_info:
            await guard(request)

        assert exc_info.value.status_code == 429
        assert "too many" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_rate_window_resets_correctly(self, request_factory):
        """Should allow requests again after the time window resets."""
        limiter = DefaultLocalRateLimiter()
        guard = limiter.dependency(times=1, seconds=1)

        request = request_factory({})
        await guard(request)

        # Wait for window to reset
        await asyncio.sleep(1.1)

        # Should be allowed again
        await guard(request)

    @pytest.mark.asyncio
    async def test_rate_limit_persists_until_window_expires(self, request_factory):
        """Should continue blocking requests until the full window expires."""
        limiter = DefaultLocalRateLimiter()
        times = 2
        seconds = 5

        guard = limiter.dependency(times=times, seconds=seconds)
        request = request_factory({})

        # Exceed the limit
        for _ in range(times):
            await guard(request)

        with pytest.raises(HTTPException):
            await guard(request)

        # Wait for partial window reset (should still be blocked)
        await asyncio.sleep(seconds - 1)
        with pytest.raises(HTTPException):
            await guard(request)

        # Wait for full window reset
        await asyncio.sleep(1)
        for _ in range(times):
            await guard(request)

        # Should be blocked again after limit
        with pytest.raises(HTTPException):
            await guard(request)


class TestRateLimitDependency:
    """Test the rate_limit dependency function."""

    @pytest.fixture(autouse=True)
    def restore_limiter_state(self):
        """Ensure clean state for each test."""

        def _reset_limiter_state():
            configure_rate_limiter(use_external=False, local_factory=None)
            if hasattr(app.state, "local_rate_limiter"):
                app.state.local_rate_limiter = None

        snapshot = {
            "redis_url": getattr(main_config, "redis_url", None),
        }
        _reset_limiter_state()
        try:
            yield
        finally:
            _reset_limiter_state()
            main_config.redis_url = snapshot["redis_url"]

    @pytest.mark.asyncio
    async def test_uses_local_limiter_when_redis_unavailable(
        self, request_factory, response_factory
    ):
        """Should fall back to local limiter when Redis is not configured."""
        main_config.redis_url = None
        _activate_local_rate_limiter()

        guard = rate_limit(1, 1)
        request = request_factory({})
        response = response_factory()

        # First request should pass
        await guard(request, response)

        # Second request should be blocked
        with pytest.raises(HTTPException):
            await guard(request, response)
