# Production PostgreSQL Documentation

## 🐘 **PostgreSQL 16 Production Setup**

This document provides comprehensive details about our production-ready PostgreSQL 16 deployment with enterprise-grade security, performance optimization, and operational best practices.

---

## 🔐 **Security Features**

### **Authentication & Access Control**
```yaml
Authentication Method: SCRAM-SHA-256
Password Storage: Docker Secrets (file-based)
SSL/TLS Encryption: TLSv1.3 with AES-256-GCM
Connection Logging: Enabled
Failed Login Tracking: Enabled
```

#### **Password Security**
- **SCRAM-SHA-256**: Modern password hashing algorithm (replaces MD5)
- **Docker Secrets**: Passwords stored in `/run/secrets/postgres_password`
- **No Environment Variables**: Passwords never exposed in process lists
- **Secure File Permissions**: Secret files are `600` (owner read/write only)

#### **SSL/TLS Configuration**
```sql
ssl = on
ssl_cert_file = 'server.crt'           -- Server certificate
ssl_key_file = 'server.key'            -- Private key
ssl_prefer_server_ciphers = on          -- Server chooses cipher
ssl_ciphers = 'HIGH:!aNULL:!MD5'       -- Strong ciphers only
```

**Generated Certificates:**
- **Self-signed server certificate** for development/testing
- **TLS 1.3 support** with modern cipher suites
- **Automatic certificate generation** on first startup
- **Proper file permissions** (600 for keys, 644 for certificates)

> ⚠️ **Production Certificate Warning**: Self-signed certificates are **NOT recommended for production** environments. They provide encryption but do not provide identity verification and will cause certificate warnings in client applications.

> **Exception for Managed Providers**: When deploying PostgreSQL behind a VPN or within managed container providers like **fly.io**, **Railway**, or **Render** where:
> - Database traffic stays **within the provider's private network**
> - **No external client connections** are made directly to PostgreSQL
> - Applications connect via **internal networking** (e.g., Docker networks, private DNS)
> - The **provider handles TLS termination** at the load balancer/proxy level
> 
> In these scenarios, self-signed certificates may be acceptable since:
> - ✅ Traffic is **encrypted within the private network**
> - ✅ **No certificate warnings** shown to end users
> - ✅ **Identity verification** handled at the application layer
> - ✅ **Reduced operational complexity** for internal services
>
> However, even in private networks, consider using proper certificates for:
> - **Regulatory compliance** (HIPAA, SOC2, PCI-DSS)
> - **Zero-trust security** architectures  
> - **Service mesh** deployments with mutual TLS
> - **Multi-tenant** environments with strict isolation

#### **Production Certificate Setup**

For production deployments, use proper SSL certificates from a trusted Certificate Authority (CA):

##### **Option 1: Let's Encrypt (Recommended for Public Deployments)**
```bash
# Install certbot
apt-get update && apt-get install certbot

# Generate certificate for your domain
certbot certonly --standalone -d yourdomain.com

# Copy certificates to PostgreSQL directory
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /path/to/postgres/certs/server.crt
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /path/to/postgres/certs/server.key

# Set proper permissions
chmod 600 /path/to/postgres/certs/server.key
chmod 644 /path/to/postgres/certs/server.crt
chown 999:999 /path/to/postgres/certs/server.*

# Update docker-compose.yml to mount certificates
volumes:
  - /path/to/postgres/certs:/var/lib/postgresql/certs:ro

# Update postgresql.conf
ssl_cert_file = '/var/lib/postgresql/certs/server.crt'
ssl_key_file = '/var/lib/postgresql/certs/server.key'
```

##### **Option 2: Corporate/Internal CA**
```bash
# If using internal CA, add CA certificate for client verification
ssl_ca_file = '/var/lib/postgresql/certs/ca.crt'
ssl_crl_file = '/var/lib/postgresql/certs/server.crl'  # Optional

# For client certificate authentication
hostssl all appuser 0.0.0.0/0 cert clientcert=verify-ca

# Mount CA certificate
volumes:
  - /path/to/corporate/ca.crt:/var/lib/postgresql/certs/ca.crt:ro
```

