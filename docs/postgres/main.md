# PostgreSQL Database Service

## Overview

This application uses PostgreSQL as its primary relational database, providing persistent storage for all application data. The database service is implemented using SQLModel (built on SQLAlchemy) for ORM functionality, with comprehensive production optimizations for connection pooling, security, and performance.

## Key Features

- **Production-Grade Connection Pooling**: Configurable pool sizes with pre-ping validation and automatic connection recycling
- **SQLModel ORM**: Type-safe database operations with Pydantic integration
- **Multi-Database Support**: Separate databases for application data and Temporal workflows
- **TLS/SSL Encryption**: Full support for encrypted connections in production
- **Role-Based Access Control**: Three-role security pattern (owner, user, read-only)
- **Health Monitoring**: Built-in health checks and connection pool metrics
- **Development & Production Modes**: SQLite for development, PostgreSQL for production
- **Clean Architecture**: Repository pattern with entity-based data access

## Architecture

### Database Structure

The application uses multiple PostgreSQL databases:

```
┌─────────────────────────────────────────────┐
│         PostgreSQL Server (postgres:16)      │
├─────────────────────────────────────────────┤
│                                             │
│  ┌────────────────────────────────────┐   │
│  │  Application Database (appdb)       │   │
│  │  - User data                        │   │
│  │  - User identities (OIDC linking)   │   │
│  │  - Application entities             │   │
│  │  Schema: app                        │   │
│  └────────────────────────────────────┘   │
│                                             │
│  ┌────────────────────────────────────┐   │
│  │  Temporal Database (temporal)       │   │
│  │  - Workflow executions              │   │
│  │  - Activity state                   │   │
│  │  Schema: public                     │   │
│  └────────────────────────────────────┘   │
│                                             │
│  ┌────────────────────────────────────┐   │
│  │  Temporal Visibility DB             │   │
│  │  - Workflow search/filtering        │   │
│  │  Schema: public                     │   │
│  └────────────────────────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

### Connection Management

The application uses a singleton `DbSessionService` that manages:

1. **Engine Creation**: Single engine instance per application lifecycle
2. **Session Factory**: Creates new sessions for each transaction scope
3. **Connection Pool**: Maintains reusable connections with automatic lifecycle management
4. **Health Checks**: Validates database connectivity and pool status

```python
┌─────────────────────────────────────────┐
│        DbSessionService                  │
│  (Singleton, Application Lifetime)       │
├─────────────────────────────────────────┤
│                                          │
│  ┌──────────────────────────────────┐  │
│  │  SQLAlchemy Engine               │  │
│  │  - Connection pool               │  │
│  │  - Pool size: 20                 │  │
│  │  - Max overflow: 10              │  │
│  │  - Pre-ping validation           │  │
│  └──────────────────────────────────┘  │
│                                          │
│  Session Factory Methods:                │
│  • get_session() → Session              │
│  • session_scope() → Context Manager    │
│  • health_check() → bool                │
│  • get_pool_status() → dict             │
│                                          │
└─────────────────────────────────────────┘
           │
           │ Creates sessions per request
           ▼
┌─────────────────────────────────────────┐
│     SQLModel Session (Per Request)       │
├─────────────────────────────────────────┤
│  • Bound to engine's connection pool    │
│  • Transaction-scoped                   │
│  • Auto-commit on success               │
│  • Auto-rollback on error               │
│  • Closed after request                 │
└─────────────────────────────────────────┘
```

### ORM Layer (SQLModel)

```
Entity Layer (Domain Models)
    ↓
Repository Layer (Data Access)
    ↓
SQLModel Session
    ↓
SQLAlchemy Engine
    ↓
PostgreSQL Database
```

**Example Entity Structure:**
```python
# Entity (Domain Model)
class User(Entity):
    first_name: str
    last_name: str
    email: str | None

# Table (Database Model)
class UserTable(EntityTable, table=True):
    first_name: str
    last_name: str
    email: str | None

