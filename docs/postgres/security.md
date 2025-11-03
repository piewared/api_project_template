# PostgreSQL Security Guide

## Overview

This guide covers security best practices, authentication methods, TLS/SSL configuration, and access control for PostgreSQL in this application.

## Table of Contents

1. [Security Architecture](#security-architecture)
2. [Authentication](#authentication)
3. [TLS/SSL Encryption](#tlsssl-encryption)
4. [Role-Based Access Control](#role-based-access-control)
5. [Network Security](#network-security)
6. [Password Management](#password-management)
7. [Audit Logging](#audit-logging)
8. [Security Hardening](#security-hardening)
9. [Compliance](#compliance)
10. [Incident Response](#incident-response)

## Security Architecture

### Multi-Layer Defense

```
┌─────────────────────────────────────────────┐
│  Layer 1: Network Isolation                 │
│  - Docker network isolation                 │
│  - Firewall rules (pg_hba.conf)            │
│  - Localhost-only binding (production)      │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│  Layer 2: TLS/SSL Encryption                │
│  - TLS 1.2+ only                           │
│  - Strong cipher suites                     │
│  - Certificate validation                   │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│  Layer 3: Authentication                    │
│  - SCRAM-SHA-256 password hashing          │
│  - Docker secrets (no env variables)        │
│  - Role-based access control                │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│  Layer 4: Authorization                     │
│  - Least privilege principle                │
│  - Schema-level permissions                 │
│  - Row-level security (RLS)                │
└─────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│  Layer 5: Audit & Monitoring                │
│  - Connection logging                       │
│  - Query logging (DDL + slow queries)       │
│  - Failed authentication tracking           │
└─────────────────────────────────────────────┘
```

### Three-Role Security Pattern

The application uses a least-privilege model with three distinct roles:

```
┌─────────────────────────────────────────────┐
│  Owner Role (NOLOGIN)                       │
│  Name: appowner                             │
│  Purpose: Database and schema ownership     │
│  Permissions: CREATE, ALTER, DROP objects   │
│  Login: ❌ No                               │
└─────────────────────────────────────────────┘
              │
              │ Owns database and schema
              │
    ┌─────────┴─────────┐
    │                   │
┌───▼──────────────┐  ┌─▼─────────────────┐
│ Application User │  │ Read-Only User    │
│ Name: appuser    │  │ Name: backupuser  │
│ Login: ✅ Yes    │  │ Login: ✅ Yes     │
│ Permissions:     │  │ Permissions:      │
│ - SELECT         │  │ - SELECT          │
│ - INSERT         │  │                   │
│ - UPDATE         │  │ Used for:         │
│ - DELETE         │  │ - Backups         │
│                  │  │ - Reporting       │
│ Used for:        │  │ - Analytics       │
│ - App runtime    │  │                   │
└──────────────────┘  └───────────────────┘
```

**Security Benefits:**
- **Separation of Concerns**: Owner can't be compromised via application
- **Least Privilege**: Application user has minimal required permissions
- **Audit Trail**: Clear separation between user types
- **Defense in Depth**: Even if app user is compromised, schema can't be altered

## Authentication

### SCRAM-SHA-256 Password Hashing

PostgreSQL 16 uses SCRAM-SHA-256 for password authentication (not MD5):

**Configuration:**
```properties
# postgresql.conf
password_encryption = scram-sha-256
```

**pg_hba.conf Rules:**
```properties
# Local connections use scram-sha-256
local   all             all                     scram-sha-256

# Network connections require TLS + scram-sha-256
hostssl all             all             172.30.50.0/24    scram-sha-256
```

**How SCRAM-SHA-256 Works:**
1. Client sends username
2. Server sends salt and iteration count
3. Client derives key using PBKDF2
4. Challenge-response authentication (prevents password exposure)
5. Server verifies without storing plaintext password

**Advantages over MD5:**
- Salted passwords (resistant to rainbow tables)
- Iteration count (resistant to brute force)
- Challenge-response (no password transmission)
- NIST-approved algorithm

### Docker Secrets (Production)

Passwords are stored in Docker secrets, NOT environment variables:

**docker-compose.prod.yml:**
```yaml
services:
  postgres:
    secrets:
      - postgres_password          # Superuser password
      - postgres_app_owner_pw      # Owner password (unused for login)
      - postgres_app_user_pw       # Application user password
      - postgres_app_ro_pw         # Read-only user password
      - postgres_temporal_pw       # Temporal user password

secrets:
  postgres_app_user_pw:
    file: ./infra/secrets/keys/postgres_app_user_pw.txt
```

**Accessing Secrets in Container:**
```bash
# Secrets are mounted as files
cat /run/secrets/postgres_app_user_pw
# Output: <24-character random password>
```

**Application Usage:**
```python
# Connection string uses environment variable reference
DATABASE_URL=postgresql://appuser:${POSTGRES_APP_USER_PW}@postgres:5432/appdb

# Environment variable reads from secret
POSTGRES_APP_USER_PW=$(cat /run/secrets/postgres_app_user_pw)
```

### Peer Authentication (Unix Sockets)

For local connections (within container):

```properties
# pg_hba.conf
local   all             postgres                peer
```

**How Peer Authentication Works:**
1. PostgreSQL asks OS: "Who is making this connection?"
2. OS responds with UID/username
3. PostgreSQL allows if username matches database role

**Security Benefit:** No password needed for local superuser access (useful for maintenance).

## TLS/SSL Encryption

### Server Configuration

**postgresql.conf:**
```properties
# Enable SSL
ssl = on
ssl_cert_file = '/etc/postgresql/ssl/server.crt'
ssl_key_file = '/etc/postgresql/ssl/server.key'

# TLS version constraints
ssl_min_protocol_version = 'TLSv1.2'
ssl_max_protocol_version = 'TLSv1.3'

# Prefer server cipher selection
ssl_prefer_server_ciphers = on

# Strong cipher suites (TLS 1.2)
ssl_ciphers = 'HIGH:!aNULL:!MD5'

# Enable row-level security
row_security = on
```

**Why These Settings:**
- **TLS 1.2+**: TLS 1.0/1.1 are deprecated (NIST guidelines)
- **HIGH ciphers**: Excludes weak ciphers (< 128-bit)
- **!aNULL**: No anonymous authentication
- **!MD5**: No MD5-based ciphers
- **Server cipher preference**: Server chooses strongest cipher

### Certificate Generation

**Using generate_secrets.sh:**
```bash
cd infra/secrets
./generate_secrets.sh

# Generates complete PKI hierarchy:
# - Root CA (10-year validity)
# - Intermediate CA (5-year validity)
# - PostgreSQL server certificate (1-year validity)
```

**Certificate Structure:**
```
certs/
├── root-ca.crt                    # Root CA certificate
├── root-ca.key                    # Root CA private key (keep secure!)
├── intermediate-ca.crt            # Intermediate CA certificate
├── intermediate-ca.key            # Intermediate CA private key
├── ca-bundle.crt                  # Root + Intermediate chain
└── postgres/
    ├── server.crt                 # PostgreSQL server certificate
    ├── server.key                 # PostgreSQL server private key
    └── server-chain.crt           # Server + intermediate chain
```

**Certificate Deployment:**
```yaml
# docker-compose.prod.yml
services:
  postgres:
    secrets:
      - source: postgres_tls_cert
        target: server.crt
        mode: 0400
      - source: postgres_tls_key
        target: server.key
        mode: 0400
      - source: postgres_server_ca
        target: ca-bundle.crt
        mode: 0400

secrets:
  postgres_tls_cert:
    file: ./infra/secrets/certs/postgres/server-chain-no-root.crt
  postgres_tls_key:
    file: ./infra/secrets/certs/postgres/server.key
  postgres_server_ca:
    file: ./infra/secrets/certs/ca-bundle.crt
```

### Client Configuration

**Connection String with SSL:**
```bash
# Require SSL (don't verify certificate)
DATABASE_URL=postgresql://appuser:password@postgres:5432/appdb?sslmode=require

# Verify CA certificate
DATABASE_URL=postgresql://appuser:password@postgres:5432/appdb?sslmode=verify-ca&sslrootcert=/run/secrets/ca-bundle.crt

# Full verification (hostname + CA)
DATABASE_URL=postgresql://appuser:password@postgres:5432/appdb?sslmode=verify-full&sslrootcert=/run/secrets/ca-bundle.crt
```

**SSL Modes:**

| Mode | Encrypted | Verifies Certificate | Verifies Hostname | Use Case |
|------|-----------|---------------------|-------------------|----------|
| `disable` | ❌ No | ❌ No | ❌ No | Local development only |
| `allow` | ✅ If available | ❌ No | ❌ No | Not recommended |
| `prefer` | ✅ If available | ❌ No | ❌ No | Default (not secure) |
| `require` | ✅ Yes | ❌ No | ❌ No | Minimum for production |
| `verify-ca` | ✅ Yes | ✅ Yes | ❌ No | Recommended |
| `verify-full` | ✅ Yes | ✅ Yes | ✅ Yes | Most secure |

**Recommendation:** Use `verify-ca` for production (balances security and operational complexity).

### Certificate Renewal

**Annual Renewal Process:**

```bash
# 1. Generate new certificates (preserves existing as backup)
cd infra/secrets
./generate_secrets.sh

# 2. Update Docker secrets (requires service restart)
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# 3. Verify new certificates
docker exec api-template-postgres-prod \
  psql -U appuser -d appdb -c \
  "SELECT * FROM pg_stat_ssl WHERE pid = pg_backend_pid();"

# Output should show:
# ssl | t (true)
# version | TLSv1.3
# cipher | TLS_AES_256_GCM_SHA384
```

**Let's Encrypt Integration (Optional):**

For public-facing databases:

```bash
# 1. Obtain certificate via Certbot
certbot certonly --standalone -d postgres.yourdomain.com

# 2. Copy to secrets directory
cp /etc/letsencrypt/live/postgres.yourdomain.com/fullchain.pem \
   ./infra/secrets/certs/postgres/server.crt
cp /etc/letsencrypt/live/postgres.yourdomain.com/privkey.pem \
   ./infra/secrets/certs/postgres/server.key

# 3. Set permissions
chmod 600 ./infra/secrets/certs/postgres/server.key
chmod 644 ./infra/secrets/certs/postgres/server.crt

# 4. Reload PostgreSQL
docker exec api-template-postgres-prod pg_ctl reload -D /var/lib/postgresql/data
```

## Role-Based Access Control

### Role Creation (Production)

Roles are created automatically by init scripts during first boot:

**Script:** `/infra/docker/prod/postgres/init-scripts/01-init-app.sh`

```bash
#!/bin/sh
set -eu

# Create NOLOGIN owner
CREATE ROLE appowner NOLOGIN;

# Create LOGIN users
CREATE ROLE appuser LOGIN PASSWORD '${POSTGRES_APP_USER_PW}';
CREATE ROLE backupuser LOGIN PASSWORD '${POSTGRES_APP_RO_PW}';

# Create database owned by NOLOGIN owner
CREATE DATABASE appdb OWNER appowner;

# Connect to database
\connect appdb

# Create schema owned by NOLOGIN owner
CREATE SCHEMA app AUTHORIZATION appowner;

# Lock down public access
REVOKE CREATE ON DATABASE appdb FROM PUBLIC;
REVOKE ALL ON SCHEMA app FROM PUBLIC;

# Grant application user permissions
GRANT USAGE ON SCHEMA app TO appuser;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO appuser;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA app TO appuser;

# Grant read-only user permissions
GRANT USAGE ON SCHEMA app TO backupuser;
GRANT SELECT ON ALL TABLES IN SCHEMA app TO backupuser;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA app TO backupuser;

# Set default privileges for future objects
ALTER DEFAULT PRIVILEGES FOR ROLE appowner IN SCHEMA app
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO appuser;

ALTER DEFAULT PRIVILEGES FOR ROLE appowner IN SCHEMA app
    GRANT SELECT ON TABLES TO backupuser;
```

### Permission Verification

**Check role permissions:**
```sql
-- List all roles
SELECT rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin
FROM pg_roles
WHERE rolname IN ('appowner', 'appuser', 'backupuser');

-- Check schema permissions
SELECT grantee, privilege_type
FROM information_schema.schema_privileges
WHERE schema_name = 'app';

-- Check table permissions
SELECT grantee, table_name, privilege_type
FROM information_schema.table_privileges
WHERE table_schema = 'app';
```

**Expected Output:**
```
Role        | Super | Inherit | CreateRole | CreateDB | CanLogin
------------|-------|---------|------------|----------|----------
appowner    | f     | t       | f          | f        | f
appuser     | f     | t       | f          | f        | t
backupuser  | f     | t       | f          | f        | t

Schema | Grantee    | Privilege
-------|------------|----------
app    | appuser    | USAGE
app    | backupuser | USAGE

Table      | Grantee    | Privilege
-----------|------------|----------
usertable  | appuser    | SELECT, INSERT, UPDATE, DELETE
usertable  | backupuser | SELECT
```

### Row-Level Security (RLS)

For multi-tenant applications:

```sql
-- Enable RLS on table
ALTER TABLE usertable ENABLE ROW LEVEL SECURITY;

-- Create policy for application user
CREATE POLICY user_isolation_policy ON usertable
    FOR ALL
    TO appuser
    USING (tenant_id = current_setting('app.tenant_id')::uuid);

-- Create policy for read-only user
CREATE POLICY read_only_policy ON usertable
    FOR SELECT
    TO backupuser
    USING (true);  -- Can read all rows

-- Set tenant ID in session
SET app.tenant_id = 'tenant-123';

-- Now SELECT queries are automatically filtered
SELECT * FROM usertable;  -- Only returns rows for tenant-123
```

## Network Security

### pg_hba.conf Configuration

**Development (permissive):**
```properties
# Allow all connections with password
host    all             all             0.0.0.0/0               scram-sha-256
```

**Production (restrictive):**
```properties
# TYPE  DATABASE        USER            ADDRESS                 METHOD

# Local connections (Unix socket)
local   all             postgres                                peer
local   all             all                                     scram-sha-256

# Localhost (container internal)
host    all             all             127.0.0.1/32            scram-sha-256
host    all             all             ::1/128                 scram-sha-256

# EXPLICITLY DENY non-TLS connections
hostnossl all           all             0.0.0.0/0               reject
hostnossl all           all             ::/0                    reject

# Allow TLS connections from private networks ONLY
hostssl  all            all             172.30.50.0/24          scram-sha-256  # Backend network
hostssl  all            all             172.18.0.0/16           scram-sha-256  # Docker network
hostssl  all            all             10.10.0.0/16            scram-sha-256  # Private network

# Final deny-all (defense in depth)
host     all            all             0.0.0.0/0               reject
host     all            all             ::/0                    reject
```

**Rule Order Matters:** First matching rule is applied.

### Docker Network Isolation

**Development:**
```yaml
networks:
  dev-network:
    name: dev-network
    driver: bridge

services:
  postgres:
    networks:
      - dev-network
    ports:
      - "5433:5432"  # Exposed to host
```

**Production:**
```yaml
networks:
  backend:
    name: application_internal
    driver: bridge
    internal: true  # No external access
    ipam:
      config:
        - subnet: 172.30.50.0/24
          gateway: 172.30.50.1

services:
  postgres:
    networks:
      - backend
    ports:
      - "127.0.0.1:5432:5432"  # Localhost only
```

**Security Benefits:**
- **internal: true**: Network can't reach internet
- **Localhost binding**: No external network access
- **Subnet isolation**: Controlled IP range

### Firewall Rules (Host Level)

**Using UFW (Ubuntu):**
```bash
# Allow localhost only
sudo ufw allow from 127.0.0.1 to any port 5432

# Allow from specific Docker subnet
sudo ufw allow from 172.30.50.0/24 to any port 5432

# Deny all other access
sudo ufw deny 5432/tcp
```

**Using iptables:**
```bash
# Allow localhost
iptables -A INPUT -p tcp -s 127.0.0.1 --dport 5432 -j ACCEPT

# Allow Docker network
iptables -A INPUT -p tcp -s 172.30.50.0/24 --dport 5432 -j ACCEPT

# Deny all other
iptables -A INPUT -p tcp --dport 5432 -j DROP
```

## Password Management

### Password Generation

**Using generate_secrets.sh:**
```bash
cd infra/secrets
./generate_secrets.sh

# Generates secure passwords:
# - 24 characters
# - Uppercase + lowercase + numbers + safe special chars
# - Cryptographically random (from /dev/urandom)
```

**Manual Generation:**
```bash
# Generate 24-character password
openssl rand -base64 24 | tr '+/' '-_' | cut -c1-24

# Generate 32-character password
openssl rand -base64 32 | tr '+/' '-_' | cut -c1-32
```

### Password Storage

**❌ NEVER:**
- Store in environment variables (visible in `docker inspect`)
- Commit to version control
- Store in plaintext files outside secrets directory
- Share via email/chat

**✅ ALWAYS:**
- Use Docker secrets
- Encrypt at rest (filesystem encryption)
- Use secrets management service (AWS Secrets Manager, HashiCorp Vault)
- Rotate regularly (every 90 days)

### Password Rotation

**Quick Rotation Process:**

```bash
# 1. Generate new password
NEW_PASSWORD=$(openssl rand -base64 24 | tr '+/' '-_' | cut -c1-24)

# 2. Update secret file
echo "$NEW_PASSWORD" > ./infra/secrets/keys/postgres_app_user_pw.txt

# 3. Update password in database
docker exec -it api-template-postgres-prod psql -U postgres -d appdb <<SQL
ALTER USER appuser PASSWORD '$NEW_PASSWORD';
SQL

# 4. Restart application to pick up new secret
docker-compose -f docker-compose.prod.yml restart app
```

**Automated Rotation (Recommended):**

See [Secrets Management Documentation](../secrets_management.md) for automated rotation with backup and verification.

### Password Complexity Requirements

**Current Requirements:**
- Minimum length: 24 characters
- Character set: `[A-Za-z0-9-_]`
- Entropy: ~143 bits (24 chars * 6 bits/char)

**Recommended for Custom Passwords:**
- Minimum length: 16 characters
- At least 3 character classes:
  - Uppercase: A-Z
  - Lowercase: a-z
  - Numbers: 0-9
  - Special: !@#$%^&*()_+-=[]{}|

## Audit Logging

### Connection Logging

**postgresql.conf:**
```properties
log_connections = on
log_disconnections = on
log_duration = off
log_line_prefix = '%t [%p-%l] %q%u@%d '
```

**Example Log Output:**
```
2025-11-02 10:30:15 UTC [1234-1] appuser@appdb LOG: connection authorized: user=appuser database=appdb SSL enabled (protocol=TLSv1.3, cipher=TLS_AES_256_GCM_SHA384, bits=256)
2025-11-02 10:30:45 UTC [1234-2] appuser@appdb LOG: disconnection: session time: 0:00:30.123
```

### Query Logging

**Log DDL statements:**
```properties
log_statement = 'ddl'  # CREATE, ALTER, DROP
```

**Log slow queries:**
```properties
log_min_duration_statement = 1000  # Log queries > 1 second
```

**Example Log Output:**
```
2025-11-02 10:30:20 UTC [1234-3] appuser@appdb LOG: duration: 1523.456 ms  statement: SELECT * FROM usertable WHERE email LIKE '%@example.com%'
```

### Failed Authentication Tracking

**postgresql.conf:**
```properties
log_min_error_statement = error  # Log statements causing errors
```

**Example Log Output:**
```
2025-11-02 10:31:00 UTC [1235-1] appuser@appdb FATAL: password authentication failed for user "appuser"
2025-11-02 10:31:00 UTC [1235-1] appuser@appdb DETAIL: Connection matched pg_hba.conf line 10: "hostssl all all 172.30.50.0/24 scram-sha-256"
```

### pg_stat_statements Extension

**Enable query statistics:**
```sql
-- In postgresql.conf
shared_preload_libraries = 'pg_stat_statements'

-- Create extension
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- View top queries
SELECT
    query,
    calls,
    total_exec_time,
    mean_exec_time,
    max_exec_time
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

## Security Hardening

### Database Configuration

**postgresql.conf hardening:**
```properties
# Disable insecure features
ssl_prefer_server_ciphers = on
password_encryption = scram-sha-256
row_security = on

# Enable security logging
log_connections = on
log_disconnections = on
log_statement = 'ddl'
log_min_error_statement = error

# Prevent resource exhaustion
max_connections = 100
statement_timeout = 300000  # 5 minutes
idle_in_transaction_session_timeout = 600000  # 10 minutes

# Data integrity
fsync = on
synchronous_commit = on
full_page_writes = on
wal_log_hints = on
data_checksums = on  # Enable at initdb time
```

### Application Configuration

**Connection string hardening:**
```bash
# Use SSL with certificate verification
DATABASE_URL=postgresql://appuser:password@postgres:5432/appdb?sslmode=verify-ca&sslrootcert=/run/secrets/ca-bundle.crt&connect_timeout=10&application_name=api_production
```

**Connection pool limits:**
```yaml
# config.yaml
database:
  pool_size: 20
  max_overflow: 10
  pool_timeout: 30
  pool_recycle: 1800
```

### Docker Container Hardening

**docker-compose.prod.yml:**
```yaml
services:
  postgres:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - DAC_OVERRIDE
      - FOWNER
      - SETUID
      - SETGID
    read_only: false  # PostgreSQL needs to write
    tmpfs:
      - /tmp:noexec,nosuid,nodev,size=100m
    user: postgres  # Run as non-root user
```

## Compliance

### GDPR Compliance

**Data Encryption:**
- ✅ TLS 1.2+ for data in transit
- ✅ Filesystem encryption for data at rest (host level)
- ✅ Encrypted backups

**Data Minimization:**
```sql
-- Store only necessary fields
CREATE TABLE usertable (
    id UUID PRIMARY KEY,
    email VARCHAR(255),  -- Only if required
    created_at TIMESTAMP,
    updated_at TIMESTAMP
    -- No unnecessary PII
);
```

**Right to Erasure:**
```sql
-- Soft delete implementation
ALTER TABLE usertable ADD COLUMN deleted_at TIMESTAMP;
ALTER TABLE usertable ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE;

-- Delete user data
UPDATE usertable SET
    deleted_at = NOW(),
    is_deleted = TRUE,
    email = NULL,  -- Anonymize
    first_name = 'DELETED',
    last_name = 'USER'
WHERE id = 'user-123';
```

**Audit Trail:**
```sql
-- Create audit log table
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    action VARCHAR(50),
    timestamp TIMESTAMP DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT
);
```

### HIPAA Compliance (Healthcare)

**Encryption Requirements:**
- ✅ TLS 1.2+ with FIPS 140-2 compliant ciphers
- ✅ Encrypted backups with access controls
- ✅ Encrypted database volumes

**Access Controls:**
- ✅ Role-based access control (RBAC)
- ✅ Audit logging of all PHI access
- ✅ Automatic session timeout

**Business Associate Agreement (BAA):**
- Cloud provider must sign BAA (AWS, Google Cloud, Azure)
- Managed PostgreSQL services (RDS, Cloud SQL, Azure Database)

## Incident Response

### Detecting Compromised Credentials

**Signs of Compromise:**
```sql
-- Check for unusual connection sources
SELECT DISTINCT client_addr, usename, datname, state
FROM pg_stat_activity
WHERE usename = 'appuser' AND client_addr NOT IN ('172.30.50.0/24');

-- Check for privilege escalation attempts
SELECT usename, query, state
FROM pg_stat_activity
WHERE query LIKE '%CREATE ROLE%' OR query LIKE '%ALTER ROLE%';

-- Check for unusual DDL activity
SELECT query_start, usename, query
FROM pg_stat_activity
WHERE query LIKE '%DROP%' OR query LIKE '%ALTER TABLE%';
```

### Immediate Response Actions

**1. Revoke Access:**
```sql
-- Immediately revoke all permissions
REVOKE ALL ON SCHEMA app FROM appuser;
REVOKE ALL ON DATABASE appdb FROM appuser;

-- Disable login
ALTER USER appuser WITH NOLOGIN;
```

**2. Terminate Sessions:**
```sql
-- Terminate all sessions for compromised user
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE usename = 'appuser';
```

**3. Rotate Credentials:**
```bash
# Generate new password
cd infra/secrets
./generate_secrets.sh

# Apply new password
docker exec api-template-postgres-prod psql -U postgres <<SQL
ALTER USER appuser PASSWORD '<new-password>';
ALTER USER appuser WITH LOGIN;
SQL

# Restart application
docker-compose -f docker-compose.prod.yml restart app
```

**4. Audit Investigation:**
```sql
-- Check what the compromised user did
SELECT usename, query, query_start, state
FROM pg_stat_activity
WHERE usename = 'appuser';

-- Check recently modified tables
SELECT schemaname, tablename, last_vacuum, last_autovacuum, last_analyze
FROM pg_stat_user_tables
WHERE last_autovacuum > NOW() - INTERVAL '1 hour';
```

### Prevention Checklist

- [ ] Enable TLS/SSL with certificate verification
- [ ] Use SCRAM-SHA-256 authentication (not MD5)
- [ ] Store passwords in Docker secrets (not env vars)
- [ ] Implement least-privilege access control
- [ ] Enable connection and query logging
- [ ] Configure pg_hba.conf to restrict network access
- [ ] Rotate passwords every 90 days
- [ ] Use filesystem encryption for data at rest
- [ ] Implement automated backups with encryption
- [ ] Monitor for failed authentication attempts
- [ ] Set up alerts for unusual activity
- [ ] Keep PostgreSQL updated with security patches

## Related Documentation

- [Main Documentation](./main.md) - PostgreSQL overview
- [Configuration Guide](./configuration.md) - Connection settings
- [Usage Guide](./usage.md) - Code examples
- [Migrations Guide](./migrations.md) - Schema management
- [Secrets Management](../secrets_management.md) - Password and certificate generation
- [Production Deployment](../PRODUCTION_DEPLOYMENT.md) - Production setup