##### **Option 3: AWS Certificate Manager (for RDS)**
```bash
# For AWS deployments, use RDS with ACM certificates
# PostgreSQL will automatically use AWS-managed certificates
rds_force_ssl = 1
```

##### **Option 4: Managed Container Providers**

**For fly.io, Railway, Render, and similar platforms:**

```yaml
# fly.toml example
[env]
  POSTGRES_SSL_MODE = "require"      # Still enforce SSL
  POSTGRES_SSL_CERT_VALIDATION = "none"  # Accept self-signed for internal

# For fly.io private networking
[[services]]
  internal_port = 5432
  protocol = "tcp"
  
  [[services.ports]]
    port = 5432
    handlers = ["pg_tls"]  # fly.io handles TLS termination
```

**Railway/Render deployment:**
```dockerfile
# Keep self-signed certificates for internal networking
ENV POSTGRES_SSL_MODE=require
ENV POSTGRES_SSL_CERT_VALIDATION=none

# Provider handles external TLS at load balancer level
```

**When to upgrade to proper certificates on managed platforms:**
- **External database connections** (mobile apps, third-party integrations)
- **Compliance requirements** (HIPAA, SOC2, PCI-DSS)  
- **Multi-region deployments** with cross-provider communication
- **Hybrid cloud** architectures connecting to on-premises systems

**Security considerations for managed providers:**
```bash
# Even with self-signed certs, enforce strong security
# 1. Network isolation
networks:
  app-network:
    driver: bridge
    internal: true  # No external internet access

# 2. Connection string security
postgresql://appuser:${POSTGRES_PASSWORD}@postgres:5432/appdb?sslmode=require&sslcert=client.crt

# 3. Application-level encryption for sensitive data
# Use pgcrypto for column-level encryption
CREATE EXTENSION pgcrypto;
INSERT INTO users (email, encrypted_ssn) VALUES 
  ('user@example.com', pgp_sym_encrypt('123-45-6789', '${ENCRYPTION_KEY}'));
```

##### **Certificate Renewal Automation**
```bash
# Create renewal script for Let's Encrypt
cat > /usr/local/bin/renew-postgres-certs.sh << 'EOF'
#!/bin/bash
# Renew Let's Encrypt certificates and update PostgreSQL

certbot renew --quiet

# Copy new certificates
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /path/to/postgres/certs/server.crt
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /path/to/postgres/certs/server.key

# Set permissions
chmod 600 /path/to/postgres/certs/server.key
chmod 644 /path/to/postgres/certs/server.crt
chown 999:999 /path/to/postgres/certs/server.*

# Reload PostgreSQL configuration (no restart needed)
docker exec postgres_container pg_ctl reload -D /var/lib/postgresql/data

# Log renewal
echo "$(date): PostgreSQL certificates renewed" >> /var/log/cert-renewal.log
EOF

chmod +x /usr/local/bin/renew-postgres-certs.sh

# Add to crontab (check daily, renew if needed)
echo "0 2 * * * /usr/local/bin/renew-postgres-certs.sh" | crontab -
```

##### **Certificate Validation**
```bash
# Verify certificate details
openssl x509 -in /path/to/postgres/certs/server.crt -text -noout

# Check certificate expiry
openssl x509 -in /path/to/postgres/certs/server.crt -noout -enddate

# Test SSL connection with proper certificate
openssl s_client -connect yourdomain.com:5432 -starttls postgres

# Verify from PostgreSQL client
psql "host=yourdomain.com port=5432 dbname=appdb user=appuser sslmode=require sslcert=client.crt sslkey=client.key"
```

#### **Network Security**
```yaml
Listen Address: '*' (within Docker network only)
Port: 5432 (internal Docker network)
Host-based Authentication: Configured via pg_hba.conf
Connection Limits: 100 max connections
Superuser Reserved: 3 connections
```

#### **Database Permissions**
```sql
Database: appdb
Application User: appuser (limited privileges)
Schema: app (application-specific)
Extensions: pgcrypto, uuid-ossp, btree_gin
Default Privileges: Read/write on app schema only
```

---

## ⚡ **Performance Considerations**

### **Memory Configuration**
```sql
shared_buffers = 256MB              -- 25% of available RAM (adjust for production)
work_mem = 4MB                      -- Per-operation memory
maintenance_work_mem = 64MB         -- Vacuum, reindex operations
effective_cache_size = 1GB          -- OS cache estimate
```