# Repository (Data Access)
class UserRepository:
    def __init__(self, session: Session):
        self._session = session
    
    def get(self, user_id: str) -> User | None
    def create(self, user: User) -> User
    def update(self, user: User) -> User
```

## Use Cases

### 1. Application Data Storage

The primary use case is storing all application data in the `appdb` database:

- **User Management**: User profiles, authentication state
- **User Identities**: OIDC provider linkage (Google, Microsoft, Keycloak)
- **Business Entities**: Application-specific domain objects
- **Audit Logs**: Timestamps and tracking via `created_at`/`updated_at` fields

**Schema Design:**
- Application data uses the `app` schema (not `public`)
- All tables inherit from `EntityTable` base class
- Auto-generated UUIDs for primary keys
- Automatic timestamp management

### 2. Session State (Indirect)

While sessions are primarily stored in Redis, the database stores:

- **User Identity Mapping**: Links OIDC subjects to application users
- **Session Validation**: User existence checks during authentication
- **Profile Data**: User information displayed after login

### 3. Temporal Workflow Persistence

Separate databases (`temporal` and `temporal_visibility`) store:

- Workflow execution history
- Activity task state
- Search and visibility indexes
- Workflow versioning and replay data

### 4. Development Testing

In development mode, the application can use SQLite instead of PostgreSQL:

```python
# Development (SQLite)
DATABASE_URL=sqlite:///./database.db

# Production (PostgreSQL)
DATABASE_URL=postgresql://appuser:password@postgres:5432/appdb
```

## Connection Pooling

### Pool Configuration

The application uses SQLAlchemy's connection pooling with production-optimized settings:

```yaml
# config.yaml
database:
  pool_size: 20              # Base pool size
  max_overflow: 10           # Additional connections (total: 30)
  pool_timeout: 30           # Wait time for available connection (seconds)
  pool_recycle: 1800         # Recycle connections after 30 minutes
```

### Connection Lifecycle

```
Request Start
    ↓
Get Session from Pool
    ↓
[Connection Available?]
    ├─ Yes → Use Existing Connection
    │         ↓
    │     Execute Query
    │         ↓
    │     Commit/Rollback
    │         ↓
    │     Return to Pool
    │
    └─ No → [Pool Size < max_overflow?]
            ├─ Yes → Create New Connection
            │         ↓
            │     Execute Query
            │         ↓
            │     Add to Pool
            │
            └─ No → Wait (pool_timeout: 30s)
                     ↓
                 [Timeout?]
                     ├─ Connection Available → Use It
                     └─ Still None → Raise Exception
```

### Pre-Ping Validation

Every connection is validated before use:

```python
pool_pre_ping: True  # Execute "SELECT 1" before each checkout
```

**Benefits:**
- Detects stale connections (network issues, database restarts)
- Automatic reconnection on failure
- No failed queries due to dead connections

### Connection Recycling

Connections are automatically recycled after 30 minutes:

```python
pool_recycle: 1800  # 30 minutes in seconds
```

**Benefits:**
- Prevents issues with long-lived connections
- Works around database-side connection timeouts
- Ensures fresh connections for long-running applications

## Database Initialization

### Development Mode

```bash
# 1. Start development environment (includes PostgreSQL)
uv run cli dev start-env

# 2. Wait for services to be healthy (30-60 seconds)
uv run cli dev status

# 3. Initialize database (creates tables)
uv run init-db
```

### Manual Table Creation

The `init_db.py` script uses SQLModel's metadata to create all tables:

```python
from sqlmodel import SQLModel
from src.app.core.services.database.db_manage import DbManageService

# Import all table models (required for metadata registration)
from src.app.entities.core.user import UserTable
from src.app.entities.core.user_identity import UserIdentityTable

