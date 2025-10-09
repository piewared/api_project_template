from abc import ABC, abstractmethod
from typing import Any

from cachetools import TTLCache
from fastapi import HTTPException
from loguru import logger

from src.app.runtime.config.config_data import OIDCProviderConfig


class JWKSCache(ABC):
    @abstractmethod
    def get_jwks(self, issuer_url: str) -> dict[str, Any]:
        """
        Get JWKS for the given issuer URL from cache.
        Args:
            issuer_url: The OIDC issuer URL

        Returns:
            JWKS dictionary
        """
        raise NotImplementedError

    @abstractmethod
    def set_jwks(self, issuer_url: str, jwks: dict[str, Any]) -> None:
        """
        Set JWKS for the given issuer URL in cache.

        Args:
            issuer_url: The OIDC issuer URL
            jwks: The JWKS dictionary to cache
        """
        raise NotImplementedError

    @abstractmethod
    def clear_jwks_cache(self) -> None:
        """Clear the JWKS cache."""
        raise NotImplementedError


class JWKSCacheInMemory(JWKSCache):
    _JWKS_CACHE: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=10, ttl=3600)

    def __init__(self) -> None:
        pass

    def get_jwks(self, issuer_url: str) -> dict[str, Any]:
        """Get JWKS for the given issuer URL, using cache if available.

        Args:
            issuer_url: The OIDC issuer URL

        Returns:
            JWKS dictionary
        """
        return self._JWKS_CACHE.get(issuer_url, {})

    def set_jwks(self, issuer_url: str, jwks: dict[str, Any]) -> None:
        """Set JWKS for the given issuer URL in the cache.

        Args:
            issuer_url: The OIDC issuer URL
            jwks: The JWKS dictionary to cache
        """
        self._JWKS_CACHE[issuer_url] = jwks

    def clear_jwks_cache(self) -> None:
        """Clear the JWKS cache."""
        self._JWKS_CACHE.clear()


class JwksService:
    def __init__(self, cache: JWKSCache) -> None:
        self._cache = cache

    async def fetch_jwks(self, issuer: OIDCProviderConfig) -> dict[str, Any]:
        jwks_url = issuer.jwks_uri

        if not jwks_url:
            raise HTTPException(
                status_code=401, detail="Issuer has no JWKS URI configured"
            )

        jwks = self._cache.get_jwks(jwks_url)
        if jwks:
            return jwks

        import httpx  # local import to avoid forcing httpx at import time

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(jwks_url)
                resp.raise_for_status()
                jwks = resp.json()
                self._cache.set_jwks(jwks_url, jwks)
                return jwks
        except Exception as exc:
            raise HTTPException(
                status_code=500, detail=f"Failed to fetch JWKS: {exc}"
            ) from exc
