# Production PostgreSQL Documentation

> Hardened PostgreSQL 16 for containers: secure defaults, practical tuning, and operational workflows.

## At a glance

| Area           | Defaults / Highlights                                                                      |
| -------------- | ------------------------------------------------------------------------------------------ |
| Auth           | SCRAM-SHA-256; secrets via Docker S### 7.4 Certificate renewal (Let's Encrypt on host/sidecar)

```bash
# Renew certificates
certbot renew --quiet

# Copy new certificates to Docker volume mount location
cp /etc/letsencrypt/live/yourdomain/fullchain.pem ./certs/server.crt
cp /etc/letsencrypt/live/yourdomain/privkey.pem ./certs/server.key

# Set proper permissions
chmod 600 ./certs/server.key
chmod 644 ./certs/server.crt
sudo chown 999:999 ./certs/server.*

# Reload PostgreSQL configuration
docker exec app_data_postgres_db \
  pg_ctl reload -D /var/lib/postgresql/data

# Verify new certificates are loaded
docker exec app_data_postgres_db \
  psql -U appuser -d appdb -c "SELECT * FROM pg_stat_ssl LIMIT 1;"
```e-based)                                     |
| TLS            | `ssl=on`, TLS 1.2+ (1.3 supported), strong ciphers/ciphersuites                            |
| Networking     | `listen_addresses='*'` (container network), `pg_hba.conf` locked to private CIDRs over TLS |
| Performance    | sane buffers, WAL/checkpoints tuned, planner I/O hints                                     |
| Observability  | slow-query logging, `pg_stat_statements`                                                   |
| Ops            | healthchecks, backups, init scripts, least-privilege user                                  |
| Images         | `postgres:16-alpine` base, lean extra packages                                             |
| Deploy targets | Docker/Compose, fly.io, Railway, Render (examples included)                                |

---

## 1) Security

> **Security Enhancements Applied**: This configuration includes explicit TLS version constraints (TLS 1.2+), enhanced logging with detailed error reporting, row-level security enablement, and streamlined container image without unnecessary extensions.

### 1.1 Authentication & Secrets

* **Password hashing**: SCRAM-SHA-256 (no MD5).
* **Secret storage**: Docker secrets via files (`postgres_password`, `backup_password`).
* **Custom entrypoint**: Reads secrets as root, then chains to PostgreSQL entrypoint.
* **Permissions**: secret files `600`.

```yaml
# docker-compose (example excerpt)
services:
  postgres:
    image: your-app-postgres:latest
    secrets:
      - postgres_password
      - backup_password
secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
  backup_password:
    file: ./secrets/backup_password.txt
```

### 1.2 TLS / SSL

> Use real certificates for anything public or regulated. Self-signed is acceptable only for fully private, internal traffic where you knowingly disable verification in clients.

**PostgreSQL settings (excerpt):**

```conf
ssl = on
ssl_min_protocol_version = 'TLSv1.2'
ssl_max_protocol_version = 'TLSv1.3'
ssl_prefer_server_ciphers = on
ssl_ciphers = 'HIGH:!aNULL:!MD5'         # TLS ≤ 1.2
ssl_cert_file = 'server.crt'             # absolute path if outside PGDATA
ssl_key_file  = 'server.key'
password_encryption = scram-sha-256
row_security = on                        # Enable row-level security
```

**File ownership & perms**

* `server.key`: `600`, owner `postgres` (UID/GID 999)
* `server.crt`: `644`, owner `postgres`

**Production certificate options**

* **Let’s Encrypt** (public endpoints): obtain on host/sidecar, mount into DB container R/O, set absolute paths in `postgresql.conf`, `pg_ctl reload` after renewals.
* **Internal/Corporate CA**: mount `ca.crt` and optionally require client certs (`clientcert=verify-ca`) for specific roles.
* **AWS RDS**: RDS manages server certs; clients trust the RDS CA bundle. (If using RDS, most of this repository’s TLS setup won’t apply.)

### 1.3 Network policy (pg_hba.conf)

Recommend allowing only local and private ranges, and requiring TLS (`hostssl`) for networked access:

```
# Local sockets
local   all             postgres                                peer
local   all             all                                     scram-sha-256

# Loopback
host    all             all             127.0.0.1/32            scram-sha-256
host    all             all             ::1/128                 scram-sha-256

# Private networks over TLS
hostssl all             all             10.0.0.0/8              scram-sha-256
hostssl all             all             172.16.0.0/12           scram-sha-256
hostssl all             all             192.168.0.0/16          scram-sha-256

# Deny everything else
host    all             all             0.0.0.0/0               reject
```

### 1.4 Roles & privileges

* **DB**: `appdb`
* **Main Role**: `appuser` (full app privileges)
* **Backup Role**: `backup` (read-only access for backups)
* **Schema**: `app`
* **Extensions**: `pgcrypto`, `uuid-ossp`, `pg_stat_statements`

**Backup User Setup:**
- System user: Created in container for backup operations
- Database user: Read-only access to `app` schema
- Password: Managed via Docker secrets (`backup_password`)

Restrict default privileges to the `app` schema.

---

## 2) Performance

### 2.1 Memory

```conf
shared_buffers = 256MB
work_mem = 4MB
maintenance_work_mem = 64MB
effective_cache_size = 1GB
```

### 2.2 WAL & checkpoints

```conf
wal_level = replica
max_wal_size = 1GB
min_wal_size = 80MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
```

### 2.3 Planner & I/O

```conf
random_page_cost = 1.1
effective_io_concurrency = 200
```

### 2.4 Connections & logging

```conf
max_connections = 100
superuser_reserved_connections = 3

shared_preload_libraries = 'pg_stat_statements'
log_min_duration_statement = 1000      # >1s
log_line_prefix = '%t [%p-%l] %q%u@%d '  # Improved log formatting
log_statement = 'ddl'                   # Log DDL statements
log_min_error_statement = error         # Log error statements
log_checkpoints = on
log_lock_waits = on
log_temp_files = 0
log_connections = on
log_disconnections = on
```

---

## 3) Container Image & Layout

### 3.1 Dockerfile (alpine)

```dockerfile
FROM postgres:16-alpine

# Security: Install only essential packages
RUN apk add --no-cache bash curl openssl && rm -rf /var/cache/apk/*

# Create backup directories
RUN mkdir -p /var/lib/postgresql/backups && \
    chown postgres:postgres /var/lib/postgresql/backups

# Copy configurations and scripts
COPY postgresql.conf /tmp/postgresql.conf
COPY pg_hba.conf /tmp/pg_hba.conf
COPY init-scripts/ /docker-entrypoint-initdb.d/
COPY backup-scripts/ /usr/local/bin/
COPY docker-entrypoint-wrapper.sh /usr/local/bin/docker-entrypoint-wrapper.sh

# Set permissions
RUN chmod +x /docker-entrypoint-initdb.d/*.sh && \
    chmod +x /usr/local/bin/*.sh

ENV POSTGRES_DB=appdb \
    POSTGRES_USER=appuser \
    POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password \
    POSTGRES_INITDB_ARGS="--auth-host=scram-sha-256 --data-checksums" \
    POSTGRES_HOST_AUTH_METHOD=scram-sha-256

# Use custom entrypoint wrapper for Docker secrets
ENTRYPOINT ["/usr/local/bin/docker-entrypoint-wrapper.sh"]
CMD ["postgres"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" || exit 1
```

**Key Features:**
- **Custom entrypoint wrapper**: Reads Docker secrets as root before user switch
- **Security hardened**: Minimal packages, no postgresql-contrib
- **Backup user**: Created during initialization for read-only database access

### 3.2 Volumes & permissions

* **Data**: `/var/lib/postgresql/data` (PGDATA)
* **Backups**: `/var/lib/postgresql/backups`

```bash
# Host directories (handled automatically by docker-compose)
mkdir -p ./data/postgres ./data/postgres-backups

# Permissions are managed automatically by Docker
# If manual adjustment needed:
# sudo chown -R 999:999 ./data/postgres
```

---

## 4) Build & Deploy

### 4.1 Build

```bash
# Check Docker version
docker --version

# Build using docker-compose (recommended)
docker-compose -f docker-compose.prod.yml build postgres

# Or build directly with Docker
docker build -t app_data_postgres_image .
docker images | grep app_data_postgres_image
```

### 4.2 Deploy (Compose)