# Create all tables
db_manage_service = DbManageService()
db_manage_service.create_all()
```

**Important:** All table models must be imported before calling `create_all()` to ensure they're registered in SQLModel's metadata registry.

### No Built-In Migrations

**Current State:** The application uses direct table creation via SQLModel, not a migration system like Alembic.

**Implications:**
- Schema changes require manual migration scripting
- Production deployments need careful schema versioning
- Consider adding Alembic for future schema migrations

**Recommendation:** For production use, implement Alembic migrations:

```bash
# Future enhancement
alembic init alembic/
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

## Performance Characteristics

### Connection Pool Performance

| Scenario | Behavior | Performance Impact |
|----------|----------|-------------------|
| Low traffic (< 20 concurrent) | Uses base pool only | Minimal overhead, instant connections |
| Medium traffic (20-30 concurrent) | Uses overflow connections | Slight latency for new connections |
| High traffic (> 30 concurrent) | Blocks until timeout | Requests wait up to 30s, then fail |
| Connection failure | Pre-ping detects, auto-reconnects | One extra round-trip per connection |
| Long-running app | Connections recycled every 30 min | Prevents stale connection issues |

### Query Performance

**PostgreSQL Optimizations:**
- JIT compilation disabled for small queries (lower memory usage)
- `random_page_cost: 1.1` (optimized for SSD storage)
- Connection pooling reduces connection overhead
- Query timeout: 30 seconds (prevents runaway queries)

**SQLModel/SQLAlchemy Optimizations:**
- `expire_on_commit: False` - Objects remain accessible after commit
- `autoflush: True` - Queries see pending changes
- `autocommit: False` - Explicit transaction control

### Typical Latencies

| Operation | Latency (Development) | Latency (Production) |
|-----------|----------------------|---------------------|
| Get session from pool | < 1ms | < 1ms |
| Simple SELECT by ID | 1-5ms | 1-3ms |
| INSERT single row | 2-10ms | 2-5ms |
| UPDATE single row | 2-10ms | 2-5ms |
| Transaction commit | 5-20ms | 3-10ms |
| Health check (SELECT 1) | 1-5ms | 1-3ms |

## Error Handling

### Connection Errors

```python
try:
    with db_session_service.session_scope() as session:
        # Database operations
        user = session.get(UserTable, user_id)
except OperationalError as e:
    # Database connection failed
    logger.error("Database connection failed", extra={
        "error_type": type(e).__name__,
        "error_message": str(e),
    })
except TimeoutError as e:
    # Connection pool timeout
    logger.error("Connection pool exhausted", extra={
        "error_type": type(e).__name__,
        "pool_status": db_session_service.get_pool_status(),
    })
```

### Transaction Errors

The `session_scope()` context manager handles automatic rollback:

```python
@contextmanager
def session_scope(self) -> Iterator[Session]:
    db = self.get_session()
    try:
        yield db
        db.commit()  # Auto-commit on success
    except Exception as e:
        db.rollback()  # Auto-rollback on error
        logger.error("Database transaction failed", extra={
            "error_type": type(e).__name__,
            "error_message": str(e),
        })
        raise
    finally:
        db.close()  # Always close session
```

## Monitoring & Observability

### Health Checks

```python
# Check database connectivity
is_healthy = db_session_service.health_check()

# Returns: True if "SELECT 1" succeeds, False otherwise
```

**Use Cases:**
- Kubernetes liveness/readiness probes
- Load balancer health checks
- Monitoring dashboard status

### Connection Pool Metrics

```python
pool_status = db_session_service.get_pool_status()

# Returns:
{
    "size": 20,           # Total pool size
    "checked_in": 18,     # Available connections
    "checked_out": 2,     # In-use connections
    "overflow": 0,        # Overflow connections created
    "invalid": 0          # Failed connections
}
```

**Monitoring Recommendations:**

| Metric | Alert Threshold | Action |
|--------|----------------|--------|
| `checked_out` | > 90% of pool_size | Increase pool size |
| `overflow` | > 0 consistently | Increase base pool_size |
| `invalid` | > 0 | Investigate connection failures |
| Health check failures | > 3 consecutive | Alert operations team |

