"""Comprehensive tests for session storage implementations."""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from src.app.core.storage.session_storage import (
    InMemorySessionStorage,
    RedisSessionStorage,
    _detect_redis_availability,
    _reset_storage,
    get_session_storage,
)


class TestSession(BaseModel):
    """Test session model for storage tests."""
    id: str
    data: str
    created_at: int


class TestInMemorySessionStorage:
    """Test in-memory session storage implementation."""

    def setup_method(self):
        """Set up fresh storage for each test."""
        self.storage = InMemorySessionStorage()

    @pytest.mark.asyncio
    async def test_set_and_get_session(self):
        """Test storing and retrieving a session."""
        session = TestSession(id="test-123", data="test-data", created_at=int(time.time()))
        
        await self.storage.set("session-1", session, 60)
        retrieved = await self.storage.get("session-1", TestSession)
        
        assert retrieved is not None
        assert retrieved.id == "test-123"
        assert retrieved.data == "test-data"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self):
        """Test getting a session that doesn't exist."""
        result = await self.storage.get("nonexistent", TestSession)
        assert result is None

    @pytest.mark.asyncio
    async def test_session_expiration(self):
        """Test that sessions expire after TTL."""
        session = TestSession(id="expire-test", data="data", created_at=int(time.time()))
        
        # Set with very short TTL
        await self.storage.set("expire-session", session, 1)
        
        # Should exist immediately
        result = await self.storage.get("expire-session", TestSession)
        assert result is not None
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired now
        result = await self.storage.get("expire-session", TestSession)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_session(self):
        """Test deleting a session."""
        session = TestSession(id="delete-test", data="data", created_at=int(time.time()))
        
        await self.storage.set("delete-session", session, 60)
        assert await self.storage.exists("delete-session")
        
        await self.storage.delete("delete-session")
        assert not await self.storage.exists("delete-session")

    @pytest.mark.asyncio
    async def test_exists(self):
        """Test session existence checking."""
        session = TestSession(id="exists-test", data="data", created_at=int(time.time()))
        
        # Should not exist initially
        assert not await self.storage.exists("exists-session")
        
        # Should exist after storing
        await self.storage.set("exists-session", session, 60)
        assert await self.storage.exists("exists-session")
        
        # Should not exist after expiration
        await self.storage.set("expire-session", session, 1)
        await asyncio.sleep(1.1)
        assert not await self.storage.exists("expire-session")

    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        """Test cleanup of expired sessions."""
        session1 = TestSession(id="session1", data="data1", created_at=int(time.time()))
        session2 = TestSession(id="session2", data="data2", created_at=int(time.time()))
        
        # Store one session with short TTL, one with long TTL
        await self.storage.set("short-session", session1, 1)
        await self.storage.set("long-session", session2, 60)
        
        # Wait for first to expire
        await asyncio.sleep(1.1)
        
        # Cleanup should remove 1 expired session
        cleaned = await self.storage.cleanup_expired()
        assert cleaned == 1
        
        # Only long session should remain
        assert not await self.storage.exists("short-session")
        assert await self.storage.exists("long-session")

    def test_is_available(self):
        """Test availability check."""
        assert self.storage.is_available() is True

    @pytest.mark.asyncio
    async def test_corrupted_data_handling(self):
        """Test handling of corrupted session data."""
        # Manually corrupt data
        self.storage._data["corrupted"] = {
            'data': {'invalid': 'structure'},  # Missing required fields
            'expires_at': time.time() + 60
        }
        
        # Should return None and clean up corrupted data
        result = await self.storage.get("corrupted", TestSession)
        assert result is None
        assert "corrupted" not in self.storage._data


