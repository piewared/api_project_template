"""Session storage interface and implementations.

Provides a unified interface for storing auth sessions and user sessions
with Redis-first approach and in-memory fallback.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class SessionStorage(ABC):
    """Abstract interface for session storage backends."""

    @abstractmethod
    async def set(self, key: str, value: BaseModel, ttl_seconds: int) -> None:
        """Store a session with TTL.

        Args:
            key: Session identifier
            value: Session data (Pydantic model)
            ttl_seconds: Time to live in seconds
        """
        pass

    @abstractmethod
    async def get(self, key: str, model_class: type[T]) -> T | None:
        """Retrieve a session.

        Args:
            key: Session identifier
            model_class: Pydantic model class to deserialize to

        Returns:
            Session data or None if not found/expired
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a session.

        Args:
            key: Session identifier
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if session exists.

        Args:
            key: Session identifier

        Returns:
            True if session exists and not expired
        """
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """Clean up expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        pass

    @abstractmethod
    async def list_keys(self, pattern: str) -> list[str]:
        """List keys matching a pattern.

        Args:
            pattern: Key pattern (e.g., "auth:*", "user:*")

        Returns:
            List of matching keys
        """
        pass

    @abstractmethod
    async def list_sessions(self, pattern: str, model_class: type[T]) -> list[T]:
        """List sessions matching a pattern.

        Args:
            pattern: Key pattern (e.g., "auth:*", "user:*")
            model_class: Pydantic model class to deserialize to

        Returns:
            List of valid, non-expired sessions
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if storage backend is available.

        Returns:
            True if storage is healthy and available
        """
        pass


class InMemorySessionStorage(SessionStorage):
    """In-memory session storage with TTL support."""

    def __init__(self):
        self._data: dict[str, dict[str, Any]] = {}

    async def set(self, key: str, value: BaseModel, ttl_seconds: int) -> None:
        """Store session in memory with expiration."""
        expires_at = time.time() + ttl_seconds
        self._data[key] = {
            "data": json.loads(value.model_dump_json()),
            "expires_at": expires_at,
        }

    async def get(self, key: str, model_class: type[T]) -> T | None:
        """Retrieve session from memory if not expired."""
        if key not in self._data:
            return None

        entry = self._data[key]
        if time.time() > entry["expires_at"]:
            del self._data[key]
            return None

        try:
            return model_class.model_validate(entry["data"])
        except Exception:
            # Clean up corrupted data
            del self._data[key]
            return None

    async def delete(self, key: str) -> None:
        """Delete session from memory."""
        self._data.pop(key, None)

    async def exists(self, key: str) -> bool:
        """Check if session exists and is not expired."""
        if key not in self._data:
            return False

        entry = self._data[key]
        if time.time() > entry["expires_at"]:
            del self._data[key]
            return False

        return True

    async def cleanup_expired(self) -> int:
        """Remove expired sessions from memory."""
        now = time.time()
        expired_keys = [
            key for key, entry in self._data.items() if now > entry["expires_at"]
        ]

        for key in expired_keys:
            del self._data[key]

        return len(expired_keys)

    async def list_keys(self, pattern: str) -> list[str]:
        """List keys matching a pattern using fnmatch."""
        import fnmatch

        matching_keys = []

        for key in self._data.keys():
            if fnmatch.fnmatch(key, pattern):
                # Check if session is still valid (not expired)
                entry = self._data[key]
                if time.time() <= entry["expires_at"]:
                    matching_keys.append(key)
                else:
                    # Clean up expired session
                    del self._data[key]

        return matching_keys

    async def list_sessions(self, pattern: str, model_class: type[T]) -> list[T]:
        """List sessions matching a pattern."""
        sessions = []
        keys = await self.list_keys(pattern)

        for key in keys:
            try:
                session = await self.get(key, model_class)
                if session:
                    sessions.append(session)
            except Exception:
                # Skip corrupted sessions
                continue

        return sessions

    def is_available(self) -> bool:
        """In-memory storage is always available."""
        return True