```bash
# Create required directories and secrets
mkdir -p data/postgres data/postgres-backups secrets
echo "SuperSecurePassword" > secrets/postgres_password.txt
echo "BackupUserPassword" > secrets/backup_password.txt
chmod 600 secrets/*

# Start PostgreSQL service
docker-compose -f docker-compose.prod.yml up -d postgres
docker-compose -f docker-compose.prod.yml logs -f postgres
docker-compose -f docker-compose.prod.yml ps postgres
```

**Database Reset Script:**
```bash
# Complete database cleanup (removes all data!)
./reset_database.sh

# Start fresh after reset
docker-compose -f docker-compose.prod.yml up postgres
```

### 4.3 Verify

```bash
# Service readiness
docker exec app_data_postgres_db pg_isready -U appuser -d appdb

# SSL enabled?
POSTGRES_PASSWORD=$(cat secrets/postgres_password.txt)
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" app_data_postgres_db \
  psql -U appuser -d appdb -c "SHOW ssl;"

# Test main application user
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" app_data_postgres_db \
  psql -U appuser -d appdb -c "SELECT current_user, current_database();"

# Test backup user (read-only)
BACKUP_PASSWORD=$(cat secrets/backup_password.txt)
docker exec -e PGPASSWORD="$BACKUP_PASSWORD" app_data_postgres_db \
  psql -U backup -d appdb -c "SELECT current_user, current_database();"

# Verify extensions installed
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" app_data_postgres_db \
  psql -U appuser -d appdb -c \
  "SELECT name, installed_version FROM pg_available_extensions WHERE installed_version IS NOT NULL ORDER BY name;"

# Test backup user cannot write (should fail)
docker exec -e PGPASSWORD="$BACKUP_PASSWORD" app_data_postgres_db \
  psql -U backup -d appdb -c "CREATE TABLE test_readonly_check (id SERIAL);" 2>/dev/null && echo "ERROR: Backup user can write!" || echo "✓ Backup user is read-only"
```

---

## 5) Provider-Specific Examples

> These examples assume **internal-only** DB traffic inside the provider’s private network. For public access or compliance, use real certificates and strict client validation.

### 5.1 fly.io

**TLS handled by fly proxy; internal app connects over private network.**

```toml
# fly.toml
[env]
  POSTGRES_SSL_MODE = "require"                 # enforce encryption
  POSTGRES_SSL_CERT_VALIDATION = "none"        # internal-only, self-signed OK

[[services]]
  internal_port = 5432
  protocol = "tcp"
  # If exposing externally, fly proxy can terminate TLS:
  [[services.ports]]
    port = 5432
    handlers = ["pg_tls"]       # fly handles TLS termination
```

**Client connection string (internal):**

```
postgresql://appuser:${POSTGRES_PASSWORD}@postgres:5432/appdb?sslmode=require
```

* For public access, replace with real certs and `sslmode=verify-full`.

### 5.2 Railway

**Railway typically provides service-to-service private networking.**

```dockerfile
# Accept self-signed inside private network; still require TLS on the wire
ENV POSTGRES_SSL_MODE=require
ENV POSTGRES_SSL_CERT_VALIDATION=none
```

**Node/pg example (internal-only):**

```js
ssl: { require: true, rejectUnauthorized: false }
```

### 5.3 Render

**Private services can talk over Render’s internal network; public endpoints should use managed TLS and verified certs.**

```dockerfile
ENV POSTGRES_SSL_MODE=require
ENV POSTGRES_SSL_CERT_VALIDATION=none
```

> **When to upgrade to proper certs** on these platforms:
>
> * External clients (mobile/3rd-party), cross-region/provider,
> * Regulated workloads (HIPAA, SOC2, PCI-DSS),
> * Zero-trust/service mesh with mTLS,
> * Multi-tenant isolation requirements.

---

## 6) Configuration Files (in this repo)

* `postgresql.conf` – core tuning, TLS, logging.
* `pg_hba.conf` – network policy (prefer `hostssl` for private ranges).
* `docker-entrypoint-wrapper.sh` – custom entrypoint for Docker secrets handling.
* `init-scripts/`
  * `01-apply-configs.sh` – copies configs into PGDATA on first init.
  * `01-init-db.sh` – creates DB, roles, schema, extensions, and backup user.
* `reset_database.sh` – comprehensive cleanup script for development/testing.

---

## 7) Operations

### 7.1 Health & status

