# Redis Cache and Session Store

## Overview

[Redis](https://redis.io) is an in-memory data structure store used as a database, cache, message broker, and streaming engine. In this application, Redis serves as the primary backend for:

- **Session Storage** - User authentication sessions and OAuth tokens
- **Rate Limiting** - API request throttling and quota enforcement via `fastapi-limiter`
- **Future Enhancements**:
  - JWKS caching (currently in-memory via TTLCache)
  - Background job queues

## What is Redis?

Redis (REmote DIctionary Server) is an open-source, in-memory key-value data store known for:

- **Speed**: All data resides in memory, providing sub-millisecond response times
- **Versatility**: Supports strings, hashes, lists, sets, sorted sets, bitmaps, and more
- **Persistence**: Optional disk persistence with RDB snapshots and AOF logs
- **High Availability**: Replication, automatic failover, and clustering
- **Atomic Operations**: All operations are atomic, ensuring data consistency
- **TTL Support**: Built-in expiration for automatic data cleanup

### Key Features for This Application

#### 1. **Session Management**
Sessions are stored with automatic expiration:
```
Key: user:abc123xyz
Value: {"user_id": "u-12345", "provider": "google", "expires_at": 1730563200}
TTL: 3600 seconds (1 hour)
```

After TTL expires, Redis automatically removes the session - no manual cleanup needed.

#### 2. **Rate Limiting**
API request limits are enforced to prevent abuse and ensure fair resource allocation:
```
Key: fastapi-limiter:{endpoint}:{user_or_ip}
Value: Request count within time window
TTL: window_ms (e.g., 5000ms = 5 seconds)
```

When Redis is available, the application uses `fastapi-limiter` for distributed rate limiting across multiple app instances. This ensures consistent rate limits even in scaled deployments.

**Configuration** (from `config.yaml`):
```yaml
rate_limiter:
  requests: 10        # Max requests per window
  window_ms: 5000     # Time window in milliseconds
  per_endpoint: true  # Separate limits per endpoint
  per_method: true    # Separate limits per HTTP method
```

#### 3. **Fallback Support**
The application gracefully degrades to in-memory storage if Redis is unavailable:
- **Production**: Redis failure is logged but doesn't crash the app
- **Development**: Can run without Redis for quick testing
- **Testing**: Unit tests use in-memory storage by default

## Use Cases in This Application

### 1. **User Session Storage**

**Problem**: HTTP is stateless. We need to track authenticated users across requests without sending tokens on every request (security risk).

**Solution**: Store encrypted session data in Redis with automatic expiration:

```python
# After successful OAuth login
session_id = await user_session_service.create_user_session(
    user_id="u-12345",
    provider="google",
    client_fingerprint="hash-of-browser-info",
    refresh_token="oauth_refresh_token",
    access_token="oauth_access_token"
)

# Set HttpOnly cookie (not accessible to JavaScript)
response.set_cookie("user_session_id", session_id, httponly=True, secure=True)
```

**Benefits**:
- ✅ Sessions automatically expire after inactivity
- ✅ No database queries for every request (fast!)
- ✅ Tokens never exposed to browser JavaScript
- ✅ Can invalidate all user sessions instantly

### 2. **Rate Limiting**

**Problem**: Need to prevent API abuse, ensure fair resource allocation, and protect against DDoS attacks across multiple application instances.

**Solution**: Use Redis-backed `fastapi-limiter` for distributed rate limiting:

```python
from fastapi import Depends
from src.app.api.http.middleware.limiter import get_rate_limiter

@router.get("/api/resource")
async def get_resource(
    rate_limit: None = Depends(get_rate_limiter())
):
    # Rate limit enforced automatically
    return {"data": "resource"}
```

**How It Works**:
1. Request comes in for `/api/resource`
2. Rate limiter checks Redis: `fastapi-limiter:/api/resource:user:123`
3. If under limit: increment counter, allow request
4. If over limit: return 429 Too Many Requests with `Retry-After` header
5. Counter auto-expires after time window (e.g., 5 seconds)

**Benefits**:
- ✅ Distributed rate limiting across multiple app instances
- ✅ Per-endpoint and per-user/IP limits
- ✅ Automatic cleanup via TTL
- ✅ Configurable limits without code changes
- ✅ Graceful fallback to in-memory limiter if Redis unavailable

**Impact**:
- **Without rate limiting**: API vulnerable to abuse, resource exhaustion
- **With Redis rate limiting**: Consistent limits across scaled deployments
- **Fallback mode**: In-memory limits (per-instance, not distributed)

### 3. **Auth Session Storage** (OAuth Flow)

**Problem**: OAuth login requires multiple HTTP redirects. We need to track the login state between callbacks without exposing sensitive data to the client.

**Solution**: Store temporary OAuth state in Redis:

```python
# Step 1: Initiate OAuth flow
auth_session_id = secrets.token_urlsafe(32)
await storage.set(
    f"auth:{auth_session_id}",
    {"provider": "google", "state": "random-csrf-token", "nonce": "random-nonce"},
    ttl_seconds=600  # 10 minutes
)

# Step 2: Handle callback (after user logs in with Google)
auth_session = await storage.get(f"auth:{auth_session_id}")
# Verify state, exchange code for tokens, create user session
```

**Benefits**:
- ✅ CSRF protection via state parameter
- ✅ Sessions auto-expire if user abandons flow
- ✅ No database writes for temporary data

### 4. **In-Memory Fallback for Development**

**Problem**: Developers shouldn't need to run Redis for quick local testing.

**Solution**: Automatic fallback to in-memory storage:

```python
# Auto-detection on startup
storage = await get_session_storage()

# If Redis available: RedisSessionStorage
# If Redis unavailable: InMemorySessionStorage (same interface!)
```

**Development Experience**:
- ✅ Redis optional for local dev
- ✅ Production requires Redis
- ✅ Same code works in both modes

## Architecture

### High-Level Architecture

```
┌─────────────────────┐
│   FastAPI App       │
│                     │
│  ┌───────────────┐  │      ┌──────────────────┐
│  │RedisService   │──┼─────▶│  Redis Server    │
│  │               │  │      │  (localhost:6379)│
│  └───────┬───────┘  │      └──────────────────┘
│          │          │              │
│          ▼          │              │
│  ┌───────────────┐  │              │
│  │SessionStorage │  │         Persistence:
│  │ - Redis       │  │         ├─ RDB Snapshots
│  │ - InMemory    │  │         └─ AOF Logs
│  └───────────────┘  │
│          │          │
│          ▼          │
│  ┌───────────────┐  │
│  │Session Services│ │
│  │ - UserSession │  │
│  │ - AuthSession │  │
│  │ - JWKS Cache  │  │
│  └───────────────┘  │
└─────────────────────┘
```

### Components in This Application

#### 1. **RedisService** (`src/app/core/services/redis_service.py`)
- Manages Redis client lifecycle (connection, health checks, shutdown)
- Singleton service injected as FastAPI dependency
- Handles connection failures gracefully
- Provides health check endpoint integration

**Key Methods**:
- `get_client()` - Returns async Redis client
- `health_check()` - PING test for monitoring
- `test_operation()` - Full read/write/delete test
- `get_info()` - Redis server statistics
- `close()` - Graceful connection shutdown

#### 2. **SessionStorage** (`src/app/core/storage/session_storage.py`)
Abstract interface with two implementations:

**RedisSessionStorage**:
- Production implementation
- Uses Redis for persistence
- Automatic TTL management
- SCAN-based key listing

**InMemorySessionStorage**:
- Development/testing implementation
- Python dict with manual expiration checking
- No external dependencies
- Same interface as Redis version

**Key Methods**:
- `set(key, value, ttl)` - Store session with expiration
- `get(key, model_class)` - Retrieve and deserialize session
- `delete(key)` - Remove session
- `exists(key)` - Check if session exists
- `list_keys(pattern)` - Find keys matching pattern
- `list_sessions(pattern, model_class)` - List all matching sessions

#### 3. **UserSessionService** (`src/app/core/services/session/user_session.py`)
Manages authenticated user sessions:
- Creates sessions after successful OAuth login
- Validates sessions on each request
- Handles token refresh
- Rotates sessions for security
- Tracks user activity

#### 4. **AuthSessionService** (OAuth flow tracking)
Manages temporary OAuth authentication state:
- Stores CSRF tokens and nonces
- Tracks redirect URIs
- Prevents replay attacks
- Auto-expires abandoned flows

#### 5. **Rate Limiting** (via fastapi-limiter)
Distributed API rate limiting:
- Redis-backed for multi-instance consistency
- Per-endpoint and per-user/IP limits
- Automatic counter expiration
- Fallback to in-memory if Redis unavailable

**Note**: JWKS (JSON Web Key Set) caching is currently implemented using in-memory `TTLCache` (not Redis). See `src/app/core/services/jwt/jwks.py` for implementation.

## Implementation Details

### Connection Management

#### Development Setup
```yaml
# docker-compose.dev.yml
redis:
  image: redis:7-alpine
  ports:
    - "6380:6379"  # Host port 6380, container port 6379
  command: redis-server --appendonly yes
  volumes:
    - redis_data:/data
```

**Access**:
- From host: `redis://localhost:6380`
- From containers: `redis://redis:6379`
- No password required (development only)

#### Production Setup
```yaml
# docker-compose.prod.yml
redis:
  build: infra/docker/prod/redis
  ports:
    - "127.0.0.1:6379:6379"  # Bound to localhost only
  secrets:
    - redis_password
  volumes:
    - redis_data:/data
    - redis_backups:/var/lib/redis/backups
```

**Security**:
- Password authentication required
- Bound to localhost (not exposed externally)
- TLS/SSL optional (via URL scheme `rediss://`)
- Dangerous commands disabled (FLUSHALL, KEYS, etc.)

### Persistence Strategy

#### RDB Snapshots (Point-in-Time)
```conf
# redis.conf
save 900 1      # Save if 1 key changed in 15 minutes
save 300 10     # Save if 10 keys changed in 5 minutes
save 60 10000   # Save if 10,000 keys changed in 1 minute
```

**Characteristics**:
- ✅ Compact file size
- ✅ Fast restarts
- ✗ Data loss possible (last 1-15 minutes)
- ✗ CPU spike during save

**Best for**: Development, non-critical caches

#### AOF (Append-Only File)
```conf
# redis.conf
appendonly yes
appendfsync everysec  # Sync to disk every second
```

**Characteristics**:
- ✅ Minimal data loss (max 1 second)
- ✅ Crash-safe
- ✗ Larger file size
- ✗ Slower restarts

**Best for**: Production, session storage

#### Hybrid Mode (RDB + AOF)
```conf
aof-use-rdb-preamble yes
```

**Combines best of both**:
- Fast restarts (RDB format)
- Minimal data loss (AOF incremental updates)
- **Recommended for production**

### Connection Pooling

The RedisService uses connection pooling for efficiency:

```python
# redis_service.py
self._client = redis_async.from_url(
    connection_string,
    max_connections=10,           # Pool size
    socket_timeout=5,              # 5 second read timeout
    socket_connect_timeout=5,      # 5 second connect timeout
    socket_keepalive=True,         # Keep connections alive
    health_check_interval=30,      # Verify connections every 30s
    retry=Retry(
        ExponentialBackoff(base=1, cap=10),
        retries=6                  # Auto-retry failed operations
    )
)
```

**Benefits**:
- Reuses connections (no handshake overhead)
- Automatically handles connection failures
- Exponential backoff prevents thundering herd
- Health checks detect stale connections

## Data Model

### Session Keys

#### User Sessions
```
Pattern: user:{session_id}
Example: user:abc123xyz789
TTL: 3600 seconds (configurable)
Value: {
  "id": "abc123xyz789",
  "user_id": "u-12345",
  "provider": "google",
  "client_fingerprint_hash": "sha256:...",
  "created_at": 1730560000,
  "expires_at": 1730563600,
  "last_activity": 1730561234,
  "refresh_token": "encrypted:...",
  "access_token": "encrypted:...",
  "access_token_expires_at": 1730562000
}
```

#### Auth Sessions (OAuth Flow)
```
Pattern: auth:{session_id}
Example: auth:xyz789abc123
TTL: 600 seconds (10 minutes)
Value: {
  "provider": "google",
  "state": "random-csrf-token",
  "nonce": "random-nonce",
  "redirect_uri": "http://localhost:3000/dashboard",
  "created_at": 1730560000
}
```

#### JWKS Cache
```
Pattern: jwks:{issuer_url}
Example: jwks:https://accounts.google.com
TTL: 3600 seconds (1 hour)
Value: {
  "keys": [
    {
      "kty": "RSA",
      "kid": "abc123",
      "use": "sig",
      "n": "...",
      "e": "AQAB"
    }
  ]
}
```

## Failover and High Availability

### Graceful Degradation

The application handles Redis failures gracefully:

**Startup**:
```python
# If Redis unavailable at startup
try:
    redis_service = RedisService()  # Logs warning, continues
    storage = RedisSessionStorage(redis_client)
except Exception:
    logger.warning("Redis unavailable, using in-memory storage")
    storage = InMemorySessionStorage()
```

**Runtime**:
```python
# If Redis fails during operation
try:
    await storage.set(key, value, ttl)
except RuntimeError as e:
    logger.error(f"Redis operation failed: {e}")
    # Option 1: Retry with exponential backoff (automatic)
    # Option 2: Fallback to in-memory (requires implementation)
    # Option 3: Return error to user
```

### Production High Availability (Future)

For production deployments requiring >99.9% uptime:

1. **Redis Sentinel** (Master-Slave Replication)
   - Automatic failover
   - Read scaling
   - ~30 second failover time

2. **Redis Cluster** (Sharding)
   - Horizontal scaling
   - Automatic rebalancing
   - Higher throughput

3. **Redis Enterprise** (Commercial)
   - Active-active geo-replication
   - <1 second failover
   - 99.999% uptime SLA

## Performance Characteristics

### Latency

**Local Development** (localhost):
- SET: 0.1-0.5ms
- GET: 0.1-0.5ms
- DEL: 0.1-0.5ms

**Production** (same datacenter):
- SET: 1-2ms
- GET: 1-2ms
- DEL: 1-2ms

**Production** (cross-datacenter):
- SET: 10-50ms (depends on distance)
- GET: 10-50ms
- DEL: 10-50ms

### Throughput

**Single Redis Instance**:
- Simple GET/SET: ~100,000 ops/sec
- Complex operations: ~10,000 ops/sec
- Pipeline mode: ~1,000,000 ops/sec

**This Application's Load** (typical):
- Session reads: ~100/sec (authenticated requests)
- Session writes: ~10/sec (logins/logouts)
- JWKS cache reads: ~50/sec (JWT validations)
- **Well within capacity** ✅

### Memory Usage

**Session Storage**:
- Average session size: ~500 bytes
- 1,000 concurrent users: ~500 KB
- 10,000 concurrent users: ~5 MB
- 100,000 concurrent users: ~50 MB

**JWKS Cache**:
- Average JWKS: ~2 KB per provider
- 5 providers: ~10 KB
- Negligible compared to sessions

**Recommended Redis Memory**:
- Small deployments (<1,000 users): 128 MB
- Medium deployments (<10,000 users): 512 MB
- Large deployments (<100,000 users): 2 GB

## Monitoring and Observability

### Health Checks

**Basic PING**:
```python
healthy = await redis_service.health_check()
# Returns True if Redis responds to PING
```

**Full Test** (read/write/delete):
```python
healthy = await redis_service.test_operation()
# Returns True if Redis can SET, GET, and DEL
```

**Server Info**:
```python
info = await redis_service.get_info()
# Returns: {
#   "version": "7.0.5",
#   "uptime_seconds": 3600,
#   "connected_clients": 5,
#   "used_memory_human": "2.5M",
#   "total_commands_processed": 12345
# }
```

### Key Metrics to Monitor

1. **Memory Usage** - Alert if >80% of maxmemory
2. **Evicted Keys** - Alert if evictions occurring (memory pressure)
3. **Expired Keys** - Should match session creation rate
4. **Commands/Sec** - Track throughput trends
5. **Latency** - Alert if p99 >10ms
6. **Connection Count** - Alert if approaching max_connections
7. **Rejected Connections** - Indicates connection pool exhaustion

### Redis CLI Monitoring

```bash
# Connect to Redis
docker exec -it api-forge-redis-dev redis-cli

# Monitor real-time commands
> MONITOR

# Get server stats
> INFO

# Check memory usage
> INFO memory

# List all keys (development only - disabled in production)
> KEYS *

# Get key TTL
> TTL user:abc123

# Check connection count
> CLIENT LIST
```

## Security Considerations

### Development Security
- ✅ No password (acceptable for localhost)
- ✅ Bound to localhost (Docker internal network)
- ✅ Data not sensitive (test sessions only)
- ✗ No encryption
- ✗ No access control

### Production Security Requirements
- ✅ Password authentication (via secrets)
- ✅ Bound to `127.0.0.1` (not exposed externally)
- ✅ Dangerous commands disabled (FLUSHALL, KEYS, EVAL, etc.)
- ⚠️ TLS/SSL optional (via `rediss://` URL scheme)
- ⚠️ ACLs (Access Control Lists) for fine-grained permissions
- ⚠️ Encryption at rest (OS-level disk encryption)

### Data Encryption

**In Transit** (TLS):
```python
# Enable TLS via URL scheme
redis_url = "rediss://user:pass@host:6379/0"  # Note: rediss:// (double 's')
```

**At Rest**:
- Use OS-level encryption (LUKS, dm-crypt)
- Or cloud provider encryption (AWS EBS, GCP Persistent Disk)
- Redis itself doesn't encrypt data on disk

**Sensitive Data**:
- Tokens are stored in Redis but should be encrypted at application level
- Consider using application-level encryption for PII
- Redis access should be treated as "sensitive data access"

## Troubleshooting

### Common Issues

**1. Connection Refused**
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solutions**:
- Verify Redis container is running: `docker ps | grep redis`
- Check port mapping: `docker port api-forge-redis-dev`
- Verify URL in config: `REDIS_URL` environment variable
- Check firewall rules (if applicable)

**2. Authentication Failed**
```
redis.exceptions.AuthenticationError: invalid password
```

**Solutions**:
- Check `REDIS_PASSWORD` environment variable
- Verify password in secrets file: `infra/secrets/keys/redis_password.txt`
- Ensure connection string includes password: `redis://:password@host:6379`

**3. Memory Exhausted**
```
redis.exceptions.ResponseError: OOM command not allowed when used memory > 'maxmemory'
```

**Solutions**:
- Increase `maxmemory` in redis.conf
- Enable eviction policy: `maxmemory-policy allkeys-lru`
- Review session TTLs (reduce if too long)
- Scale to larger Redis instance

**4. Slow Performance**
```
Operations taking >10ms
```

**Solutions**:
- Check network latency: `redis-cli --latency`
- Review slow log: `SLOWLOG GET 10`
- Check for expensive operations (KEYS, large SCAN)
- Monitor CPU usage on Redis server
- Enable pipelining for bulk operations

## Development Workflow

### Local Development

**Start Redis**:
```bash
# Start via dev environment
uv run cli dev start-env

# Or directly with Docker Compose
docker-compose -f docker-compose.dev.yml up redis -d
```

**Test Connection**:
```bash
# From host
redis-cli -p 6380 ping
# Should return: PONG

# From container
docker exec -it api-forge-redis-dev redis-cli ping
```

**View Data**:
```bash
# List all keys (dev only)
docker exec -it api-forge-redis-dev redis-cli KEYS '*'

# Get specific key
docker exec -it api-forge-redis-dev redis-cli GET user:abc123

# Monitor live operations
docker exec -it api-forge-redis-dev redis-cli MONITOR
```

### Testing Without Redis

For unit tests, use in-memory storage:

```python
# tests/conftest.py
@pytest.fixture
async def session_storage():
    return InMemorySessionStorage()

# Your test
async def test_user_session(session_storage):
    service = UserSessionService(session_storage)
    session_id = await service.create_user_session(...)
    assert session_id is not None
```

No Redis required! ✅

## Key Benefits

✅ **Fast** - Sub-millisecond latency for session lookups  
✅ **Scalable** - Handles 100,000+ concurrent sessions on single instance  
✅ **Automatic Cleanup** - TTL-based expiration, no manual cleanup needed  
✅ **Graceful Degradation** - Falls back to in-memory storage if unavailable  
✅ **Persistent** - AOF + RDB ensures data survives crashes  
✅ **Type-Safe** - Pydantic models for all cached data  
✅ **Developer Friendly** - Optional for local development  
✅ **Production Ready** - Password auth, dangerous commands disabled, monitoring  

## Next Steps

- [Configuration](./configuration.md) - Configure Redis connection and persistence
- [Usage Guide](./usage.md) - Use Redis from FastAPI endpoints
- [Security](./security.md) - Secure Redis in production
- [Monitoring](./monitoring.md) - Monitor Redis health and performance