### **Write-Ahead Logging (WAL)**
```sql
wal_level = replica                 -- Supports streaming replication
max_wal_size = 1GB                  -- Maximum WAL size before checkpoint
min_wal_size = 80MB                 -- Minimum WAL files to keep
checkpoint_completion_target = 0.9   -- Spread checkpoints over time
wal_buffers = 16MB                  -- WAL write buffering
```

### **Query Optimization**
```sql
random_page_cost = 1.1              -- SSD-optimized (default: 4.0)
effective_io_concurrency = 200      -- Concurrent I/O operations
```

### **Connection Management**
```sql
max_connections = 100               -- Maximum concurrent connections
superuser_reserved_connections = 3  -- Reserved for admin tasks
```

### **Performance Monitoring**
```sql
log_min_duration_statement = 1000  -- Log slow queries (>1 second)
log_checkpoints = on                -- Log checkpoint activity
log_lock_waits = on                 -- Log lock contention
log_temp_files = 0                  -- Log all temp file usage
```

---

## 🏗️ **Dockerfile Architecture**

### **Base Image**
```dockerfile
FROM postgres:16-alpine
```
- **Alpine Linux**: Minimal attack surface (~5MB base)
- **PostgreSQL 16**: Latest stable with security updates
- **Official Image**: Maintained by PostgreSQL team

### **Additional Packages**
```dockerfile
RUN apk add --no-cache \
    bash \           # Advanced shell scripting
    curl \           # Health checks and monitoring
    openssl \        # SSL certificate generation
    postgresql-contrib  # Additional extensions
```

### **Security Hardening**
```dockerfile
# Create backup user with limited privileges
RUN adduser -D -s /bin/bash backup && \
    mkdir -p /var/lib/postgresql/backups && \
    chown backup:backup /var/lib/postgresql/backups
```

### **Configuration Management**
```dockerfile
# Copy production configurations
COPY postgresql.conf /tmp/postgresql.conf
COPY pg_hba.conf /tmp/pg_hba.conf

# Copy initialization scripts
COPY init-scripts/ /docker-entrypoint-initdb.d/
COPY backup-scripts/ /usr/local/bin/
```

### **Environment Variables**
```dockerfile
ENV POSTGRES_DB=appdb \
    POSTGRES_USER=appuser \
    POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password \
    POSTGRES_INITDB_ARGS="--auth-host=scram-sha-256 --data-checksums" \
    POSTGRES_HOST_AUTH_METHOD=scram-sha-256
```

### **Health Checks**
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD pg_isready -U $POSTGRES_USER -d $POSTGRES_DB || exit 1
```

---

## 💾 **Data Volumes**

For more information about managing data volumes, see [Managing Postgres Data Volumes](./postgress-data-volumes.md).

### **Primary Data Volume**
```yaml
Volume Name: postgres_data
Mount Point: /var/lib/postgresql/data
Purpose: Database files, WAL, configuration
Backup: Critical - contains all database data
```

### **Backup Volume**
```yaml
Volume Name: postgres_backups  
Mount Point: /var/lib/postgresql/backups
Purpose: Automated backup storage
Retention: Configurable via backup scripts
```

### **Host Bind Mounts**
```yaml
Host Path: ./data/postgres
Container Path: /var/lib/postgresql/data
Purpose: Data persistence across container restarts
```
```yaml
Host Path: ./data/postgres-backups
Container Path: /var/lib/postgresql/backups  
Purpose: Backup file access from host
```

### **Volume Permissions**
```bash
# Data directory ownership
chown -R 999:999 ./data/postgres      # postgres user (UID 999)

# Backup directory permissions
chown -R backup:backup /var/lib/postgresql/backups
chmod 750 /var/lib/postgresql/backups
```

---

## 🔨 **Building the Image**

### **Prerequisites**
```bash
# Ensure Docker is installed and running
docker --version

# Navigate to project directory
cd /path/to/your/project
```

### **Build Command**
```bash
# Build PostgreSQL image
docker-compose -f docker-compose.prod.yml build postgres

