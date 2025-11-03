# Redis Usage Guide

This guide demonstrates how to use Redis in your FastAPI application through dependency injection, session storage, caching, and direct operations.

## Table of Contents

- [Quick Start](#quick-start)
- [RedisService Integration](#redisservice-integration)
- [Session Storage](#session-storage)
- [User Session Management](#user-session-management)
- [Auth Session Management](#auth-session-management)
- [Caching Patterns](#caching-patterns)
- [Direct Redis Operations](#direct-redis-operations)
- [Error Handling](#error-handling)
- [Testing](#testing)
- [Best Practices](#best-practices)

## Quick Start

### 1. Start Redis (Development)

```bash
# Start via dev environment
uv run cli dev start-env

# Or directly with Docker Compose
docker-compose -f docker-compose.dev.yml up redis -d

# Verify Redis is running
docker exec -it api-template-redis-dev redis-cli ping
# Expected: PONG
```

### 2. Use in FastAPI Endpoint

```python
from fastapi import APIRouter, Depends
from app.core.services.redis_service import RedisService, get_redis_service

router = APIRouter()

@router.get("/redis-health")
async def check_redis(
    redis_service: RedisService = Depends(get_redis_service)
):
    """Check if Redis is healthy."""
    is_healthy = await redis_service.health_check()
    
    if is_healthy:
        info = await redis_service.get_info()
        return {
            "status": "healthy",
            "version": info.get("redis_version"),
            "uptime_seconds": info.get("uptime_in_seconds"),
            "connected_clients": info.get("connected_clients")
        }
    else:
        return {"status": "unhealthy"}
```

### 3. Store and Retrieve Data

```python
@router.post("/cache-value")
async def cache_value(
    key: str,
    value: str,
    ttl_seconds: int = 3600,
    redis_service: RedisService = Depends(get_redis_service)
):
    """Cache a value with expiration."""
    redis_client = await redis_service.get_client()
    await redis_client.set(key, value, ex=ttl_seconds)
    return {"message": f"Cached {key} for {ttl_seconds} seconds"}

@router.get("/get-cached-value")
async def get_cached_value(
    key: str,
    redis_service: RedisService = Depends(get_redis_service)
):
    """Retrieve cached value."""
    redis_client = await redis_service.get_client()
    value = await redis_client.get(key)
    
    if value is None:
        return {"error": "Key not found"}
    
    return {"key": key, "value": value}
```

## RedisService Integration

### Dependency Injection

The `RedisService` is a singleton service managed by FastAPI's dependency injection:

```python
from fastapi import Depends
from app.core.services.redis_service import RedisService, get_redis_service

# Inject into endpoint
@router.get("/example")
async def example_endpoint(
    redis_service: RedisService = Depends(get_redis_service)
):
    # Use redis_service here
    pass
```

### Available Methods

#### `get_client()` - Get Redis Client

```python
redis_client = await redis_service.get_client()

# Returns: redis.asyncio.Redis instance
# Use for direct Redis operations
```

#### `health_check()` - Check Redis Health

```python
is_healthy = await redis_service.health_check()

# Returns: bool (True if PING succeeds)
# Use for health check endpoints
```

#### `test_operation()` - Full Operation Test

```python
is_working = await redis_service.test_operation()

# Returns: bool (True if SET, GET, DEL all succeed)
# Use for comprehensive health checks
```

#### `get_info()` - Get Redis Server Info

```python
info = await redis_service.get_info()

# Returns: dict with server statistics
# Example: {
#   "redis_version": "7.0.5",
#   "uptime_in_seconds": 3600,
#   "connected_clients": 5,
#   "used_memory_human": "2.5M",
#   "total_commands_processed": 12345
# }
```

#### `close()` - Graceful Shutdown

```python
await redis_service.close()

# Closes all connections in pool
# Called automatically on app shutdown
```

### Complete Example: Health Check Endpoint

```python
from fastapi import APIRouter, Depends, HTTPException
from app.core.services.redis_service import RedisService, get_redis_service

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/redis")
async def redis_health(
    redis_service: RedisService = Depends(get_redis_service)
):
    """
    Comprehensive Redis health check.
    
    Checks:
    - Basic connectivity (PING)
    - Read/write operations (SET, GET, DEL)
    - Server statistics
    """
    # Basic health check
    if not await redis_service.health_check():
        raise HTTPException(
            status_code=503,
            detail="Redis is not responding to PING"
        )
    
    # Full operation test
    if not await redis_service.test_operation():
        raise HTTPException(
            status_code=503,
            detail="Redis operations are failing"
        )
    
    # Get server info
    info = await redis_service.get_info()
    
    return {
        "status": "healthy",
        "redis": {
            "version": info.get("redis_version"),
            "uptime_seconds": info.get("uptime_in_seconds"),
            "connected_clients": info.get("connected_clients"),
            "used_memory": info.get("used_memory_human"),
            "total_commands": info.get("total_commands_processed")
        }
    }
```

## Session Storage

The `SessionStorage` abstraction provides a consistent interface for storing sessions in Redis or in-memory.

### Get Session Storage

```python
from app.core.storage.session_storage import get_session_storage

# In FastAPI dependency
session_storage = await get_session_storage()

# Auto-selects:
# - RedisSessionStorage if Redis available
# - InMemorySessionStorage if Redis unavailable
```

### SessionStorage Methods

#### `set()` - Store Session

```python
from app.core.models.auth_session import AuthSession

# Create session data
auth_session = AuthSession(
    provider="google",
    state="random-csrf-token",
    nonce="random-nonce",
    created_at=datetime.now(UTC)
)

# Store with TTL
await session_storage.set(
    key="auth:abc123",
    value=auth_session,
    ttl_seconds=600  # 10 minutes
)
```

#### `get()` - Retrieve Session

```python
# Retrieve and deserialize
auth_session = await session_storage.get(
    key="auth:abc123",
    model_class=AuthSession
)

if auth_session is None:
    # Session not found or expired
    raise HTTPException(status_code=401, detail="Session expired")

# Use session data
print(f"Provider: {auth_session.provider}")
```

#### `delete()` - Remove Session

```python
# Delete session (e.g., on logout)
await session_storage.delete(key="user:abc123")

# Session is immediately removed
```

#### `exists()` - Check Session Existence

```python
# Check if session exists
if await session_storage.exists(key="user:abc123"):
    print("Session is active")
else:
    print("Session not found or expired")
```

#### `list_keys()` - Find Keys by Pattern

```python
# Find all user sessions
user_session_keys = await session_storage.list_keys(pattern="user:*")

# Example result: ["user:abc123", "user:xyz789"]
```

#### `list_sessions()` - List All Sessions

```python
from app.core.models.user_session import UserSession

# Get all active user sessions
sessions = await session_storage.list_sessions(
    pattern="user:*",
    model_class=UserSession
)

# Returns: List[UserSession]
for session in sessions:
    print(f"User {session.user_id}: expires at {session.expires_at}")
```

#### `cleanup_expired()` - Manual Cleanup

```python
# Remove expired sessions (in-memory only)
removed_count = await session_storage.cleanup_expired()

# Note: Redis auto-expires via TTL, so this is a no-op
print(f"Removed {removed_count} expired sessions")
```

### Complete Example: Auth Session Flow

```python
from fastapi import APIRouter, Depends, Response, HTTPException
from app.core.storage.session_storage import SessionStorage, get_session_storage
from app.core.models.auth_session import AuthSession
import secrets
from datetime import datetime, UTC

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.get("/login")
async def initiate_login(
    provider: str,
    session_storage: SessionStorage = Depends(get_session_storage)
):
    """
    Step 1: Initiate OAuth login flow.
    
    Creates temporary auth session to track OAuth state.
    """
    # Generate CSRF protection tokens
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    auth_session_id = secrets.token_urlsafe(32)
    
    # Create auth session
    auth_session = AuthSession(
        provider=provider,
        state=state,
        nonce=nonce,
        created_at=datetime.now(UTC)
    )
    
    # Store with 10 minute TTL
    await session_storage.set(
        key=f"auth:{auth_session_id}",
        value=auth_session,
        ttl_seconds=600
    )
    
    # Build OAuth authorization URL
    auth_url = f"https://provider.com/oauth/authorize?state={state}&nonce={nonce}"
    
    return {
        "auth_url": auth_url,
        "auth_session_id": auth_session_id
    }

@router.get("/callback")
async def handle_callback(
    auth_session_id: str,
    state: str,
    code: str,
    session_storage: SessionStorage = Depends(get_session_storage)
):
    """
    Step 2: Handle OAuth callback.
    
    Validates auth session and exchanges code for tokens.
    """
    # Retrieve auth session
    auth_session = await session_storage.get(
        key=f"auth:{auth_session_id}",
        model_class=AuthSession
    )
    
    if auth_session is None:
        raise HTTPException(
            status_code=401,
            detail="Auth session expired or invalid"
        )
    
    # Verify CSRF token
    if auth_session.state != state:
        raise HTTPException(
            status_code=401,
            detail="Invalid state parameter (CSRF attack?)"
        )
    
    # Delete auth session (one-time use)
    await session_storage.delete(key=f"auth:{auth_session_id}")
    
    # Exchange code for tokens (implementation omitted)
    # access_token, refresh_token = await exchange_code(code)
    
    # Create user session (see next section)
    # user_session_id = await create_user_session(...)
    
    return {"message": "Login successful"}
```

## User Session Management

### UserSessionService

The `UserSessionService` manages authenticated user sessions with token storage and rotation.

```python
from app.core.services.session.user_session import UserSessionService
from app.core.storage.session_storage import get_session_storage

# Initialize service
session_storage = await get_session_storage()
user_session_service = UserSessionService(session_storage)
```

### Create User Session

```python
from datetime import datetime, UTC, timedelta

# After successful OAuth login
session_id = await user_session_service.create_user_session(
    user_id="u-12345",
    provider="google",
    client_fingerprint="sha256:browser-info-hash",
    refresh_token="oauth-refresh-token",
    access_token="oauth-access-token",
    access_token_expires_at=datetime.now(UTC) + timedelta(hours=1)
)

# Returns: session_id (e.g., "abc123xyz789")
# Session stored with key: "user:abc123xyz789"
# Default TTL: 3600 seconds (1 hour)
```

### Retrieve User Session

```python
# On each authenticated request
user_session = await user_session_service.get_user_session(
    session_id="abc123xyz789"
)

if user_session is None:
    # Session expired or invalid
    raise HTTPException(status_code=401, detail="Session expired")

# Access session data
print(f"User ID: {user_session.user_id}")
print(f"Provider: {user_session.provider}")
print(f"Expires at: {user_session.expires_at}")
```

### Validate Session

```python
# Validate session and check expiration
is_valid = await user_session_service.validate_session(
    session_id="abc123xyz789",
    client_fingerprint="sha256:browser-info-hash"
)

if not is_valid:
    # Session invalid, expired, or fingerprint mismatch
    raise HTTPException(status_code=401, detail="Invalid session")
```

### Delete Session (Logout)

```python
# On logout
await user_session_service.delete_session(session_id="abc123xyz789")

# Session immediately removed from Redis
```

### Rotate Session

```python
# Rotate session ID after sensitive operations
new_session_id = await user_session_service.rotate_session(
    old_session_id="abc123xyz789"
)

# Old session deleted, new session created with same data
# Update cookie with new session ID
response.set_cookie("user_session_id", new_session_id, httponly=True)
```

### Complete Example: Authentication Middleware

```python
from fastapi import Request, Depends, HTTPException
from app.core.services.session.user_session import UserSessionService
from app.core.storage.session_storage import get_session_storage

async def get_current_user_session(
    request: Request,
    session_storage: SessionStorage = Depends(get_session_storage)
) -> UserSession:
    """
    FastAPI dependency to require authentication.
    
    Validates user session from cookie.
    """
    # Get session ID from cookie
    session_id = request.cookies.get("user_session_id")
    if not session_id:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated"
        )
    
    # Initialize service
    user_session_service = UserSessionService(session_storage)
    
    # Get client fingerprint (hash of User-Agent, Accept-Language, etc.)
    client_fingerprint = generate_client_fingerprint(request)
    
    # Validate session
    is_valid = await user_session_service.validate_session(
        session_id=session_id,
        client_fingerprint=client_fingerprint
    )
    
    if not is_valid:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session"
        )
    
    # Get session data
    user_session = await user_session_service.get_user_session(session_id)
    
    if user_session is None:
        raise HTTPException(
            status_code=401,
            detail="Session not found"
        )
    
    return user_session

# Use in protected endpoints
@router.get("/protected")
async def protected_endpoint(
    user_session: UserSession = Depends(get_current_user_session)
):
    return {
        "message": f"Hello, user {user_session.user_id}!",
        "provider": user_session.provider,
        "expires_at": user_session.expires_at.isoformat()
    }
```

## Auth Session Management

Auth sessions track temporary OAuth state during the login flow.

### Create Auth Session

```python
from app.core.models.auth_session import AuthSession
from datetime import datetime, UTC
import secrets

# Generate OAuth state tokens
state = secrets.token_urlsafe(32)
nonce = secrets.token_urlsafe(32)
auth_session_id = secrets.token_urlsafe(32)

# Create auth session
auth_session = AuthSession(
    provider="google",
    state=state,
    nonce=nonce,
    redirect_uri="http://localhost:3000/dashboard",
    created_at=datetime.now(UTC)
)

# Store with 10 minute TTL
await session_storage.set(
    key=f"auth:{auth_session_id}",
    value=auth_session,
    ttl_seconds=600
)
```

### Validate and Consume Auth Session

```python
# On OAuth callback
auth_session = await session_storage.get(
    key=f"auth:{auth_session_id}",
    model_class=AuthSession
)

if auth_session is None:
    raise HTTPException(status_code=401, detail="Auth session expired")

# Verify state (CSRF protection)
if auth_session.state != received_state:
    raise HTTPException(status_code=401, detail="Invalid state")

# Delete auth session (one-time use)
await session_storage.delete(key=f"auth:{auth_session_id}")

# Proceed with token exchange...
```

## Caching Patterns

### Simple Cache with TTL

```python
from fastapi import APIRouter, Depends
from app.core.services.redis_service import RedisService, get_redis_service
import json

router = APIRouter()

@router.get("/expensive-data/{item_id}")
async def get_expensive_data(
    item_id: str,
    redis_service: RedisService = Depends(get_redis_service)
):
    """
    Fetch data with caching.
    
    First request: Fetch from database (slow)
    Subsequent requests: Fetch from Redis (fast)
    """
    cache_key = f"expensive_data:{item_id}"
    redis_client = await redis_service.get_client()
    
    # Try cache first
    cached_data = await redis_client.get(cache_key)
    if cached_data:
        return json.loads(cached_data)
    
    # Cache miss - fetch from database
    data = await fetch_from_database(item_id)  # Expensive operation
    
    # Cache result for 1 hour
    await redis_client.set(
        cache_key,
        json.dumps(data),
        ex=3600
    )
    
    return data
```

### Cache Invalidation

```python
@router.put("/items/{item_id}")
async def update_item(
    item_id: str,
    new_data: dict,
    redis_service: RedisService = Depends(get_redis_service)
):
    """
    Update item and invalidate cache.
    """
    # Update database
    await update_database(item_id, new_data)
    
    # Invalidate cache
    cache_key = f"expensive_data:{item_id}"
    redis_client = await redis_service.get_client()
    await redis_client.delete(cache_key)
    
    return {"message": "Item updated"}
```

### Cache-Aside Pattern (Lazy Loading)

```python
async def get_user_profile(
    user_id: str,
    redis_client
) -> dict:
    """
    Cache-aside pattern: Load from cache, fallback to DB.
    """
    cache_key = f"user_profile:{user_id}"
    
    # Try cache
    cached_profile = await redis_client.get(cache_key)
    if cached_profile:
        return json.loads(cached_profile)
    
    # Cache miss - load from DB
    profile = await database.get_user_profile(user_id)
    
    # Update cache
    await redis_client.set(
        cache_key,
        json.dumps(profile),
        ex=3600  # 1 hour TTL
    )
    
    return profile
```

### Write-Through Cache

```python
async def update_user_profile(
    user_id: str,
    new_profile: dict,
    redis_client
):
    """
    Write-through pattern: Update DB and cache together.
    """
    # Update database
    await database.update_user_profile(user_id, new_profile)
    
    # Update cache
    cache_key = f"user_profile:{user_id}"
    await redis_client.set(
        cache_key,
        json.dumps(new_profile),
        ex=3600
    )
```

### JWKS Caching (Real Example)

```python
from app.core.services.jwt.jwks import JWKSCache, JWKSCacheInMemory
import httpx

class JWKSService:
    def __init__(self, cache: JWKSCache):
        self.cache = cache
    
    async def get_jwks(self, issuer_url: str) -> dict:
        """
        Get JWKS with caching.
        
        First request: Fetch from issuer (100ms)
        Cached requests: Fetch from memory (<1ms)
        """
        # Try cache
        cached_jwks = self.cache.get(issuer_url)
        if cached_jwks:
            return cached_jwks
        
        # Cache miss - fetch from issuer
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{issuer_url}/.well-known/jwks.json")
            jwks = response.json()
        
        # Cache for 1 hour
        self.cache.set(issuer_url, jwks, ttl_seconds=3600)
        
        return jwks

# Usage
cache = JWKSCacheInMemory()
jwks_service = JWKSService(cache)

# First call: 100ms (network request)
jwks = await jwks_service.get_jwks("https://accounts.google.com")

# Second call: <1ms (cache hit)
jwks = await jwks_service.get_jwks("https://accounts.google.com")
```

## Direct Redis Operations

### Basic Operations

```python
from app.core.services.redis_service import get_redis_service

redis_service = await get_redis_service()
redis_client = await redis_service.get_client()

# SET - Store value
await redis_client.set("key", "value")
await redis_client.set("key", "value", ex=3600)  # With TTL

# GET - Retrieve value
value = await redis_client.get("key")  # Returns string or None

# DEL - Delete key
await redis_client.delete("key")

# EXISTS - Check existence
exists = await redis_client.exists("key")  # Returns 1 if exists, 0 otherwise

# TTL - Get remaining time
ttl = await redis_client.ttl("key")  # Seconds until expiration, -1 if no TTL

# EXPIRE - Set expiration
await redis_client.expire("key", 3600)  # Expire in 1 hour
```

### Hash Operations

```python
# HSET - Set hash field
await redis_client.hset("user:123", "name", "John Doe")
await redis_client.hset("user:123", "email", "john@example.com")

# HGET - Get hash field
name = await redis_client.hget("user:123", "name")

# HGETALL - Get all fields
user_data = await redis_client.hgetall("user:123")
# Returns: {"name": "John Doe", "email": "john@example.com"}

# HDEL - Delete hash field
await redis_client.hdel("user:123", "email")

# HEXISTS - Check field existence
exists = await redis_client.hexists("user:123", "name")
```

### List Operations

```python
# LPUSH - Push to list (left)
await redis_client.lpush("recent_logins", "user:123")

# RPUSH - Push to list (right)
await redis_client.rpush("pending_tasks", "task:456")

# LRANGE - Get list range
logins = await redis_client.lrange("recent_logins", 0, 9)  # First 10

# LPOP - Pop from left
task = await redis_client.lpop("pending_tasks")

# LLEN - Get list length
count = await redis_client.llen("recent_logins")
```

### Set Operations

```python
# SADD - Add to set
await redis_client.sadd("active_users", "user:123", "user:456")

# SMEMBERS - Get all members
users = await redis_client.smembers("active_users")

# SISMEMBER - Check membership
is_active = await redis_client.sismember("active_users", "user:123")

# SREM - Remove from set
await redis_client.srem("active_users", "user:123")
```

### Sorted Set Operations

```python
# ZADD - Add with score
await redis_client.zadd("leaderboard", {"user:123": 100, "user:456": 150})

# ZRANGE - Get range by rank
top_users = await redis_client.zrange("leaderboard", 0, 9, desc=True)

# ZSCORE - Get member score
score = await redis_client.zscore("leaderboard", "user:123")

# ZRANK - Get member rank
rank = await redis_client.zrank("leaderboard", "user:123")
```

### Scanning Keys

```python
# SCAN - Iterate over keys (production-safe)
cursor = 0
pattern = "user:*"
all_keys = []

while True:
    cursor, keys = await redis_client.scan(
        cursor=cursor,
        match=pattern,
        count=100
    )
    all_keys.extend(keys)
    
    if cursor == 0:
        break

# Never use KEYS in production (blocks server)
# keys = await redis_client.keys("user:*")  # ❌ DANGEROUS
```

## Error Handling

### Connection Errors

```python
from redis.exceptions import ConnectionError, TimeoutError
from fastapi import HTTPException

try:
    redis_client = await redis_service.get_client()
    await redis_client.set("key", "value")
except ConnectionError:
    # Redis not available
    raise HTTPException(
        status_code=503,
        detail="Redis service unavailable"
    )
except TimeoutError:
    # Operation took too long
    raise HTTPException(
        status_code=504,
        detail="Redis operation timed out"
    )
```

### Graceful Degradation

```python
async def get_data_with_fallback(
    key: str,
    redis_service: RedisService
):
    """
    Try cache first, fallback to database if Redis fails.
    """
    try:
        redis_client = await redis_service.get_client()
        cached_data = await redis_client.get(key)
        
        if cached_data:
            return json.loads(cached_data)
    except Exception as e:
        # Log error but don't fail
        logger.warning(f"Redis error: {e}, falling back to database")
    
    # Fallback to database
    return await fetch_from_database(key)
```

### Retry Logic

The Redis client automatically retries with exponential backoff:

```python
# Configured in RedisService
Retry(
    ExponentialBackoff(base=1, cap=10),
    retries=6
)

# Retries automatically on transient errors:
# - Connection errors
# - Timeout errors
# - Server errors (5xx)

# Does NOT retry:
# - Authentication errors
# - Syntax errors
# - Client errors (4xx)
```

## Testing

### Unit Tests (In-Memory Storage)

```python
import pytest
from app.core.storage.session_storage import InMemorySessionStorage
from app.core.services.session.user_session import UserSessionService

@pytest.fixture
async def session_storage():
    """Provide in-memory storage for fast tests."""
    return InMemorySessionStorage()

@pytest.fixture
async def user_session_service(session_storage):
    """Provide user session service."""
    return UserSessionService(session_storage)

async def test_create_user_session(user_session_service):
    """Test session creation."""
    session_id = await user_session_service.create_user_session(
        user_id="test-user",
        provider="test-provider",
        client_fingerprint="test-fingerprint",
        refresh_token="refresh-token",
        access_token="access-token"
    )
    
    assert session_id is not None
    
    # Verify session exists
    session = await user_session_service.get_user_session(session_id)
    assert session.user_id == "test-user"
```

### Integration Tests (Real Redis)

```python
import pytest
from app.core.storage.session_storage import RedisSessionStorage
from app.core.services.redis_service import RedisService

@pytest.fixture
async def redis_session_storage():
    """Provide Redis storage for integration tests."""
    redis_service = RedisService()
    redis_client = await redis_service.get_client()
    storage = RedisSessionStorage(redis_client)
    
    yield storage
    
    # Cleanup: Delete all test keys
    keys = await redis_client.keys("test:*")
    if keys:
        await redis_client.delete(*keys)
    
    await redis_service.close()

async def test_redis_session_persistence(redis_session_storage):
    """Test session persistence in Redis."""
    await redis_session_storage.set(
        key="test:session",
        value={"data": "value"},
        ttl_seconds=60
    )
    
    # Verify data persisted
    data = await redis_session_storage.get(
        key="test:session",
        model_class=dict
    )
    
    assert data["data"] == "value"
```

### Mocking Redis

```python
from unittest.mock import AsyncMock, MagicMock
import pytest

@pytest.fixture
def mock_redis_client():
    """Mock Redis client for unit tests."""
    client = AsyncMock()
    client.get = AsyncMock(return_value='{"key": "value"}')
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    return client

async def test_with_mock_redis(mock_redis_client):
    """Test using mocked Redis client."""
    await mock_redis_client.set("key", "value")
    value = await mock_redis_client.get("key")
    
    assert value == '{"key": "value"}'
    mock_redis_client.set.assert_called_once_with("key", "value")
```

## Best Practices

### 1. Always Use TTL

```python
# ✅ GOOD: Data auto-expires
await redis_client.set("key", "value", ex=3600)

# ❌ BAD: Data never expires (memory leak)
await redis_client.set("key", "value")
```

### 2. Use Appropriate Key Patterns

```python
# ✅ GOOD: Hierarchical keys
"user:12345:session"
"user:12345:profile"
"auth:abc123:state"

# ❌ BAD: Flat keys (hard to search/delete)
"user12345session"
"userprofile12345"
```

### 3. Avoid KEYS Command

```python
# ✅ GOOD: Use SCAN (non-blocking)
cursor = 0
while True:
    cursor, keys = await redis_client.scan(cursor, match="user:*", count=100)
    process_keys(keys)
    if cursor == 0:
        break

# ❌ BAD: KEYS blocks server (disabled in production)
# keys = await redis_client.keys("user:*")
```

### 4. Handle Connection Failures

```python
# ✅ GOOD: Graceful fallback
try:
    return await get_from_redis(key)
except ConnectionError:
    logger.warning("Redis unavailable, using database")
    return await get_from_database(key)

# ❌ BAD: Crash on Redis failure
# return await get_from_redis(key)  # Crashes if Redis down
```

### 5. Use Pipelining for Bulk Operations

```python
# ✅ GOOD: Pipeline (1 network round-trip)
async with redis_client.pipeline() as pipe:
    for i in range(1000):
        pipe.set(f"key:{i}", f"value:{i}")
    await pipe.execute()

# ❌ BAD: Individual commands (1000 network round-trips)
for i in range(1000):
    await redis_client.set(f"key:{i}", f"value:{i}")
```

### 6. Set Appropriate TTLs

```python
# Session data: Short TTL (1 hour)
await redis_client.set("session:abc", data, ex=3600)

# JWKS cache: Medium TTL (1 hour)
await redis_client.set("jwks:issuer", data, ex=3600)

# User profiles: Long TTL (24 hours)
await redis_client.set("profile:123", data, ex=86400)

# Temporary data: Very short TTL (5 minutes)
await redis_client.set("temp:xyz", data, ex=300)
```

### 7. Use Type-Safe Models

```python
# ✅ GOOD: Pydantic models
from app.core.models.user_session import UserSession

session = await session_storage.get("user:abc", model_class=UserSession)
# Type-safe: session.user_id, session.expires_at, etc.

# ❌ BAD: Raw dictionaries
session = json.loads(await redis_client.get("user:abc"))
# No type safety, prone to errors
```

### 8. Monitor Memory Usage

```python
# Check memory usage periodically
info = await redis_service.get_info()
used_memory_mb = info["used_memory"] / 1024 / 1024

if used_memory_mb > 400:  # 80% of 512MB limit
    logger.warning(f"Redis memory high: {used_memory_mb:.2f}MB")
```

## Next Steps

- [Main Overview](./main.md) - Understand Redis architecture
- [Configuration](./configuration.md) - Configure Redis settings
- [Security](./security.md) - Secure Redis in production
- [CLI Access](./redis-cli-access.md) - Debug with Redis CLI