class TestRedisSessionStorage:
    """Test Redis session storage implementation."""

    def setup_method(self):
        """Set up mock Redis client for each test."""
        self.mock_redis = AsyncMock()
        self.storage = RedisSessionStorage(self.mock_redis)

    @pytest.mark.asyncio
    async def test_set_session(self):
        """Test storing a session in Redis."""
        session = TestSession(id="redis-test", data="test-data", created_at=int(time.time()))
        
        await self.storage.set("redis-session", session, 60)
        
        # Verify Redis setex was called with correct parameters
        self.mock_redis.setex.assert_called_once()
        args = self.mock_redis.setex.call_args
        assert args[0][0] == "redis-session"
        assert args[0][1] == 60
        
        # Verify serialized data
        serialized_data = args[0][2]
        deserialized = json.loads(serialized_data)
        assert deserialized["id"] == "redis-test"

    @pytest.mark.asyncio
    async def test_get_session(self):
        """Test retrieving a session from Redis."""
        session_data = TestSession(id="get-test", data="test-data", created_at=int(time.time()))
        self.mock_redis.get.return_value = session_data.model_dump_json()
        
        result = await self.storage.get("get-session", TestSession)
        
        assert result is not None
        assert result.id == "get-test"
        assert result.data == "test-data"
        self.mock_redis.get.assert_called_once_with("get-session")

    @pytest.mark.asyncio
    async def test_get_session_bytes(self):
        """Test retrieving a session when Redis returns bytes."""
        session_data = TestSession(id="bytes-test", data="test-data", created_at=int(time.time()))
        self.mock_redis.get.return_value = session_data.model_dump_json().encode('utf-8')
        
        result = await self.storage.get("bytes-session", TestSession)
        
        assert result is not None
        assert result.id == "bytes-test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self):
        """Test getting a session that doesn't exist in Redis."""
        self.mock_redis.get.return_value = None
        
        result = await self.storage.get("nonexistent", TestSession)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_session(self):
        """Test deleting a session from Redis."""
        await self.storage.delete("delete-session")
        
        self.mock_redis.delete.assert_called_once_with("delete-session")

    @pytest.mark.asyncio
    async def test_exists(self):
        """Test checking session existence in Redis."""
        self.mock_redis.exists.return_value = 1
        
        result = await self.storage.exists("exists-session")
        assert result is True
        
        self.mock_redis.exists.assert_called_once_with("exists-session")

    @pytest.mark.asyncio
    async def test_exists_false(self):
        """Test checking session existence when not in Redis."""
        self.mock_redis.exists.return_value = 0
        
        result = await self.storage.exists("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_expired_noop(self):
        """Test cleanup (Redis handles expiration automatically)."""
        result = await self.storage.cleanup_expired()
        assert result == 0

    @pytest.mark.asyncio
    async def test_ping_success(self):
        """Test successful Redis ping."""
        self.mock_redis.ping.return_value = True
        
        result = await self.storage.ping()
        assert result is True
        assert self.storage.is_available() is True

    @pytest.mark.asyncio
    async def test_ping_failure(self):
        """Test failed Redis ping."""
        self.mock_redis.ping.side_effect = Exception("Connection failed")
        
        result = await self.storage.ping()
        assert result is False
        assert self.storage.is_available() is False

    @pytest.mark.asyncio
    async def test_redis_operation_failure(self):
        """Test handling of Redis operation failures."""
        self.mock_redis.setex.side_effect = Exception("Redis error")
        
        session = TestSession(id="fail-test", data="data", created_at=int(time.time()))
        
        with pytest.raises(RuntimeError, match="Redis set failed"):
            await self.storage.set("fail-session", session, 60)
        
        assert self.storage.is_available() is False

    def test_is_available_initial_state(self):
        """Test initial availability state."""
        assert self.storage.is_available() is True


class TestStorageDetection:
    """Test Redis detection and fallback logic."""

    def setup_method(self):
        """Reset storage state for each test."""
        _reset_storage()

    @pytest.mark.asyncio
    async def test_redis_detection_success(self):
        """Test successful Redis detection."""
        mock_redis_client = AsyncMock()
        mock_redis_storage = AsyncMock(spec=RedisSessionStorage)
        mock_redis_storage.ping.return_value = True
        
        with patch('redis.asyncio.from_url', return_value=mock_redis_client), \
             patch.object(RedisSessionStorage, '__new__', return_value=mock_redis_storage), \
             patch('src.app.runtime.context.get_config') as mock_config:
            
            # Configure mock config
            mock_config.return_value.redis.enabled = True
            mock_config.return_value.redis.url = "redis://localhost:6379"
            
            storage = await _detect_redis_availability()
            
            assert storage is mock_redis_storage

    @pytest.mark.asyncio
    async def test_redis_detection_disabled(self):
        """Test fallback when Redis is disabled in config."""
        with patch('src.app.runtime.context.get_config') as mock_config:
            mock_config.return_value.redis.enabled = False
            
            storage = await _detect_redis_availability()
            
            assert isinstance(storage, InMemorySessionStorage)

    @pytest.mark.asyncio
    async def test_redis_detection_no_url(self):
        """Test fallback when Redis URL is not configured."""
        with patch('src.app.runtime.context.get_config') as mock_config:
            mock_config.return_value.redis.enabled = True
            mock_config.return_value.redis.url = ""
            
            storage = await _detect_redis_availability()
            
            assert isinstance(storage, InMemorySessionStorage)

    @pytest.mark.asyncio
    async def test_redis_detection_connection_failure(self):
        """Test fallback when Redis connection fails."""
        with patch('redis.asyncio.from_url', side_effect=Exception("Connection failed")), \
             patch('src.app.runtime.context.get_config') as mock_config:
            
            mock_config.return_value.redis.enabled = True
            mock_config.return_value.redis.url = "redis://localhost:6379"
            
            storage = await _detect_redis_availability()
            
            assert isinstance(storage, InMemorySessionStorage)

    @pytest.mark.asyncio
    async def test_redis_detection_ping_failure(self):
        """Test fallback when Redis ping fails."""
        mock_redis_client = AsyncMock()
        
        with patch('redis.asyncio.from_url', return_value=mock_redis_client), \
             patch('src.app.runtime.context.get_config') as mock_config:
            
            mock_config.return_value.redis.enabled = True
            mock_config.return_value.redis.url = "redis://localhost:6379"
            
            # Mock ping failure
            with patch.object(RedisSessionStorage, 'ping', return_value=False):
                storage = await _detect_redis_availability()
                
                assert isinstance(storage, InMemorySessionStorage)

    @pytest.mark.asyncio
    async def test_get_session_storage_singleton(self):
        """Test that get_session_storage returns the same instance."""
        with patch('src.app.core.storage.session_storage._detect_redis_availability') as mock_detect:
            mock_storage = InMemorySessionStorage()
            mock_detect.return_value = mock_storage
            
            storage1 = await get_session_storage()
            storage2 = await get_session_storage()
            
            assert storage1 is storage2
            mock_detect.assert_called_once()


class TestStorageIntegration:
    """Integration tests for storage layer."""

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent storage operations."""
        storage = InMemorySessionStorage()
        
        sessions = [
            TestSession(id=f"session-{i}", data=f"data-{i}", created_at=int(time.time()))
            for i in range(10)
        ]
        
        # Store sessions concurrently
        await asyncio.gather(*[
            storage.set(f"concurrent-{i}", session, 60)
            for i, session in enumerate(sessions)
        ])
        
        # Retrieve sessions concurrently
        results = await asyncio.gather(*[
            storage.get(f"concurrent-{i}", TestSession)
            for i in range(10)
        ])
        
        # Verify all sessions were stored and retrieved correctly
        for i, result in enumerate(results):
            assert result is not None
            assert result.id == f"session-{i}"
            assert result.data == f"data-{i}"

    @pytest.mark.asyncio
    async def test_large_session_data(self):
        """Test storing and retrieving large session data."""
        large_data = "x" * 10000  # 10KB of data
        session = TestSession(id="large", data=large_data, created_at=int(time.time()))
        
        storage = InMemorySessionStorage()
        
        await storage.set("large-session", session, 60)
        result = await storage.get("large-session", TestSession)
        
        assert result is not None
        assert result.data == large_data
        assert len(result.data) == 10000