class RedisSessionStorage(SessionStorage):
    """Redis-based session storage with serialization."""

    def __init__(self, redis_client):
        self._redis = redis_client
        self._available = True

    async def set(self, key: str, value: BaseModel, ttl_seconds: int) -> None:
        """Store session in Redis with TTL."""
        try:
            data = value.model_dump_json()
            await self._redis.setex(key, ttl_seconds, data)
            self._available = True
        except Exception as e:
            self._available = False
            raise RuntimeError(f"Redis set failed: {e}") from e

    async def get(self, key: str, model_class: type[T]) -> T | None:
        """Retrieve session from Redis."""
        try:
            data = await self._redis.get(key)
            if data is None:
                return None

            # Decode if bytes
            if isinstance(data, bytes):
                data = data.decode("utf-8")

            return model_class.model_validate_json(data)
        except Exception as e:
            self._available = False
            raise RuntimeError(f"Redis get failed: {e}") from e

    async def delete(self, key: str) -> None:
        """Delete session from Redis."""
        try:
            await self._redis.delete(key)
            self._available = True
        except Exception as e:
            self._available = False
            raise RuntimeError(f"Redis delete failed: {e}") from e

    async def exists(self, key: str) -> bool:
        """Check if session exists in Redis."""
        try:
            result = await self._redis.exists(key)
            self._available = True
            return bool(result)
        except Exception as e:
            self._available = False
            raise RuntimeError(f"Redis exists failed: {e}") from e

    async def cleanup_expired(self) -> int:
        """Redis handles expiration automatically."""
        return 0

    async def list_keys(self, pattern: str) -> list[str]:
        """List keys matching a pattern using Redis SCAN."""
        try:
            keys = []
            cursor = 0

            while True:
                cursor, batch = await self._redis.scan(cursor, match=pattern, count=100)
                keys.extend(batch)

                if cursor == 0:
                    break

            self._available = True
            return keys
        except Exception as e:
            self._available = False
            raise RuntimeError(f"Redis scan failed: {e}") from e

    async def list_sessions(self, pattern: str, model_class: type[T]) -> list[T]:
        """List sessions matching a pattern."""
        try:
            sessions = []
            keys = await self.list_keys(pattern)

            for key in keys:
                try:
                    session = await self.get(key, model_class)
                    if session:
                        sessions.append(session)
                except Exception:
                    # Skip corrupted/invalid sessions
                    continue

            return sessions
        except Exception as e:
            self._available = False
            raise RuntimeError(f"Redis list sessions failed: {e}") from e

    def is_available(self) -> bool:
        """Check if Redis connection is healthy."""
        return self._available

    async def ping(self) -> bool:
        """Test Redis connection health."""
        try:
            await self._redis.ping()
            self._available = True
            return True
        except Exception:
            self._available = False
            return False


# Global storage instance
_storage: SessionStorage | None = None


async def _detect_redis_availability() -> SessionStorage:
    """Attempt to create Redis storage, fall back to in-memory."""
    try:
        # Try to import and connect to Redis
        import redis.asyncio as redis

        from src.app.runtime.context import get_config

        config = get_config()
        if not config.redis.enabled or not config.redis.url:
            raise RuntimeError("Redis not configured")

        # Create Redis client
        redis_client = redis.from_url(
            config.redis.url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )

        # Test connection
        redis_storage = RedisSessionStorage(redis_client)
        if await redis_storage.ping():
            print("✅ Session storage: Redis connected")
            return redis_storage
        else:
            raise RuntimeError("Redis ping failed")

    except Exception as e:
        print(f"⚠️  Redis unavailable ({e}), using in-memory session storage")
        return InMemorySessionStorage()


async def get_session_storage() -> SessionStorage:
    """Get the configured session storage instance."""
    global _storage

    if _storage is None:
        _storage = await _detect_redis_availability()

    return _storage


def _reset_storage() -> None:
    """Reset storage instance (for testing)."""
    global _storage
    _storage = None
