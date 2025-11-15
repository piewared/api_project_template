# Redis Configuration Reference

This document provides a complete reference for all Redis-related configuration options in this application.

## Table of Contents

- [Configuration File Location](#configuration-file-location)
- [Environment Variables](#environment-variables)
- [Core Settings](#core-settings)
- [Connection Settings](#connection-settings)
- [Persistence Settings](#persistence-settings)
- [Security Settings](#security-settings)
- [Performance Tuning](#performance-tuning)
- [Environment-Specific Configuration](#environment-specific-configuration)
- [Redis Server Configuration](#redis-server-configuration)

## Configuration File Location

**Main Config**: `/config.yaml`  
**Environment Overrides**: `.env` file (root directory)  
**Redis Server Config**: `infra/docker/prod/redis/redis.conf` (production only)

## Environment Variables

All Redis configuration can be overridden via environment variables:

```bash
# .env file
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=your-secure-password
REDIS_MAX_CONNECTIONS=10
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5
REDIS_DECODE_RESPONSES=true
```

Environment variables take precedence over `config.yaml` values.

## Core Settings

### `redis.enabled`

**Type**: `boolean`  
**Default**: `true`  
**Environment Variable**: `REDIS_ENABLED`

Enables or disables Redis integration. When disabled, the application falls back to in-memory storage.

```yaml
redis:
  enabled: true
```

**Use Cases**:
- Set to `false` for quick local development without Docker
- Set to `true` for production deployments
- Integration tests may override this per-test

**Impact When Disabled**:
- ✅ Sessions stored in-memory (process memory)
- ✅ Application still works
- ✗ Sessions lost on restart
- ✗ Multiple app instances don't share sessions
- ✗ No persistence across deployments

### `redis.url`

**Type**: `string`  
**Default**: `redis://localhost:6379`  
**Environment Variable**: `REDIS_URL`

Connection string for Redis server.

```yaml
redis:
  url: ${REDIS_URL:-redis://localhost:6379}
```

**Format**: `redis://[user][:password]@host[:port][/database]`

**Examples**:

```bash
# Development (no auth)
redis://localhost:6380

# Production (password auth)
redis://:your-password@localhost:6379

# TLS/SSL
rediss://:your-password@production-redis:6379

# Docker internal network
redis://redis:6379

# Specific database (0-15)
redis://localhost:6379/1
```

**Notes**:
- Use `redis://` for unencrypted connections
- Use `rediss://` for TLS/SSL connections (note double 's')
- Port defaults to 6379 if not specified
- Database defaults to 0 if not specified

### `redis.password`

**Type**: `string`  
**Default**: `null` (no password)  
**Environment Variable**: `REDIS_PASSWORD`

Password for Redis authentication. Can be specified in URL or separately.

```yaml
redis:
  password: ${REDIS_PASSWORD:-}
```

**Priority** (if both specified):
1. Password in URL takes precedence
2. Falls back to `redis.password` config value

**Examples**:

```yaml
# Option 1: In URL
redis:
  url: redis://:mypassword@localhost:6379

# Option 2: Separate config
redis:
  url: redis://localhost:6379
  password: mypassword
```

**Security Notes**:
- ⚠️ Never commit passwords to Git
- ✅ Use environment variables in production
- ✅ Store in secrets management (AWS Secrets Manager, etc.)
- ✅ Rotate regularly (every 90 days)

## Connection Settings

### `redis.max_connections`

**Type**: `integer`  
**Default**: `10`  
**Environment Variable**: `REDIS_MAX_CONNECTIONS`

Maximum number of connections in the connection pool.

```yaml
redis:
  max_connections: ${REDIS_MAX_CONNECTIONS:-10}
```

**Sizing Guidelines**:

| Deployment Size | Recommended Value | Reasoning |
|----------------|-------------------|-----------|
| Small (<100 req/s) | 10 | Default, low overhead |
| Medium (<1000 req/s) | 20-50 | Higher concurrency |
| Large (>1000 req/s) | 50-100 | High throughput |

**Formula**: `max_connections ≈ (peak_requests_per_second / 100) + 10`

**Example Calculation**:
- Peak traffic: 500 requests/second
- Estimated: (500 / 100) + 10 = 15 connections
- Recommended: 20 connections (with headroom)

**Impact**:
- **Too Low**: Connection exhaustion, requests blocked
- **Too High**: Memory waste (each connection ~100KB)
- **Just Right**: Optimal throughput with minimal memory

### `redis.decode_responses`

**Type**: `boolean`  
**Default**: `true`  
**Environment Variable**: `REDIS_DECODE_RESPONSES`

Automatically decode Redis byte responses to UTF-8 strings.

```yaml
redis:
  decode_responses: ${REDIS_DECODE_RESPONSES:-true}
```

**When `true`** (Recommended):
```python
await redis.get("key")  # Returns: "value" (string)
```

**When `false`**:
```python
await redis.get("key")  # Returns: b"value" (bytes)
```

**Use Cases**:
- ✅ Set to `true` for JSON/text data (99% of use cases)
- ✗ Set to `false` only for binary data (images, pickled objects)

**This Application**: Always `true` (sessions and caches are JSON)

### `redis.socket_timeout`

**Type**: `float` (seconds)  
**Default**: `5.0`  
**Environment Variable**: `REDIS_SOCKET_TIMEOUT`

Timeout for socket read operations.

```yaml
redis:
  socket_timeout: ${REDIS_SOCKET_TIMEOUT:-5}
```

**Meaning**: How long to wait for Redis to respond to a command before giving up.

**Tuning**:
- **Network**: Local: 1-2s, Same datacenter: 5s, Cross-region: 10s
- **Safety**: Higher = more patient, Lower = fail fast

**Example Scenarios**:

| Timeout | Use Case |
|---------|----------|
| 1s | Local development, fail-fast debugging |
| 5s | Production (same datacenter) |
| 10s | Cross-region deployments |
| 30s | Slow operations (SCAN, large values) |

**This Application**: 5 seconds (balanced)

### `redis.socket_connect_timeout`

**Type**: `float` (seconds)  
**Default**: `5.0`  
**Environment Variable**: `REDIS_SOCKET_CONNECT_TIMEOUT`

Timeout for establishing initial connection to Redis.

```yaml
redis:
  socket_connect_timeout: ${REDIS_SOCKET_CONNECT_TIMEOUT:-5}
```

**Meaning**: How long to wait for TCP connection handshake.

**Tuning**:
- **Fast Network**: 2-3 seconds
- **Slow Network**: 10 seconds
- **High Availability**: Lower (fail fast, try next node)

**This Application**: 5 seconds (same as socket_timeout)

### Retry Policy

The Redis client automatically retries failed operations with exponential backoff:

```python
# Configured in src/app/core/services/redis_service.py
Retry(
    ExponentialBackoff(base=1, cap=10),
    retries=6
)
```

**Retry Schedule**:
1. Initial attempt: 0ms
2. 1st retry: 1s (base)
3. 2nd retry: 2s (2x base)
4. 3rd retry: 4s (4x base)
5. 4th retry: 8s (8x base)
6. 5th retry: 10s (capped)
7. 6th retry: 10s (capped)

**Total Max Time**: ~45 seconds

**Retry Behavior**:
- ✅ Automatic for transient errors (network blips)
- ✅ Exponential backoff prevents thundering herd
- ✗ Does not retry authentication errors
- ✗ Does not retry syntax errors

### Connection Pool Health Checks

```python
# Configured in src/app/core/services/redis_service.py
health_check_interval=30  # Verify connections every 30s
socket_keepalive=True      # TCP keepalive enabled
```

**Health Check Behavior**:
- Every 30 seconds, send PING to idle connections
- If PING fails, close connection and create new one
- Prevents "connection went away" errors
- Minimal overhead (~1 command per 30s per connection)

## Persistence Settings

Persistence is configured in `infra/docker/prod/redis/redis.conf` (production only).

### RDB Snapshots (Point-in-Time)

```conf
# redis.conf
save 900 1      # After 900 sec (15 min) if at least 1 key changed
save 300 10     # After 300 sec (5 min) if at least 10 keys changed
save 60 10000   # After 60 sec (1 min) if at least 10000 keys changed
```

**How It Works**:
1. Redis forks a child process
2. Child writes memory snapshot to disk (dump.rdb)
3. Parent continues serving requests
4. On restart, Redis loads dump.rdb

**Trade-offs**:
- ✅ Compact file size
- ✅ Fast restarts
- ✗ Data loss risk (last 1-15 minutes)
- ✗ CPU spike during fork

**Configuration Options**:

```conf
# Save location
dir /data
dbfilename dump.rdb

# Compression (reduces file size by ~10x)
rdbcompression yes

# Checksum validation
rdbchecksum yes

# Stop writes on save error (safety)
stop-writes-on-bgsave-error yes
```

**When to Use**:
- ✅ Development environments
- ✅ Cache-only data (acceptable to lose)
- ✗ Session storage (use AOF instead)

### AOF (Append-Only File)

```conf
# redis.conf
appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
```

**How It Works**:
1. Redis logs every write command to AOF
2. On restart, Redis replays all commands
3. Result: Exact state reconstruction

**Sync Modes**:

| Mode | Meaning | Data Loss Risk | Performance |
|------|---------|----------------|-------------|
| `always` | Sync after every write | None | Slow (~100 ops/s) |
| `everysec` | Sync every second | Max 1 second | Fast (~50K ops/s) |
| `no` | OS decides when to sync | Up to 30 seconds | Fastest (~100K ops/s) |

**Recommended**: `everysec` (balance of safety and performance)

**Trade-offs**:
- ✅ Minimal data loss (max 1 second)
- ✅ Crash-safe
- ✗ Larger file size than RDB
- ✗ Slower restarts (replaying commands)

**AOF Rewrite** (compaction):
```conf
auto-aof-rewrite-percentage 100  # Rewrite when 2x original size
auto-aof-rewrite-min-size 64mb   # But not before 64MB
```

**Rewrite Process**:
1. AOF grows over time (append-only)
2. When criteria met, Redis rewrites AOF with current state
3. Result: Smaller file, faster restarts

### Hybrid Mode (RDB + AOF)

```conf
# redis.conf
aof-use-rdb-preamble yes
```

**How It Works**:
1. AOF file starts with RDB snapshot (compact)
2. New writes appended as commands (incremental)
3. On load: Fast RDB load + replay incremental AOF

**Benefits**:
- ✅ Fast restarts (RDB format)
- ✅ Minimal data loss (AOF incremental)
- ✅ **Recommended for production**

**This Application**: Hybrid mode enabled in production

### Data Directory

```yaml
# docker-compose.prod.yml
volumes:
  - redis_data:/data           # Primary data
  - redis_backups:/var/lib/redis/backups  # Backup location
```

**Files**:
- `/data/dump.rdb` - RDB snapshot
- `/data/appendonly.aof` - AOF log
- `/var/lib/redis/backups/` - Manual backups

**Backup Strategy**:
```bash
# Manual backup (RDB snapshot)
docker exec api-forge-redis redis-cli BGSAVE

# Copy backup file
docker cp api-forge-redis:/data/dump.rdb ./backup-$(date +%Y%m%d).rdb

# Restore from backup
docker cp ./backup-20240315.rdb api-forge-redis:/data/dump.rdb
docker restart api-forge-redis
```

## Security Settings

### Password Authentication

#### Development (No Password)
```yaml
# docker-compose.dev.yml
redis:
  image: redis:7-alpine
  # No requirepass (development only)
```

#### Production (Password Required)
```yaml
# docker-compose.prod.yml
redis:
  secrets:
    - redis_password
  entrypoint: ["/usr/local/bin/docker-entrypoint.sh"]
  command: ["redis-server", "/usr/local/etc/redis/redis.conf", "--requirepass", "$(cat /run/secrets/redis_password)"]
```

**Setting Password**:

```bash
# Generate secure password
openssl rand -base64 32 > infra/secrets/keys/redis_password.txt

# Use in .env
echo "REDIS_PASSWORD=$(cat infra/secrets/keys/redis_password.txt)" >> .env
```

### Disabled Commands

Production Redis disables dangerous commands:

```conf
# redis.conf
rename-command FLUSHDB ""      # Wipes database
rename-command FLUSHALL ""     # Wipes all databases
rename-command KEYS ""         # Blocks server (O(N) operation)
rename-command CONFIG ""       # Prevents reconfiguration
rename-command DEBUG ""        # Debugging commands
rename-command SHUTDOWN ""     # Prevents shutdown
rename-command EVAL ""         # Arbitrary Lua execution
rename-command EVALSHA ""      # Lua script execution
```

**Why Disable**:
- `FLUSHDB/FLUSHALL`: Accidental data loss
- `KEYS`: Blocks server on large datasets (use SCAN instead)
- `CONFIG`: Security risk (attacker could reconfigure)
- `EVAL`: Arbitrary code execution

**Development**: All commands enabled (safe for localhost)

### Network Binding

#### Development
```yaml
# docker-compose.dev.yml
ports:
  - "6380:6379"  # Exposed to host on 6380
```

**Access**: Any process on host can connect to `localhost:6380`

#### Production
```yaml
# docker-compose.prod.yml
ports:
  - "127.0.0.1:6379:6379"  # Bound to localhost only
```

**Access**: Only processes on same machine can connect

**External Access** (if needed):
```yaml
# NOT RECOMMENDED - Requires firewall + authentication
ports:
  - "0.0.0.0:6379:6379"  # Exposed to network
```

### TLS/SSL

**Enable TLS** (optional):

```conf
# redis.conf
tls-port 6379
port 0  # Disable unencrypted port

tls-cert-file /certs/redis.crt
tls-key-file /certs/redis.key
tls-ca-cert-file /certs/ca.crt

tls-auth-clients yes  # Require client certificates
```

**Client Configuration**:
```yaml
redis:
  url: rediss://localhost:6379  # Note: rediss:// (double 's')
```

**Certificate Generation**:
```bash
# Generate CA
openssl genrsa -out ca.key 4096
openssl req -new -x509 -key ca.key -out ca.crt -days 3650

# Generate Redis server certificate
openssl genrsa -out redis.key 4096
openssl req -new -key redis.key -out redis.csr
openssl x509 -req -in redis.csr -CA ca.crt -CAkey ca.key -out redis.crt -days 3650
```

**This Application**: TLS not enabled by default (localhost deployment)

### Access Control Lists (ACLs)

Redis 6+ supports fine-grained user permissions:

```conf
# redis.conf

# Default user (admin)
user default on >default-password ~* &* +@all

# Read-only user
user readonly on >readonly-password ~* &* +@read -@write -@dangerous

# Session storage user
user sessionapp on >sessionapp-password ~user:* +get +set +del +expire
```

**ACL Categories**:
- `+@all` - All commands
- `+@read` - Read-only commands (GET, SCAN, etc.)
- `+@write` - Write commands (SET, DEL, etc.)
- `+@dangerous` - Dangerous commands (FLUSHDB, KEYS, etc.)

**This Application**: ACLs not configured (uses single password)

## Performance Tuning

### Memory Management

```conf
# redis.conf
maxmemory 512mb
maxmemory-policy allkeys-lru
```

**Eviction Policies**:

| Policy | Behavior | Use Case |
|--------|----------|----------|
| `noeviction` | Return error when memory full | Databases (never lose data) |
| `allkeys-lru` | Evict least recently used keys | Caches (this application) |
| `volatile-lru` | Evict only keys with TTL | Mixed database + cache |
| `allkeys-random` | Evict random keys | When LRU overhead too high |
| `volatile-ttl` | Evict keys with shortest TTL | Prioritize longer-lived data |

**This Application**: `allkeys-lru` (pure cache, evict when full)

**Memory Estimation**:
- Session size: ~500 bytes
- 1,000 sessions: ~500 KB
- 10,000 sessions: ~5 MB
- 100,000 sessions: ~50 MB

**Recommended Sizing**: 10x peak session count for headroom

### TCP Backlog

```conf
# redis.conf
tcp-backlog 511
```

**Meaning**: Maximum pending connections queue size

**Tuning**:
- Low traffic: 128
- Medium traffic: 511 (default)
- High traffic: 2048

**System Limit**:
```bash
# Check system limit
sysctl net.core.somaxconn

# Increase if needed
sudo sysctl -w net.core.somaxconn=2048
```

### Timeouts

```conf
# redis.conf
timeout 300  # Close idle client connections after 300 seconds
```

**Purpose**: Free up connection slots from abandoned clients

**Tuning**:
- Short-lived connections: 60 seconds
- Long-lived connections: 300 seconds (default)
- Persistent connections: 0 (never timeout)

**This Application**: 300 seconds (balanced)

### Slow Log

```conf
# redis.conf
slowlog-log-slower-than 10000  # Log commands slower than 10ms
slowlog-max-len 128             # Keep last 128 slow commands
```

**Viewing Slow Log**:
```bash
redis-cli SLOWLOG GET 10
```

**Example Output**:
```
1) 1) (integer) 0           # Unique ID
   2) (integer) 1730563200   # Unix timestamp
   3) (integer) 12000        # Execution time (microseconds)
   4) 1) "KEYS"              # Command
      2) "*"
   5) "127.0.0.1:54321"      # Client address
```

**This Application**: 10ms threshold (alerts if exceeded)

### Latency Monitoring

```conf
# redis.conf
latency-monitor-threshold 100  # Track events slower than 100ms
```

**Viewing Latency Events**:
```bash
redis-cli LATENCY LATEST
redis-cli LATENCY HISTORY command
redis-cli LATENCY DOCTOR
```

**This Application**: 100ms threshold (detect serious issues)

## Environment-Specific Configuration

### Development Environment

**File**: `docker-compose.dev.yml`

```yaml
redis:
  image: redis:7-alpine
  container_name: api-forge-redis-dev
  ports:
    - "6380:6379"  # Offset by 1000 to avoid conflicts
  command: redis-server --appendonly yes
  volumes:
    - redis_data:/data
  networks:
    - dev-network
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 3s
    retries: 3
```

**Configuration**:
```yaml
# config.yaml
redis:
  enabled: true
  url: redis://localhost:6380
  password: null  # No password
```

**Characteristics**:
- ✅ No authentication (localhost only)
- ✅ AOF persistence enabled
- ✅ Port 6380 (avoids conflicts with local Redis)
- ✅ Health checks every 10 seconds
- ✗ No security hardening

### Production Environment

**File**: `docker-compose.prod.yml`

```yaml
redis:
  build:
    context: ./infra/docker/prod/redis
  container_name: api-forge-redis
  ports:
    - "127.0.0.1:6379:6379"  # Bound to localhost only
  secrets:
    - redis_password
  volumes:
    - redis_data:/data
    - redis_backups:/var/lib/redis/backups
  networks:
    - app-network
  deploy:
    resources:
      limits:
        memory: 512M
  healthcheck:
    test: ["CMD", "redis-cli", "--no-auth-warning", "-a", "$$REDIS_PASSWORD", "ping"]
    interval: 30s
    timeout: 5s
    retries: 3
```

**Configuration**:
```yaml
# config.yaml
redis:
  enabled: true
  url: ${REDIS_URL:-redis://localhost:6379}
  password: ${REDIS_PASSWORD}
```

**Characteristics**:
- ✅ Password authentication required
- ✅ Dangerous commands disabled
- ✅ Bound to localhost (not exposed externally)
- ✅ Memory limit enforced (512MB)
- ✅ Health checks every 30 seconds
- ✅ Backup volume mounted
- ✅ RDB + AOF hybrid persistence

### Testing Environment

**File**: `tests/conftest.py`

```python
@pytest.fixture
async def session_storage():
    # Use in-memory storage for fast tests
    return InMemorySessionStorage()
```

**Characteristics**:
- ✅ No Redis required (faster test runs)
- ✅ Isolated per test (no shared state)
- ✅ Automatic cleanup
- ✗ Doesn't test Redis integration (use integration tests for that)

## Redis Server Configuration

**File**: `infra/docker/prod/redis/redis.conf`

Full production configuration (100+ lines):

### Core Settings
```conf
bind 0.0.0.0
protected-mode yes
port 6379
tcp-backlog 511
timeout 300
tcp-keepalive 300
```

### Persistence
```conf
save 900 1
save 300 10
save 60 10000
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb

appendonly yes
appendfilename "appendonly.aof"
appendfsync everysec
aof-use-rdb-preamble yes
```

### Memory Management
```conf
maxmemory 512mb
maxmemory-policy allkeys-lru
maxmemory-samples 5
```

### Security
```conf
# Disable dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command KEYS ""
rename-command CONFIG ""
rename-command DEBUG ""
rename-command SHUTDOWN ""
rename-command EVAL ""
rename-command EVALSHA ""
```

### Monitoring
```conf
slowlog-log-slower-than 10000
slowlog-max-len 128
latency-monitor-threshold 100
```

### Logging
```conf
loglevel notice
logfile /data/redis.log
```

See full file at `infra/docker/prod/redis/redis.conf`

## Validation

### Validate Configuration

```bash
# Test connection
redis-cli -p 6380 ping
# Expected: PONG

# Check config
redis-cli -p 6380 CONFIG GET maxmemory
# Expected: 1) "maxmemory" 2) "536870912" (512MB)

# Test authentication (production)
redis-cli -p 6379 -a your-password ping
# Expected: PONG

# Check persistence mode
redis-cli -p 6380 CONFIG GET appendonly
# Expected: 1) "appendonly" 2) "yes"
```

### Health Check Endpoint

```bash
# Application health check
curl http://localhost:8000/health

# Response includes Redis status:
{
  "status": "healthy",
  "services": {
    "redis": "healthy",
    "database": "healthy"
  }
}
```

### Monitor Live Configuration

```bash
# Watch configuration changes
redis-cli -p 6380 CONFIG GET '*'

# Monitor memory usage
redis-cli -p 6380 INFO memory

# Check connection count
redis-cli -p 6380 CLIENT LIST
```

## Troubleshooting Configuration Issues

### Issue: Connection Refused

**Symptom**:
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Diagnosis**:
```bash
# Check if Redis is running
docker ps | grep redis

# Check port mapping
docker port api-forge-redis-dev

# Test connection
redis-cli -p 6380 ping
```

**Solutions**:
- Start Redis: `docker-compose -f docker-compose.dev.yml up redis -d`
- Check `REDIS_URL` environment variable
- Verify port not blocked by firewall

### Issue: Authentication Failed

**Symptom**:
```
redis.exceptions.AuthenticationError: invalid password
```

**Diagnosis**:
```bash
# Check password in environment
echo $REDIS_PASSWORD

# Check password in secrets file
cat infra/secrets/keys/redis_password.txt

# Test with password
redis-cli -p 6379 -a "$(cat infra/secrets/keys/redis_password.txt)" ping
```

**Solutions**:
- Verify `REDIS_PASSWORD` environment variable matches secrets file
- Ensure password included in connection URL: `redis://:password@host:6379`
- Check docker secret is mounted: `docker exec redis cat /run/secrets/redis_password`

### Issue: Out of Memory

**Symptom**:
```
redis.exceptions.ResponseError: OOM command not allowed
```

**Diagnosis**:
```bash
# Check memory usage
redis-cli -p 6380 INFO memory

# Expected output includes:
# used_memory_human:256.00M
# maxmemory_human:512.00M
```

**Solutions**:
- Increase `maxmemory` in redis.conf
- Enable eviction: `maxmemory-policy allkeys-lru`
- Review session TTLs (reduce if too long)
- Scale to larger instance

### Issue: Slow Performance

**Symptom**: Operations taking >10ms

**Diagnosis**:
```bash
# Check latency
redis-cli -p 6380 --latency

# Check slow log
redis-cli -p 6380 SLOWLOG GET 10

# Check CPU usage
docker stats api-forge-redis-dev
```

**Solutions**:
- Avoid expensive operations (KEYS, large SCAN)
- Enable pipelining for bulk operations
- Check network latency
- Increase connection pool size
- Consider Redis Cluster for sharding

## Next Steps

- [Main Overview](./main.md) - Understand Redis architecture
- [Usage Guide](./usage.md) - Use Redis from FastAPI
- [Security](./security.md) - Secure Redis in production
- [Monitoring](./redis-cli-access.md) - Access Redis CLI for debugging
