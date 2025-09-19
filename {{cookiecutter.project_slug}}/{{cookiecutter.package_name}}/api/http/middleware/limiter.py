"""Rate limiting helpers used by the HTTP layer."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
import time
from typing import Any, Awaitable, Callable, DefaultDict, Deque, Optional

from fastapi import HTTPException, Request, Response
from loguru import logger

from {{cookiecutter.package_name}}.runtime.settings import settings

try:
    from fastapi_limiter.depends import RateLimiter
    _has_external = True
except Exception:  # pragma: no cover - optional dependency
    RateLimiter = None  # type: ignore
    _has_external = False


LocalLimiterFactory = Callable[[int, int], Callable[[Request], Awaitable[Any]]]

_use_external_limiter = _has_external
_local_limiter_factory: Optional[LocalLimiterFactory] = None


class DefaultLocalRateLimiter:
    """Simple in-memory limiter used when Redis isn't available."""

    def __init__(self) -> None:
        self._hits: DefaultDict[str, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    def dependency(
        self,
        times: int,
        seconds: int,
        *,
        per_endpoint: bool = True,
        per_method: bool = False,
    ) -> Callable[[Request], Awaitable[None]]:
        async def _inner(request: Request) -> None:
            key = self._make_key(
                request,
                per_endpoint=per_endpoint,
                per_method=per_method,
            )
            await self._throttle(key, times, seconds)

        return _inner

    def _make_key(self, request: Request, *, per_endpoint: bool, per_method: bool) -> str:
        uid = getattr(request.state, "uid", None)
        if uid is not None:
            ident = f"user:{uid}"
        else:
            client_host = request.client.host if request.client else "anonymous"
            ident = f"ip:{client_host}"

        path_piece = ""
        if per_endpoint:
            route = request.scope.get("route")
            template = getattr(route, "path", None)
            path_piece = (template or request.url.path).rstrip("/")

        method_piece = request.method if per_method else ""

        parts = [ident]
        if method_piece:
            parts.append(method_piece)
        if path_piece:
            parts.append(path_piece)
        return ":".join(parts)

    async def _throttle(self, key: str, times: int, seconds: int) -> None:
        now = time.monotonic()
        window_start = now - seconds
        async with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= window_start:
                hits.popleft()
            if len(hits) >= times:
                retry_after = max(0, int(seconds - (now - hits[0])))
                raise HTTPException(
                    status_code=429,
                    detail="Too Many Requests",
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)


def configure_rate_limiter(
    *,
    use_external: bool,
    local_factory: Optional[LocalLimiterFactory] = None,
) -> None:
    """Configure which limiter implementation should be used."""

    global _use_external_limiter, _local_limiter_factory

    if use_external and not _has_external:
        raise RuntimeError("Cannot enable external rate limiter; dependencies missing")
    if use_external and local_factory is not None:
        raise ValueError("Cannot use both external and local rate limiter")

    _use_external_limiter = use_external and _has_external
    _local_limiter_factory = local_factory or (_local_limiter_factory or DefaultLocalRateLimiter().dependency)


def rate_limit(times: int | None = None, seconds: int | None = None) -> Callable[[Request, Response], Awaitable[Any]]:
    """Return a dependency enforcing request quotas."""

    async def dependency(request: Request, response: Response) -> Any:
        effective_times = times if times is not None else (settings.rate_limit_requests or 10)
        effective_seconds = seconds if seconds is not None else (settings.rate_limit_window or 60)

        if _use_external_limiter and RateLimiter is not None:
            limiter = RateLimiter(times=effective_times, seconds=effective_seconds)
            return await limiter(request, response)

        if _local_limiter_factory is not None:
            guard = _local_limiter_factory(effective_times, effective_seconds)
            return await guard(request)

        return None

    return dependency


async def close_rate_limiter() -> None:
    if _use_external_limiter and RateLimiter is not None:
        try:
            from fastapi_limiter import FastAPILimiter

            if hasattr(FastAPILimiter, "close"):
                await FastAPILimiter.close()
        except Exception:  # pragma: no cover - best effort cleanup
            logger.exception("Error closing FastAPILimiter")