```bash
# Check service status
docker-compose -f docker-compose.prod.yml ps postgres

# Check PostgreSQL readiness
docker exec app_data_postgres_db pg_isready -U appuser -d appdb

# View recent logs
docker-compose -f docker-compose.prod.yml logs --tail=50 postgres

# Check resource usage
docker stats app_data_postgres_db --no-stream
```

### 7.2 Monitoring

```sql
-- Enable pg_stat_statements (if not already enabled)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Top slow queries
SELECT query, mean_exec_time, calls, total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Database sizes
SELECT pg_size_pretty(pg_database_size('appdb')) AS database_size;

-- Table sizes in app schema
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'app'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Connection counts by state
SELECT state, count(*) AS connections
FROM pg_stat_activity 
GROUP BY state
ORDER BY connections DESC;

-- Active SSL connections
SELECT pid, ssl, version, cipher 
FROM pg_stat_ssl 
WHERE ssl IS TRUE;

-- Cache hit ratios (should be > 99%)
SELECT 
    schemaname,
    tablename,
    heap_blks_hit::float / (heap_blks_hit + heap_blks_read) * 100 AS cache_hit_ratio
FROM pg_statio_user_tables
WHERE heap_blks_hit + heap_blks_read > 0
ORDER BY cache_hit_ratio ASC;
```

**Run monitoring queries:**
```bash
# Execute monitoring queries
POSTGRES_PASSWORD=$(cat secrets/postgres_password.txt)
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" app_data_postgres_db \
  psql -U appuser -d appdb -c "SELECT query, mean_exec_time, calls FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 5;"
```

### 7.3 Backups

```bash
# Using backup user for database dumps (recommended)
BACKUP_PASSWORD=$(cat secrets/backup_password.txt)
docker exec -e PGPASSWORD="$BACKUP_PASSWORD" app_data_postgres_db \
  pg_dump -U backup -d appdb --schema=app > backup_$(date +%Y%m%d_%H%M%S).sql

# Full database dump using main user
POSTGRES_PASSWORD=$(cat secrets/postgres_password.txt)
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" app_data_postgres_db \
  pg_dump -U appuser -d appdb > full_backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from SQL dump
docker exec -i app_data_postgres_db \
  bash -c "PGPASSWORD='$POSTGRES_PASSWORD' psql -U appuser -d appdb" < backup_file.sql

# Traditional backup scripts (if available in container)
docker exec app_data_postgres_db ls -la /usr/local/bin/backup-*.sh 2>/dev/null || echo "No backup scripts found"

# Test backup user permissions (should fail for write operations)
docker exec -e PGPASSWORD="$BACKUP_PASSWORD" app_data_postgres_db \
  psql -U backup -d appdb -c "CREATE TABLE test_table (id SERIAL);" 2>&1 | grep -q "permission denied" && echo "✓ Backup user is read-only" || echo "⚠ Backup user has write access"
```

### 7.4 Certificate renewal (Let’s Encrypt on host/sidecar)

```bash
certbot renew --quiet
cp /etc/letsencrypt/live/yourdomain/fullchain.pem /path/to/certs/server.crt
cp /etc/letsencrypt/live/yourdomain/privkey.pem   /path/to/certs/server.key
chmod 600 /path/to/certs/server.key
chmod 644 /path/to/certs/server.crt
chown 999:999 /path/to/certs/server.*
docker exec postgres_container pg_ctl reload -D /var/lib/postgresql/data
```

---

## 8) Troubleshooting

**Connection refused**

```bash
# Check service status
docker-compose -f docker-compose.prod.yml ps postgres

# Check container logs
docker-compose -f docker-compose.prod.yml logs postgres

# Test network connectivity
docker exec app_data_postgres_db netstat -ln | grep 5432

# Test from another container on the same network
docker run --rm --network app_data_app-network alpine \
  sh -c "apk add --no-cache postgresql-client && pg_isready -h app_data_postgres_db -p 5432"
```

**Auth failed**