### Structured Logging

All database operations log structured data:

```python
logger.info("Database engine initialized", extra={
    "pool_size": 20,
    "max_overflow": 10,
    "pool_timeout": 30,
    "pool_recycle": 1800,
})

logger.error("Database transaction failed", extra={
    "error_type": "IntegrityError",
    "error_message": "duplicate key value violates unique constraint",
})
```

## Security Features

### Authentication

- **SCRAM-SHA-256**: Modern password hashing (no MD5)
- **Docker Secrets**: Passwords loaded from files, never environment variables
- **Connection Pooling**: Reduces authentication overhead

### TLS/SSL Encryption

Production deployments enforce encrypted connections:

```python
# Connection string with SSL mode
DATABASE_URL=postgresql://appuser:password@postgres:5432/appdb?sslmode=require

# PostgreSQL configuration
ssl = on
ssl_min_protocol_version = 'TLSv1.2'
ssl_max_protocol_version = 'TLSv1.3'
```

### Role-Based Access Control

Three-role security pattern:

1. **Owner (NOLOGIN)**: `appowner` - Database and schema owner, no login capability
2. **Application User (LOGIN)**: `appuser` - Full CRUD access to application tables
3. **Read-Only User (LOGIN)**: `backupuser` - Read-only access for backups/reporting

```sql
-- Example privilege grants
GRANT USAGE ON SCHEMA app TO appuser;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO appuser;
GRANT SELECT ON ALL TABLES IN SCHEMA app TO backupuser;
```

### Network Isolation

**Development:**
- Binds to port 5433 (not default 5432)
- Docker network isolation (`dev-network`)
- Password: `devpass` (hardcoded, acceptable for dev)

**Production:**
- Binds to localhost only: `127.0.0.1:5432`
- Backend Docker network only (`application_internal`)
- pg_hba.conf restricts connections to private subnets
- Requires TLS for all network connections

## Comparison: Development vs Production

| Feature | Development | Production |
|---------|------------|------------|
| **Database** | PostgreSQL 16-alpine OR SQLite | PostgreSQL 16-alpine |
| **Port** | 5433 | 5432 (localhost only) |
| **Password** | Hardcoded `devpass` | Docker secrets from files |
| **TLS/SSL** | Disabled | Required (TLS 1.2+) |
| **Connection Pool** | Smaller (pool_size: 5) | Larger (pool_size: 20) |
| **Logging** | Verbose (echo: True) | Minimal (echo: False) |
| **Network** | `dev-network` bridge | `application_internal` bridge |
| **Volume** | `postgres_data_dev` | `./data/postgres` (bind mount) |
| **Authentication** | Password only | SCRAM-SHA-256 + TLS |
| **Init Scripts** | None | Role setup, database creation |
| **Health Checks** | Basic | Comprehensive with retries |
| **Backups** | None | Automated with retention |
| **Monitoring** | Basic logs | Structured logs + metrics |

## Best Practices

### 1. Session Management

**✅ DO: Use context managers**
```python
with db_session_service.session_scope() as session:
    user = session.get(UserTable, user_id)
    # Automatic commit on success, rollback on error
```

**❌ DON'T: Forget to close sessions**
```python
session = db_session_service.get_session()
user = session.get(UserTable, user_id)
session.commit()
# Missing: session.close() - connection leak!
```

### 2. Repository Pattern

**✅ DO: Use repositories for data access**
```python
class UserRepository:
    def __init__(self, session: Session):
        self._session = session
    
    def get(self, user_id: str) -> User | None:
        row = self._session.get(UserTable, user_id)
        if row is None:
            return None
        return User.model_validate(row, from_attributes=True)
```