# Or build directly with Docker
docker build -t your-app-postgres:latest ./docker/postgres/
```

### **Build Process Steps**
1. **Base Image Download**: Pulls postgres:16-alpine
2. **Package Installation**: Installs bash, curl, openssl, postgresql-contrib
3. **User Creation**: Creates backup user with limited privileges
4. **File Copying**: Copies configuration files and scripts
5. **Permission Setting**: Makes scripts executable
6. **Environment Setup**: Configures production environment variables

### **Build Verification**
```bash
# Verify image was built successfully
docker images | grep postgres

# Check image layers
docker history your-app-postgres:latest
```

---

## 🚀 **Deployment Steps**

### **1. Prerequisites Setup**
```bash
# Create required directories
mkdir -p data/postgres data/postgres-backups secrets

# Create secrets files
echo "YourSecurePassword123!" > secrets/postgres_password.txt
echo "BackupPassword456!" > secrets/backup_password.txt

# Set secure permissions
chmod 600 secrets/*
```

### **2. Deploy PostgreSQL**
```bash
# Start PostgreSQL service
docker-compose -f docker-compose.prod.yml up -d postgres

# Monitor startup logs
docker-compose -f docker-compose.prod.yml logs -f postgres
```

### **3. Verify Deployment**
```bash
# Check service status
docker-compose -f docker-compose.prod.yml ps postgres

# Test database connectivity
docker exec postgres_container pg_isready -U appuser -d appdb

# Verify SSL is enabled
docker exec postgres_container psql -U appuser -d appdb -c "SHOW ssl;"
```

### **4. Initial Database Setup**
```bash
# Connect to database (will prompt for password)
docker exec -it postgres_container psql -U appuser -d appdb

# Or use environment variable
docker exec postgres_container bash -c \
  'PGPASSWORD=$(cat /run/secrets/postgres_password) psql -U appuser -d appdb'
```

---

## 🔧 **Configuration Files**

### **postgresql.conf**
**Location**: `/docker/postgres/postgresql.conf`
```sql
# Key production settings
listen_addresses = '*'                    # Accept connections from Docker network
shared_buffers = 256MB                   # Shared memory for caching
work_mem = 4MB                           # Per-query working memory
ssl = on                                 # Enable SSL/TLS
password_encryption = scram-sha-256      # Modern password hashing
log_connections = on                     # Security logging
log_disconnections = on                  # Security logging
```

### **pg_hba.conf**
**Location**: `/docker/postgres/pg_hba.conf`
```
# TYPE  DATABASE    USER        ADDRESS         METHOD
local   all         postgres                    trust
local   all         all                         scram-sha-256
host    all         all         127.0.0.1/32    scram-sha-256
host    all         all         ::1/128         scram-sha-256
host    all         all         all             scram-sha-256
```

### **Initialization Scripts**
**Location**: `/docker/postgres/init-scripts/`
- `01-apply-configs.sh`: Applies custom configurations
- `01-init-db.sh`: Creates application database and user

---

## 📊 **Monitoring & Maintenance**

### **Health Monitoring**
```bash
# Container health status
docker-compose -f docker-compose.prod.yml ps

# Database availability
docker exec postgres_container pg_isready

# Connection count
docker exec postgres_container psql -U appuser -d appdb -c \
  "SELECT count(*) FROM pg_stat_activity;"

# SSL connections
docker exec postgres_container psql -U appuser -d appdb -c \
  "SELECT pid, ssl, version, cipher FROM pg_stat_ssl WHERE ssl = true;"
```

### **Performance Monitoring**
```sql
-- Slow queries
SELECT query, mean_exec_time, calls 
FROM pg_stat_statements 
ORDER BY mean_exec_time DESC LIMIT 10;

-- Database size
SELECT pg_size_pretty(pg_database_size('appdb'));

-- Table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(tablename))
FROM pg_tables WHERE schemaname = 'app';

-- Connection statistics
SELECT state, count(*) FROM pg_stat_activity GROUP BY state;
```

### **Backup Operations**
```bash
# Manual backup
docker exec postgres_container /usr/local/bin/backup-postgres.sh

# Restore from backup
docker exec postgres_container /usr/local/bin/restore-postgres.sh backup_file.sql

# List available backups
docker exec postgres_container ls -la /var/lib/postgresql/backups/
```

---

## 🔒 **Security Best Practices**

### **1. Regular Updates**
```bash
# Update base image regularly
docker pull postgres:16-alpine
docker-compose build postgres
```

### **2. Secret Rotation**
```bash
# Update password (requires container restart)
echo "NewSecurePassword789!" > secrets/postgres_password.txt
docker-compose restart postgres
```

### **3. Access Control**
```bash
# Limit network access
# Use Docker networks to isolate database
# Never expose port 5432 to host in production
```

### **4. Audit Logging**
```sql
-- Enable additional logging
log_statement = 'all'                   # Log all statements (verbose)
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d '
```

### **5. Resource Limits**
```yaml
# In docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
    reservations:
      cpus: '1.0'
      memory: 1G
```

---

## 🚨 **Troubleshooting**

### **Common Issues**

#### **Connection Refused**
```bash
# Check if container is running
docker-compose ps postgres

# Check logs for startup errors
docker-compose logs postgres

# Verify network connectivity
docker exec app_container ping postgres
```

#### **Authentication Failed**
```bash
# Verify password file exists
docker exec postgres_container cat /run/secrets/postgres_password

# Check pg_hba.conf settings
docker exec postgres_container cat /var/lib/postgresql/data/pg_hba.conf

# Test with correct password
PGPASSWORD=your_password psql -h localhost -U appuser -d appdb
```

#### **SSL Issues**
```bash
# Check SSL certificates
docker exec postgres_container ls -la /var/lib/postgresql/data/server.*

# Verify SSL configuration
docker exec postgres_container psql -U appuser -d appdb -c "SHOW ssl;"

# Test SSL connection
docker exec postgres_container psql -h localhost -U appuser -d appdb \
  -c "SELECT * FROM pg_stat_ssl;"
```

#### **Performance Issues**
```sql
-- Check for long-running queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query 
FROM pg_stat_activity 
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';

-- Check for lock contention
SELECT blocked_locks.pid AS blocked_pid,
       blocking_locks.pid AS blocking_pid,
       blocked_activity.query AS blocked_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype;
```

---

## 📋 **Production Checklist**

### **Pre-Deployment**
- [ ] Secrets files created with secure passwords
- [ ] Directory permissions set correctly (600 for secrets)
- [ ] PostgreSQL configuration reviewed and tuned
- [ ] SSL certificates configured properly
- [ ] Backup strategy implemented
- [ ] Monitoring setup completed

### **Post-Deployment**
- [ ] Health checks passing
- [ ] SSL connections working
- [ ] Authentication working correctly
- [ ] Performance metrics within acceptable ranges
- [ ] Backup scripts tested
- [ ] Log rotation configured
- [ ] Security audit completed

### **Ongoing Maintenance**
- [ ] Regular security updates
- [ ] Password rotation schedule
- [ ] Backup verification
- [ ] Performance monitoring
- [ ] Log analysis
- [ ] Capacity planning

---

## 🔗 **Integration Examples**

### **Python/FastAPI Connection**
```python
import asyncpg
import ssl

async def get_db_connection():
    # SSL context for secure connections
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connection = await asyncpg.connect(
        host="postgres",
        port=5432,
        user="appuser",
        password=os.getenv("POSTGRES_PASSWORD"),
        database="appdb",
        ssl=ssl_context
    )
    return connection
```

### **Node.js Connection**
```javascript
const { Pool } = require('pg');

const pool = new Pool({
    host: 'postgres',
    port: 5432,
    user: 'appuser',
    password: process.env.POSTGRES_PASSWORD,
    database: 'appdb',
    ssl: {
        require: true,
        rejectUnauthorized: false  // For self-signed certificates
    },
    max: 20,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 2000,
});
```

---

## 📚 **Additional Resources**

- [PostgreSQL Official Documentation](https://www.postgresql.org/docs/16/)
- [PostgreSQL Security Guidelines](https://www.postgresql.org/docs/16/security.html)
- [Docker PostgreSQL Best Practices](https://docs.docker.com/samples/postgresql/)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)

---

**Your PostgreSQL deployment is now production-ready with enterprise-grade security, performance optimization, and operational excellence! 🚀**