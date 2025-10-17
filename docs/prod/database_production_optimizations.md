# Database Production Optimizations Guide

## Overview

The `DbSessionService` class has been optimized for production use with comprehensive connection pooling, monitoring, and database-specific optimizations.

## Key Production Optimizations Applied

### 1. Connection Pooling Configuration

```python
# All values configurable via config.yaml
pool_size: 20              # Base pool size
max_overflow: 10           # Additional connections beyond base pool
pool_timeout: 30           # Seconds to wait for connection
pool_recycle: 1800         # Recycle connections after 30 minutes
```

**Production Benefits:**
- Prevents connection exhaustion under load
- Automatically manages connection lifecycle
- Configurable based on application needs

### 2. Connection Validation

```python
pool_pre_ping: True        # Validate connections before use
```

**Production Benefits:**
- Detects stale connections before queries fail
- Automatic reconnection on connection loss
- Improved reliability in cloud environments

### 3. Environment-Specific Logging

```python
echo: False (production)    # Disable SQL logging for performance
echo: True (development)    # Enable SQL logging for debugging
echo_pool: True (dev only)  # Pool-level logging
```

**Production Benefits:**
- Reduced I/O overhead in production
- Comprehensive debugging in development
- Structured logging for monitoring

### 4. PostgreSQL-Specific Optimizations

```python
server_settings: {
    "jit": "off",                           # Disable JIT for small queries
    "application_name": "production_api",   # Identify connections
    "random_page_cost": "1.1",             # SSD optimization
    "effective_cache_size": "1GB"          # Memory optimization
}
command_timeout: 30                        # Query timeout
```

**Production Benefits:**
- Optimized for SSD storage
- Connection identification for monitoring
- Query timeout protection
- Memory usage optimization

### 5. Session Configuration

```python
expire_on_commit: False    # Prevent lazy loading issues
autoflush: True           # Auto-flush before queries
autocommit: False         # Explicit transaction control
```

**Production Benefits:**
- Predictable object behavior after commits
- Consistent query execution
- Explicit transaction boundaries

### 6. Error Handling & Monitoring

```python
# Structured error logging
logger.error("Database transaction failed", extra={
    "error_type": type(e).__name__,
    "error_message": str(e),
})

# Health check endpoint
def health_check() -> bool

# Pool monitoring
def get_pool_status() -> dict
```

**Production Benefits:**
- Detailed error tracking for debugging
- Health check for load balancers
- Pool metrics for monitoring dashboards

## Recommended Configuration Values

### Small Application (< 100 concurrent users)
```yaml
database:
  pool_size: 10
  max_overflow: 5
  pool_timeout: 20
  pool_recycle: 1800
```

### Medium Application (100-1000 concurrent users)
```yaml
database:
  pool_size: 20
  max_overflow: 10
  pool_timeout: 30
  pool_recycle: 1800
```

### Large Application (> 1000 concurrent users)
```yaml
database:
  pool_size: 50
  max_overflow: 20
  pool_timeout: 10
  pool_recycle: 900
```

## Additional Production Considerations

### 1. Database Server Configuration

**PostgreSQL production settings:**
```sql
-- Memory settings
shared_buffers = 25% of RAM
effective_cache_size = 75% of RAM
work_mem = 4MB

-- Connection settings
max_connections = 200
idle_in_transaction_session_timeout = 300000

-- Performance settings
random_page_cost = 1.1  # For SSD
checkpoint_completion_target = 0.9
```

### 2. Connection Pool Monitoring

Monitor these key metrics:
- Pool utilization percentage
- Connection wait times
- Failed connection attempts
- Pool overflow events

### 3. Query Performance

- Enable `log_min_duration_statement` in PostgreSQL for slow query detection
- Use connection pooling at the application level (already implemented)
- Consider read replicas for read-heavy workloads

### 4. Security Considerations

- Use connection string without passwords (implemented)
- Read passwords from Docker secrets or environment variables (implemented)
- Enable SSL/TLS for database connections in production
- Use least-privilege database user accounts

### 5. Backup and Recovery

- Regular automated backups
- Point-in-time recovery capability
- Backup restoration testing
- Database replication for high availability

## Usage Examples

### Basic Usage
```python
db_service = DbSessionService()

# Get a session
with db_service.session_scope() as session:
    # Your database operations
    result = session.query(MyModel).all()
```

### Health Check Integration
```python
# In your FastAPI health endpoint
@app.get("/health")
async def health_check():
    db_healthy = db_service.health_check()
    return {
        "status": "healthy" if db_healthy else "unhealthy",
        "database": "connected" if db_healthy else "disconnected"
    }
```

### Monitoring Integration
```python
# In your metrics endpoint
@app.get("/metrics")
async def metrics():
    pool_status = db_service.get_pool_status()
    return {
        "database_pool": pool_status,
        "pool_utilization": pool_status["checked_out"] / pool_status["size"]
    }
```

## Performance Testing

Before deploying to production:

1. **Load Testing**: Test with expected concurrent user load
2. **Connection Pool Sizing**: Monitor pool utilization under load
3. **Query Performance**: Profile slow queries and optimize
4. **Failover Testing**: Test database connection recovery
5. **Resource Monitoring**: Monitor CPU, memory, and I/O usage

## Troubleshooting Common Issues

### Connection Pool Exhaustion
- Increase `pool_size` or `max_overflow`
- Check for connection leaks (unclosed sessions)
- Monitor long-running transactions

### Slow Queries
- Enable query logging
- Add database indexes
- Optimize query patterns
- Consider connection pooling at database level

### Connection Timeouts
- Increase `pool_timeout`
- Check network latency
- Verify database server capacity
- Monitor connection establishment times