**❌ DON'T: Access tables directly in API routes**
```python
@router.get("/users/{user_id}")
async def get_user(user_id: str, session: Session = Depends(get_session)):
    # Bad: Business logic in route handler
    user = session.get(UserTable, user_id)
    return user
```

### 3. Entity Validation

**✅ DO: Validate domain models, persist table models**
```python
# 1. Validate input with domain model
user = User(first_name="John", last_name="Doe", email="john@example.com")

# 2. Convert to table model for persistence
user_table = UserTable.model_validate(user, from_attributes=True)
session.add(user_table)
session.commit()
```

**❌ DON'T: Mix domain and persistence concerns**
```python
# Bad: Directly validating table models from user input
user_table = UserTable(**request_data)  # No validation!
session.add(user_table)
```

### 4. Error Handling

**✅ DO: Handle specific database exceptions**
```python
from sqlalchemy.exc import IntegrityError, OperationalError

try:
    session.add(user_table)
    session.commit()
except IntegrityError:
    # Handle duplicate key, constraint violations
    logger.warning("User already exists")
    raise HTTPException(status_code=409, detail="User already exists")
except OperationalError:
    # Handle connection failures
    logger.error("Database connection failed")
    raise HTTPException(status_code=503, detail="Database unavailable")
```

### 5. Testing

**✅ DO: Use session_scope for test isolation**
```python
@pytest.fixture
def db_session():
    with db_session_service.session_scope() as session:
        yield session
        # Automatic rollback in tests
```

## Troubleshooting

### Issue: Connection Pool Exhausted

**Symptoms:**
```
TimeoutError: QueuePool limit of size 20 overflow 10 reached, 
connection timed out, timeout 30
```

**Solutions:**
1. Increase pool size: `pool_size: 30` in config.yaml
2. Increase max overflow: `max_overflow: 20`
3. Check for connection leaks (missing `session.close()`)
4. Review long-running queries blocking connections

### Issue: Stale Connection Errors

**Symptoms:**
```
OperationalError: server closed the connection unexpectedly
```

**Solutions:**
1. Verify `pool_pre_ping: True` is enabled (it is by default)
2. Reduce `pool_recycle` time: `pool_recycle: 900` (15 minutes)
3. Check network stability between app and database

### Issue: Slow Query Performance

**Symptoms:**
- Queries taking > 1 second for simple operations
- High CPU usage on database server

**Solutions:**
1. Add indexes to frequently queried columns
2. Use `EXPLAIN ANALYZE` to examine query plans
3. Enable query logging: `log_min_duration_statement: 1000` (1 second)
4. Review `random_page_cost` and `effective_cache_size` settings

### Issue: Migration Conflicts

**Current State:** No migration system exists (SQLModel creates tables directly)

**Temporary Solution:**
1. Manually create migration SQL scripts
2. Version scripts: `migrations/001_initial_schema.sql`
3. Apply manually before deployment

**Permanent Solution:**
Implement Alembic:
```bash
# Add Alembic dependency
uv add alembic

# Initialize Alembic
alembic init alembic/

# Generate migration from models
alembic revision --autogenerate -m "Add user table"

# Apply migration
alembic upgrade head
```

### Issue: Development Database Not Initializing

**Symptoms:**
```
relation "usertable" does not exist
```

**Solutions:**
1. Ensure dev environment is running: `uv run cli dev status`
2. Run database initialization: `uv run init-db`
3. Check all table models are imported in `init_db.py`
4. Verify DATABASE_URL environment variable is correct

## Related Documentation

- [Configuration Guide](./configuration.md) - Database connection settings and environment variables
- [Usage Guide](./usage.md) - Code examples and repository patterns
- [Security Guide](./security.md) - TLS setup, authentication, and access control
- [Migrations Guide](./migrations.md) - Schema versioning and Alembic integration
- [Production Deployment](../PRODUCTION_DEPLOYMENT.md) - Production PostgreSQL setup
- [Secrets Management](../secrets_management.md) - Database password management