```bash
# Check secrets are present and readable
docker exec app_data_postgres_db test -f /run/secrets/postgres_password && echo "✓ postgres secret present"
docker exec app_data_postgres_db test -f /run/secrets/backup_password && echo "✓ backup secret present"

# Verify local secret files exist
ls -la secrets/ | grep -E "(postgres_password|backup_password)" && echo "✓ Local secret files found"

# Test main user authentication
POSTGRES_PASSWORD=$(cat secrets/postgres_password.txt)
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" app_data_postgres_db \
  psql -U appuser -d appdb -c "SELECT 'Main user auth successful' AS status;"

# Test backup user authentication
BACKUP_PASSWORD=$(cat secrets/backup_password.txt)
docker exec -e PGPASSWORD="$BACKUP_PASSWORD" app_data_postgres_db \
  psql -U backup -d appdb -c "SELECT 'Backup user auth successful' AS status;"

# Check pg_hba.conf configuration
docker exec app_data_postgres_db \
  grep -E "(local|host)" /var/lib/postgresql/data/pg_hba.conf
```

**TLS issues**

```bash
# Check SSL certificate files exist and have correct permissions
docker exec app_data_postgres_db ls -l /var/lib/postgresql/data/server.*

# Verify SSL is enabled in PostgreSQL
POSTGRES_PASSWORD=$(cat secrets/postgres_password.txt)
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" app_data_postgres_db \
  psql -U appuser -d appdb -c "SHOW ssl; SELECT name, setting FROM pg_settings WHERE name LIKE 'ssl%';"

# Check active SSL connections
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" app_data_postgres_db \
  psql -U appuser -d appdb -c "SELECT pid, ssl, version, cipher FROM pg_stat_ssl WHERE ssl;"

# Test SSL connection from external client (if accessible)
# openssl s_client -connect yourdomain.com:5432 -starttls postgres
```

**Performance**

```sql
-- Long-running queries (run inside container)
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state <> 'idle' AND now() - query_start > interval '5 minutes';

-- Lock contention
SELECT bl.pid AS blocked_pid, wl.pid AS blocking_pid, a.query AS blocked_statement
FROM pg_locks bl
JOIN pg_stat_activity a ON a.pid = bl.pid
JOIN pg_locks wl ON wl.locktype = bl.locktype
                 AND coalesce(wl.relation,0)=coalesce(bl.relation,0)
                 AND wl.pid <> bl.pid
WHERE NOT bl.granted;
```

**Database reset issues**

```bash
# If reset script fails, try manual cleanup
docker-compose -f docker-compose.prod.yml down -v
sudo rm -rf data/postgres data/postgres-backups
docker volume prune -f

# Recreate directories
mkdir -p data/postgres data/postgres-backups

# Start fresh
docker-compose -f docker-compose.prod.yml up postgres

# Use reset script for automated cleanup
./reset_database.sh --help
./reset_database.sh
```

---

## 9) Checklists

**Pre-deployment**

* [ ] Secrets created (`postgres_password.txt`, `backup_password.txt`) with proper permissions (`600`)
* [ ] `postgresql.conf` & `pg_hba.conf` reviewed
* [ ] Custom entrypoint wrapper tested
* [ ] TLS configured (real certs for public/regulated)
* [ ] Backup user access verified (read-only)
* [ ] Monitoring + slow query capture enabled

**Post-deployment**

* [ ] Healthchecks green
* [ ] Auth & TLS verified (both appuser and backup user)
* [ ] Backup user permissions tested (cannot write)
* [ ] Extensions installed and functional
* [ ] Baseline performance captured
* [ ] Log rotation verified

**Ongoing**

* [ ] Regular image updates
* [ ] Password rotation
* [ ] Restore drills from backups
* [ ] Slow query review
* [ ] Capacity planning

---

## 10) Client Examples

> The following disable hostname/cert verification and are **only** appropriate for internal networks with self-signed certs. For public production, use a trusted CA and `sslmode=verify-full` (or `rejectUnauthorized: true` with a CA bundle).

**Python (asyncpg)**

```python
import os, asyncpg, ssl

async def get_db_connection():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return await asyncpg.connect(
        host="postgres",
        port=5432,
        user="appuser",
        password=os.getenv("POSTGRES_PASSWORD"),
        database="appdb",
        ssl=ctx,
    )
```

**Node.js (pg)**

```js
const { Pool } = require('pg');
const pool = new Pool({
  host: 'postgres',
  port: 5432,
  user: 'appuser',
  password: process.env.POSTGRES_PASSWORD,
  database: 'appdb',
  ssl: { require: true, rejectUnauthorized: false }, // internal only
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});
```

---

## 11) Additional Resources

* PostgreSQL 16 Docs: Security, SSL/TLS, Performance
* Docker Official Postgres Image Docs
* pg_stat_statements (monitoring)

---

