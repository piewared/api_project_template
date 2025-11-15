# Redis CLI Access and Debugging

This guide covers how to access and use the Redis CLI for debugging, monitoring, and administration.

## Table of Contents

- [Quick Access](#quick-access)
- [Development Environment](#development-environment)
- [Production Environment](#production-environment)
- [Basic Commands](#basic-commands)
- [Debugging Sessions](#debugging-sessions)
- [Monitoring Commands](#monitoring-commands)
- [Administrative Commands](#administrative-commands)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Quick Access

### Development

```bash
# Direct access (no password)
redis-cli -p 6380 ping
# PONG

# From Docker container
docker exec -it api-forge-redis-dev redis-cli ping
# PONG
```

### Production

```bash
# With password (from secrets file)
redis-cli -p 6379 --no-auth-warning -a "$(cat infra/secrets/keys/redis_password.txt)" ping
# PONG

# From Docker container
docker exec -it api-forge-redis redis-cli -a "$(cat /run/secrets/redis_password)" ping
# PONG

# Via SSH tunnel (remote access)
ssh -L 6379:localhost:6379 user@production-server
redis-cli -p 6379 -a "password" ping
```

## Development Environment

### Direct Access from Host

```bash
# Connect to development Redis (port 6380)
redis-cli -p 6380

# Once connected
127.0.0.1:6380> PING
PONG

127.0.0.1:6380> SET mykey "Hello World"
OK

127.0.0.1:6380> GET mykey
"Hello World"

127.0.0.1:6380> QUIT
```

### Execute Single Command

```bash
# No need to enter interactive mode
redis-cli -p 6380 PING
# PONG

redis-cli -p 6380 GET mykey
# "Hello World"

redis-cli -p 6380 INFO server
# Server info output...
```

### From Docker Container

```bash
# Interactive mode
docker exec -it api-forge-redis-dev redis-cli

# Single command
docker exec api-forge-redis-dev redis-cli PING

# With output
docker exec api-forge-redis-dev redis-cli GET user:abc123
```

### Using Docker Compose Exec

```bash
# Interactive mode
docker-compose -f docker-compose.dev.yml exec redis redis-cli

# Single command
docker-compose -f docker-compose.dev.yml exec redis redis-cli DBSIZE
```

## Production Environment

### Authentication Required

```bash
# Option 1: Password on command line (shows warning)
redis-cli -p 6379 -a "your-password" ping

# Option 2: Suppress warning
redis-cli -p 6379 --no-auth-warning -a "your-password" ping

# Option 3: From secrets file
redis-cli -p 6379 --no-auth-warning -a "$(cat infra/secrets/keys/redis_password.txt)" ping

# Option 4: Interactive mode (authenticate after connecting)
redis-cli -p 6379
127.0.0.1:6379> AUTH your-password
OK
127.0.0.1:6379> PING
PONG
```

### From Docker Container

```bash
# Interactive mode with auth
docker exec -it api-forge-redis redis-cli --no-auth-warning -a "$$REDIS_PASSWORD"

# Single command with auth
docker exec api-forge-redis redis-cli --no-auth-warning -a "$$REDIS_PASSWORD" PING

# Using secrets file
docker exec api-forge-redis redis-cli --no-auth-warning -a "$(cat /run/secrets/redis_password)" PING
```

### Remote Access via SSH Tunnel

```bash
# Step 1: Create SSH tunnel (local port 6379 → production server localhost:6379)
ssh -L 6379:localhost:6379 user@production-server

# Step 2: In another terminal, connect to local port
redis-cli -p 6379 --no-auth-warning -a "password" ping
# PONG

# Close tunnel: Ctrl+C in SSH terminal
```

**Why SSH Tunnel?**
- Production Redis bound to `127.0.0.1` (localhost only)
- Cannot connect directly from external IP
- SSH tunnel creates secure encrypted connection
- Appears as localhost connection to Redis

### Access Control Lists (ACLs)

If ACLs are configured, specify username:

```bash
# Connect as specific user
redis-cli -p 6379 --user sessionapp --no-auth-warning -a "sessionapp-password"

# Or authenticate after connecting
redis-cli -p 6379
127.0.0.1:6379> AUTH sessionapp sessionapp-password
OK
```

## Basic Commands

### Data Operations

#### Strings

```bash
# SET - Store value
> SET mykey "myvalue"
OK

# SET with TTL (expires in 3600 seconds)
> SET mykey "myvalue" EX 3600
OK

# GET - Retrieve value
> GET mykey
"myvalue"

# DEL - Delete key
> DEL mykey
(integer) 1

# EXISTS - Check existence
> EXISTS mykey
(integer) 0

# TTL - Get remaining time to live
> SET mykey "value" EX 3600
> TTL mykey
(integer) 3599

# EXPIRE - Set expiration
> SET mykey "value"
> EXPIRE mykey 3600
(integer) 1

# INCR - Increment number
> SET counter 0
> INCR counter
(integer) 1
> INCR counter
(integer) 2
```

#### Hashes

```bash
# HSET - Set hash field
> HSET user:123 name "John Doe"
(integer) 1
> HSET user:123 email "john@example.com"
(integer) 1

# HGET - Get hash field
> HGET user:123 name
"John Doe"

# HGETALL - Get all fields
> HGETALL user:123
1) "name"
2) "John Doe"
3) "email"
4) "john@example.com"

# HDEL - Delete field
> HDEL user:123 email
(integer) 1

# HEXISTS - Check field existence
> HEXISTS user:123 name
(integer) 1
```

#### Lists

```bash
# LPUSH - Push to list (left)
> LPUSH tasks "task1"
(integer) 1
> LPUSH tasks "task2"
(integer) 2

# RPUSH - Push to list (right)
> RPUSH tasks "task3"
(integer) 3

# LRANGE - Get list range
> LRANGE tasks 0 -1
1) "task2"
2) "task1"
3) "task3"

# LPOP - Pop from left
> LPOP tasks
"task2"

# LLEN - Get list length
> LLEN tasks
(integer) 2
```

#### Sets

```bash
# SADD - Add to set
> SADD active_users "user:123"
(integer) 1
> SADD active_users "user:456"
(integer) 1

# SMEMBERS - Get all members
> SMEMBERS active_users
1) "user:123"
2) "user:456"

# SISMEMBER - Check membership
> SISMEMBER active_users "user:123"
(integer) 1

# SREM - Remove from set
> SREM active_users "user:123"
(integer) 1
```

### Key Inspection

```bash
# TYPE - Get key type
> SET mystring "value"
> TYPE mystring
string

> HSET myhash field "value"
> TYPE myhash
hash

# SCAN - Iterate over keys (production-safe)
> SCAN 0 MATCH "user:*" COUNT 10
1) "cursor"  # New cursor for next iteration
2) 1) "user:123"
   2) "user:456"

# Continue scanning
> SCAN cursor MATCH "user:*" COUNT 10

# DBSIZE - Count total keys
> DBSIZE
(integer) 42

# KEYS - List keys (DEVELOPMENT ONLY - disabled in production)
> KEYS user:*
1) "user:123"
2) "user:456"
```

### Persistence

```bash
# SAVE - Synchronous save (blocks server)
> SAVE
OK

# BGSAVE - Background save (non-blocking)
> BGSAVE
Background saving started

# LASTSAVE - Last save timestamp
> LASTSAVE
(integer) 1730563200

# BGREWRITEAOF - Rewrite AOF (compaction)
> BGREWRITEAOF
Background append only file rewriting started
```

## Debugging Sessions

### Inspect Session Data

```bash
# Get user session
> GET user:abc123xyz789
"{\"user_id\":\"u-12345\",\"provider\":\"google\",\"expires_at\":1730563600}"

# Check session TTL
> TTL user:abc123xyz789
(integer) 3245

# List all user sessions
> SCAN 0 MATCH "user:*" COUNT 100
1) "0"
2) 1) "user:abc123xyz789"
   2) "user:def456uvw012"
```

### Inspect Auth Sessions

```bash
# Get auth session (OAuth flow)
> GET auth:xyz789abc123
"{\"provider\":\"google\",\"state\":\"random-token\",\"nonce\":\"random-nonce\"}"

# Check if session exists
> EXISTS auth:xyz789abc123
(integer) 1

# Delete auth session (cleanup)
> DEL auth:xyz789abc123
(integer) 1
```

### Decode JSON Values

```bash
# Get raw JSON
> GET user:abc123
"{\"user_id\":\"u-12345\",\"provider\":\"google\"}"

# Or use jq for pretty printing (from host)
redis-cli -p 6380 GET user:abc123 | jq .
{
  "user_id": "u-12345",
  "provider": "google",
  "created_at": 1730560000,
  "expires_at": 1730563600
}
```

### Search for Keys

```bash
# Find all sessions for a user
> SCAN 0 MATCH "user:*" COUNT 1000

# Find all auth sessions
> SCAN 0 MATCH "auth:*" COUNT 1000

# Find JWKS caches
> SCAN 0 MATCH "jwks:*" COUNT 100
```

### Delete Multiple Keys

```bash
# Delete all auth sessions (development only)
> EVAL "return redis.call('del', unpack(redis.call('keys', 'auth:*')))" 0

# Or use redis-cli with SCAN (production-safe)
redis-cli -p 6380 --scan --pattern "auth:*" | xargs redis-cli -p 6380 DEL
```

## Monitoring Commands

### Server Information

```bash
# General server info
> INFO
# Server
redis_version:7.0.5
os:Linux 5.15.0-1 x86_64
uptime_in_seconds:3600
# ... (lots of output)

# Specific sections
> INFO server
> INFO memory
> INFO stats
> INFO replication
> INFO cpu
> INFO keyspace

# Memory usage
> INFO memory
used_memory:2621440
used_memory_human:2.50M
used_memory_peak:3145728
used_memory_peak_human:3.00M
maxmemory:536870912
maxmemory_human:512.00M
```

### Statistics

```bash
# Total commands processed
> INFO stats | grep total_commands
total_commands_processed:12345

# Commands per second
> INFO stats | grep instantaneous
instantaneous_ops_per_sec:42

# Connection statistics
> INFO clients
connected_clients:5
client_recent_max_input_buffer:2
client_recent_max_output_buffer:0
```

### Slow Log

```bash
# Get last 10 slow commands
> SLOWLOG GET 10
1) 1) (integer) 0           # Unique ID
   2) (integer) 1730563200   # Unix timestamp
   3) (integer) 12000        # Execution time (microseconds)
   4) 1) "GET"               # Command
      2) "user:abc123"
   5) "127.0.0.1:54321"      # Client address

# Get slow log length
> SLOWLOG LEN
(integer) 42

# Reset slow log
> SLOWLOG RESET
OK
```

### Latency Monitoring

```bash
# Get latest latency events
> LATENCY LATEST
1) 1) "command"
   2) (integer) 1730563200
   3) (integer) 150
   4) (integer) 200

# Get latency history for event
> LATENCY HISTORY command

# Get latency doctor analysis
> LATENCY DOCTOR
Dave, I have observed latency spikes in this Redis instance.
You can use "LATENCY GRAPH" to visualize them.
```

### Client List

```bash
# List connected clients
> CLIENT LIST
id=1 addr=127.0.0.1:54321 fd=8 name= age=42 idle=0 flags=N db=0 sub=0 psub=0 multi=-1 qbuf=0 qbuf-free=0 obl=0 oll=0 omem=0 events=r cmd=client

# Kill specific client
> CLIENT KILL 127.0.0.1:54321
OK

# Set client name (for debugging)
> CLIENT SETNAME my-app-connection
OK

# Get current client name
> CLIENT GETNAME
"my-app-connection"
```

### Real-Time Monitoring

```bash
# Monitor all commands (DEVELOPMENT ONLY)
> MONITOR
OK
1730563200.123456 [0 127.0.0.1:54321] "GET" "user:abc123"
1730563201.234567 [0 127.0.0.1:54321] "SET" "user:abc123" "..."

# Stop monitoring: Ctrl+C
```

### Continuous Stats

```bash
# Live stats (updates every second)
redis-cli -p 6380 --stat
------- data ------ --------------------- load -------------------- - child -
keys       mem      clients blocked requests            connections
42         2.50M    5       0       12345 (+0)          10
42         2.50M    5       0       12350 (+5)          10
```

### Latency Testing

```bash
# Measure latency (Ctrl+C to stop)
redis-cli -p 6380 --latency
min: 0, max: 1, avg: 0.15 (123 samples)

# Latency histogram
redis-cli -p 6380 --latency-history
min: 0, max: 1, avg: 0.15 (123 samples) -- 10 seconds range

# Latency distribution
redis-cli -p 6380 --latency-dist
```

## Administrative Commands

### Database Management

```bash
# Select database (0-15)
> SELECT 1
OK

# Flush current database (DISABLED IN PRODUCTION)
> FLUSHDB
OK

# Flush all databases (DISABLED IN PRODUCTION)
> FLUSHALL
OK

# Get database size
> DBSIZE
(integer) 42
```

### Configuration

```bash
# Get configuration value
> CONFIG GET maxmemory
1) "maxmemory"
2) "536870912"

# Get all configuration
> CONFIG GET *

# Set configuration (runtime only - DISABLED IN PRODUCTION)
> CONFIG SET maxmemory 1073741824
OK

# Rewrite config file
> CONFIG REWRITE
OK
```

### ACL Management

```bash
# List all users
> ACL LIST
1) "user default on #... ~* &* +@all"
2) "user readonly on #... ~* &* +@read"

# Get user permissions
> ACL GETUSER sessionapp
 1) "flags"
 2) 1) "on"
 3) "passwords"
 4) 1) "..."
 5) "commands"
 6) "+get +set +del"

# Create user
> ACL SETUSER newuser on >password ~* +@read
OK

# Save ACLs
> ACL SAVE
OK

# View current user
> ACL WHOAMI
"default"
```

### Replication (if configured)

```bash
# View replication status
> INFO replication
role:master
connected_slaves:1
slave0:ip=10.0.1.2,port=6379,state=online,offset=12345

# Make replica of another server
> REPLICAOF 192.168.1.100 6379
OK

# Stop being replica
> REPLICAOF NO ONE
OK
```

## Troubleshooting

### Connection Issues

```bash
# Test connectivity
redis-cli -p 6380 ping
# Expected: PONG
# If fails: Redis not running or wrong port

# Check if Redis is running
docker ps | grep redis

# Check Redis logs
docker logs api-forge-redis-dev

# Check port mapping
docker port api-forge-redis-dev
```

### Authentication Failures

```bash
# Test authentication
redis-cli -p 6379 -a "password" ping
# Expected: PONG
# If fails: Wrong password

# Check password in secrets file
cat infra/secrets/keys/redis_password.txt

# Check Docker secret
docker exec api-forge-redis cat /run/secrets/redis_password
```

### Memory Issues

```bash
# Check memory usage
> INFO memory
used_memory_human:512.00M
maxmemory_human:512.00M  # At limit!

# Check eviction stats
> INFO stats | grep evicted
evicted_keys:42  # Keys being evicted

# Check memory by database
> INFO keyspace
db0:keys=1000,expires=800,avg_ttl=3600000
```

**Solutions**:
- Increase `maxmemory` in redis.conf
- Review session TTLs (reduce if too long)
- Enable eviction policy (if not already)
- Scale to larger instance

### Performance Issues

```bash
# Check latency
redis-cli -p 6380 --latency
min: 0, max: 50, avg: 2.5  # Elevated latency

# Check slow log
> SLOWLOG GET 10
# Look for expensive operations

# Check CPU usage
docker stats api-forge-redis-dev

# Check for blocking operations
> INFO stats | grep blocked_clients
blocked_clients:0
```

### Data Loss

```bash
# Check last save
> LASTSAVE
(integer) 1730560000

# Force save
> BGSAVE
Background saving started

# Check AOF status
> INFO persistence
aof_enabled:1
aof_last_write_status:ok
```

### Session Not Found

```bash
# Check if key exists
> EXISTS user:abc123
(integer) 0  # Session expired or deleted

# Check TTL
> TTL user:abc123
(integer) -2  # -2 = key doesn't exist, -1 = no TTL, >0 = seconds remaining

# Search for similar keys
> SCAN 0 MATCH "user:abc*" COUNT 100
```

## Best Practices

### 1. Use SCAN Instead of KEYS

```bash
# ✅ GOOD: Non-blocking scan
cursor=0
while true; do
  result=$(redis-cli -p 6380 SCAN $cursor MATCH "user:*" COUNT 100)
  cursor=$(echo "$result" | head -n1)
  keys=$(echo "$result" | tail -n+2)
  echo "$keys"
  [[ $cursor == "0" ]] && break
done

# ❌ BAD: Blocks server (disabled in production)
redis-cli -p 6380 KEYS "user:*"
```

### 2. Avoid MONITOR in Production

```bash
# ❌ BAD: Logs every command, impacts performance
> MONITOR

# ✅ GOOD: Use slow log instead
> SLOWLOG GET 10
```

### 3. Use Pipelining for Bulk Operations

```bash
# ✅ GOOD: Pipeline (1 network round-trip)
echo -e "SET key1 value1\nSET key2 value2\nSET key3 value3" | redis-cli -p 6380 --pipe

# ❌ BAD: Individual commands (3 network round-trips)
redis-cli -p 6380 SET key1 value1
redis-cli -p 6380 SET key2 value2
redis-cli -p 6380 SET key3 value3
```

### 4. Authenticate Securely

```bash
# ✅ GOOD: Password from file, suppressed warning
redis-cli -p 6379 --no-auth-warning -a "$(cat infra/secrets/keys/redis_password.txt)"

# ⚠️ WARNING: Password in command line (visible in process list)
redis-cli -p 6379 -a "password"

# ❌ BAD: Password in shell history
redis-cli -p 6379 -a "my-secret-password" GET key
```

### 5. Clean Up After Debugging

```bash
# Delete test keys
> DEL test:*

# Or use SCAN + DEL
redis-cli -p 6380 --scan --pattern "test:*" | xargs redis-cli -p 6380 DEL
```

### 6. Monitor Resource Usage

```bash
# Check memory before bulk operations
> INFO memory

# Monitor during operation
redis-cli -p 6380 --stat

# Check after operation
> INFO stats
```

### 7. Use Descriptive Client Names

```python
# In application code
redis_client = await redis.from_url(
    "redis://localhost:6379",
    client_name="fastapi-app"
)

# Now in Redis CLI
> CLIENT LIST
id=1 name=fastapi-app ...
```

### 8. Document Debugging Sessions

```bash
# Save CLI output to file
redis-cli -p 6380 INFO > redis-info-$(date +%Y%m%d-%H%M%S).txt

# Log commands to file
redis-cli -p 6380 MONITOR | tee redis-monitor.log
```

## Quick Reference

### Common Debugging Workflow

```bash
# 1. Check if Redis is running
docker ps | grep redis

# 2. Test connection
redis-cli -p 6380 ping

# 3. Check memory usage
redis-cli -p 6380 INFO memory

# 4. Check active sessions
redis-cli -p 6380 SCAN 0 MATCH "user:*" COUNT 100

# 5. Inspect specific session
redis-cli -p 6380 GET user:abc123

# 6. Check session TTL
redis-cli -p 6380 TTL user:abc123

# 7. Check slow log
redis-cli -p 6380 SLOWLOG GET 10

# 8. Check server stats
redis-cli -p 6380 INFO stats
```

### Useful One-Liners

```bash
# Count keys by pattern
redis-cli -p 6380 --scan --pattern "user:*" | wc -l

# Get all session IDs
redis-cli -p 6380 --scan --pattern "user:*"

# Delete all test keys
redis-cli -p 6380 --scan --pattern "test:*" | xargs redis-cli -p 6380 DEL

# Monitor live operations
redis-cli -p 6380 MONITOR | grep -i "user:"

# Check memory usage over time
watch -n 1 'redis-cli -p 6380 INFO memory | grep used_memory_human'
```

## Next Steps

- [Main Overview](./main.md) - Understand Redis architecture
- [Configuration](./configuration.md) - Configure Redis settings
- [Usage Guide](./usage.md) - Use Redis from FastAPI
- [Security](./security.md) - Secure Redis in production
