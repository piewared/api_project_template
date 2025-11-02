# TLS Connection Testing and Certificate Verification

This document provides comprehensive testing procedures to verify that PostgreSQL TLS is properly configured and that clients can securely connect with full certificate verification.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Server-Side TLS Configuration](#server-side-tls-configuration)
- [Client-Side Certificate Verification](#client-side-certificate-verification)
- [Testing Procedures](#testing-procedures)
- [SSL Modes Explained](#ssl-modes-explained)
- [Troubleshooting](#troubleshooting)
- [Security Best Practices](#security-best-practices)

## Overview

PostgreSQL uses a protocol-specific TLS handshake, which means you cannot use standard tools like `openssl s_client` directly to test TLS connections. Instead, you must use PostgreSQL-specific clients like `psql`.

### Key Components

**Server-Side (PostgreSQL):**
- `server.crt` - Server certificate (including intermediate CA chain)
- `server.key` - Server private key
- These files must be readable by the PostgreSQL process

**Client-Side (Application/psql):**
- `ca-bundle.crt` - CA certificate bundle (root + intermediate CAs)
- Used to verify the server's certificate authenticity

## Prerequisites

Before testing, ensure:

1. PostgreSQL is running with TLS enabled in `postgresql.conf`:
   ```ini
   ssl = on
   ssl_cert_file = '/etc/postgresql/ssl/server.crt'
   ssl_key_file = '/etc/postgresql/ssl/server.key'
   ssl_min_protocol_version = 'TLSv1.2'
   ssl_max_protocol_version = 'TLSv1.3'
   ```

2. Certificate files have been generated:
   ```bash
   ./infra/secrets/generate_secrets.sh
   ```

3. You have the required credentials:
   - Database username and password
   - Path to `ca-bundle.crt`

## Server-Side TLS Configuration

### 1. Verify Certificate Files Exist in Container

```bash
docker exec <postgres-container-name> ls -l /etc/postgresql/ssl/server.crt /etc/postgresql/ssl/server.key
```

**Expected output:**
```
-rw-r--r-- 1 postgres postgres 4492 Oct 13 19:58 /etc/postgresql/ssl/server.crt
-rw------- 1 postgres postgres 1708 Oct 13 19:58 /etc/postgresql/ssl/server.key
```

### 2. Inspect Server Certificate

```bash
docker exec <postgres-container-name> openssl x509 -in /etc/postgresql/ssl/server.crt -text -noout
```

Verify:
- Valid date range (Not Before/Not After)
- Correct Subject Alternative Names (SANs)
- Proper issuer (your Intermediate CA)

### 3. Validate Private Key

```bash
docker exec <postgres-container-name> openssl rsa -in /etc/postgresql/ssl/server.key -check
```

**Expected output:**
```
RSA key ok
```

### 4. Check PostgreSQL Logs

```bash
docker logs <postgres-container-name> 2>&1 | grep -i ssl
```

Look for:
```
SSL: existing certificate and key found at /etc/postgresql/ssl/server.crt / /etc/postgresql/ssl/server.key
```

## Client-Side Certificate Verification

### Test 1: Basic TLS Connection (No Verification)

Test that TLS is enabled and working:

```bash
# From host machine
PGPASSWORD=$(cat ./infra/secrets/keys/postgres_app_user_pw.txt) \
psql "postgresql://appuser@localhost:5432/postgres?sslmode=require" \
-c "SELECT version();"
```

**What this tests:**
- Connection is encrypted
- Server presents a certificate
- Does NOT verify certificate authenticity

### Test 2: Verify TLS Protocol and Cipher

Confirm the TLS version and cipher suite in use:

```bash
PGPASSWORD=$(cat ./infra/secrets/keys/postgres_app_user_pw.txt) \
psql "postgresql://appuser@localhost:5432/postgres?sslmode=require" \
-c "SELECT ssl, version, cipher, bits FROM pg_stat_ssl WHERE pid = pg_backend_pid();"
```

**Expected output:**
```
 ssl | version |         cipher         | bits 
-----+---------+------------------------+------
 t   | TLSv1.3 | TLS_AES_256_GCM_SHA384 |  256
```

**Interpretation:**
- `ssl = t` - SSL/TLS is active
- `version = TLSv1.3` - Modern TLS protocol
- `cipher = TLS_AES_256_GCM_SHA384` - Strong encryption
- `bits = 256` - 256-bit encryption

### Test 3: Verify Certificate Against CA Bundle

Test that the server's certificate is signed by a trusted CA:

```bash
PGPASSWORD=$(cat ./infra/secrets/keys/postgres_app_user_pw.txt) \
psql "postgresql://appuser@localhost:5432/postgres?sslmode=verify-ca&sslrootcert=./infra/secrets/certs/ca-bundle.crt" \
-c "SELECT version();"
```

**What this tests:**
- Connection is encrypted
- Server certificate is verified against the CA bundle
- Certificate chain is valid (intermediate + root CA)

### Test 4: Full Certificate Verification (with Hostname)

Test complete certificate verification including hostname matching:

```bash
PGPASSWORD=$(cat ./infra/secrets/keys/postgres_app_user_pw.txt) \
psql "postgresql://appuser@localhost:5432/postgres?sslmode=verify-full&sslrootcert=./infra/secrets/certs/ca-bundle.crt" \
-c "SELECT ssl, version, cipher, bits FROM pg_stat_ssl WHERE pid = pg_backend_pid();"
```

**What this tests:**
- Connection is encrypted
- Server certificate is verified against the CA bundle
- Hostname matches the certificate's Common Name or SANs

### Test 5: Negative Test - Invalid CA Bundle

Verify that certificate verification is actually enforced:

```bash
PGPASSWORD=$(cat ./infra/secrets/keys/postgres_app_user_pw.txt) \
psql "postgresql://appuser@localhost:5432/postgres?sslmode=verify-ca&sslrootcert=/dev/null" \
-c "SELECT version();" 2>&1
```

**Expected output:**
```
psql: error: connection to server at "localhost" (127.0.0.1), port 5432 failed: 
could not read root certificate file "/dev/null": no certificate or crl found
```

**Interpretation:**
If this test succeeds (returns version), certificate verification is NOT working properly!

## Testing Procedures

### From Inside the PostgreSQL Container

```bash
# Enter the container
docker exec -it <postgres-container-name> bash

# Test basic connection
PGPASSWORD=$(cat /run/secrets/postgres_app_user_pw) \
psql "postgresql://appuser@localhost:5432/postgres?sslmode=require" \
-c "SELECT version();"

# Check SSL status
PGPASSWORD=$(cat /run/secrets/postgres_app_user_pw) \
psql "postgresql://appuser@localhost:5432/postgres?sslmode=require" \
-c "SELECT * FROM pg_stat_ssl WHERE pid = pg_backend_pid();"
```

### From Host Machine

```bash
# Test with CA verification
PGPASSWORD=$(cat ./infra/secrets/keys/postgres_app_user_pw.txt) \
psql "postgresql://appuser@localhost:5432/postgres?sslmode=verify-ca&sslrootcert=./infra/secrets/certs/ca-bundle.crt" \
-c "SELECT version();"
```

### From Application Container

```bash
# Example for a Python application container
docker exec <app-container-name> python -c "
import psycopg2
conn = psycopg2.connect(
    host='postgres',
    port=5432,
    dbname='appdb',
    user='appuser',
    password='<password>',
    sslmode='verify-full',
    sslrootcert='/path/to/ca-bundle.crt'
)
print('Connection successful!')
conn.close()
"
```

## SSL Modes Explained

PostgreSQL supports several SSL modes with increasing security levels:

| Mode | Encrypted | Verify Certificate | Verify Hostname | Use Case |
|------|-----------|-------------------|-----------------|----------|
| `disable` | ❌ | ❌ | ❌ | Development only |
| `allow` | If available | ❌ | ❌ | Legacy compatibility |
| `prefer` | If available | ❌ | ❌ | Legacy compatibility |
| `require` | ✅ | ❌ | ❌ | Encryption without CA trust |
| `verify-ca` | ✅ | ✅ | ❌ | Production (self-signed CA) |
| `verify-full` | ✅ | ✅ | ✅ | **Production (recommended)** |

### Recommended Settings by Environment

**Development:**
```
sslmode=require
```

**Staging/Production:**
```
sslmode=verify-full&sslrootcert=/path/to/ca-bundle.crt
```

## Troubleshooting

### Issue: "no peer certificate available"

**Symptom:**
```
openssl s_client -connect localhost:5432 -CAfile ca-bundle.crt
CONNECTED(00000003)
no peer certificate available
```

**Cause:** PostgreSQL uses a protocol-specific TLS handshake, not standard TLS.

**Solution:** Use `psql` or other PostgreSQL clients to test, not `openssl s_client`.

### Issue: "pg_hba.conf rejects connection"

**Symptom:**
```
FATAL: pg_hba.conf rejects connection for host "X.X.X.X", user "username", database "dbname", no encryption
```

**Cause:** Connection is not using SSL, but `pg_hba.conf` requires it.

**Solution:** 
1. Check `pg_hba.conf` for `hostssl` rules
2. Ensure client is using `sslmode=require` or higher
3. Verify client is connecting from an allowed subnet

### Issue: "could not read root certificate file"

**Symptom:**
```
could not read root certificate file "/path/to/ca-bundle.crt": No such file or directory
```

**Cause:** CA bundle file not found or not accessible.

**Solution:**
1. Verify the file exists: `ls -l /path/to/ca-bundle.crt`
2. Check file permissions: `chmod 644 ca-bundle.crt`
3. For Docker containers, ensure the file is mounted or copied into the container

### Issue: "certificate verify failed"

**Symptom:**
```
SSL error: certificate verify failed
```

**Cause:** Server certificate not signed by a CA in the bundle, or certificate chain is incomplete.

**Solution:**
1. Verify the CA bundle contains all necessary CAs:
   ```bash
   openssl crl2pkcs7 -nocrl -certfile ca-bundle.crt | openssl pkcs7 -print_certs -noout
   ```
2. Check the server certificate chain:
   ```bash
   openssl verify -CAfile ca-bundle.crt server.crt
   ```
3. Regenerate certificates if necessary:
   ```bash
   ./infra/secrets/generate_secrets.sh
   ```

### Issue: TLS version mismatch

**Symptom:**
```
SSL error: unsupported protocol
```

**Cause:** Client and server don't support compatible TLS versions.

**Solution:**
1. Check server TLS configuration in `postgresql.conf`:
   ```ini
   ssl_min_protocol_version = 'TLSv1.2'
   ssl_max_protocol_version = 'TLSv1.3'
   ```
2. Check client TLS support (varies by driver)

## Security Best Practices

### 1. Always Use `verify-full` in Production

```python
# Python example
conn = psycopg2.connect(
    host='postgres.example.com',
    sslmode='verify-full',
    sslrootcert='/path/to/ca-bundle.crt'
)
```

### 2. Protect Certificate Files

```bash
# Server private key should be read-only by PostgreSQL user
chmod 400 server.key
chown postgres:postgres server.key

# CA bundle should be readable by application
chmod 644 ca-bundle.crt
```

### 3. Use Strong TLS Configuration

In `postgresql.conf`:
```ini
ssl = on
ssl_prefer_server_ciphers = on
ssl_ciphers = 'HIGH:!aNULL:!MD5'
ssl_min_protocol_version = 'TLSv1.2'
ssl_max_protocol_version = 'TLSv1.3'
```

### 4. Enforce SSL in pg_hba.conf

```
# Explicitly reject non-SSL connections
hostnossl all all 0.0.0.0/0 reject
hostnossl all all ::/0 reject

# Only allow SSL connections
hostssl all all 172.30.50.0/24 scram-sha-256
```

### 5. Regular Certificate Rotation

- Monitor certificate expiration dates
- Rotate certificates before expiration
- Test rotation in staging before production
- Keep backup copies of previous certificates

### 6. Monitor TLS Connections

Query active connections and their TLS status:

```sql
SELECT 
    datname,
    usename,
    client_addr,
    ssl,
    version,
    cipher,
    bits
FROM pg_stat_ssl
JOIN pg_stat_activity ON pg_stat_ssl.pid = pg_stat_activity.pid
WHERE ssl = true;
```

## Connection String Examples

### PostgreSQL URI Format

```bash
# Basic TLS (encryption only)
postgresql://user:password@host:5432/dbname?sslmode=require

# With CA verification
postgresql://user:password@host:5432/dbname?sslmode=verify-ca&sslrootcert=/path/to/ca-bundle.crt

# Full verification (hostname + CA)
postgresql://user:password@host:5432/dbname?sslmode=verify-full&sslrootcert=/path/to/ca-bundle.crt
```

### Environment Variables

```bash
export PGSSLMODE=verify-full
export PGSSLROOTCERT=/path/to/ca-bundle.crt
export PGHOST=localhost
export PGPORT=5432
export PGDATABASE=appdb
export PGUSER=appuser
export PGPASSWORD=<password>

psql -c "SELECT version();"
```

### Application Configuration (Python)

```python
import psycopg2

# Development
conn = psycopg2.connect(
    host='localhost',
    port=5432,
    dbname='appdb',
    user='appuser',
    password='secret',
    sslmode='require'
)

# Production
conn = psycopg2.connect(
    host='postgres.example.com',
    port=5432,
    dbname='appdb',
    user='appuser',
    password='secret',
    sslmode='verify-full',
    sslrootcert='/app/secrets/ca-bundle.crt'
)
```

## Quick Reference Commands

```bash
# List generated certificates
./infra/secrets/generate_secrets.sh -l

# Verify certificate chain
openssl verify -CAfile ./infra/secrets/certs/ca-bundle.crt ./infra/secrets/certs/postgres/server-chain-no-root.crt

# Test basic TLS connection
PGPASSWORD=$(cat ./infra/secrets/keys/postgres_app_user_pw.txt) \
psql "postgresql://appuser@localhost:5432/postgres?sslmode=require" -c "SELECT version();"

# Test with CA verification
PGPASSWORD=$(cat ./infra/secrets/keys/postgres_app_user_pw.txt) \
psql "postgresql://appuser@localhost:5432/postgres?sslmode=verify-ca&sslrootcert=./infra/secrets/certs/ca-bundle.crt" -c "SELECT version();"

# Test with full verification
PGPASSWORD=$(cat ./infra/secrets/keys/postgres_app_user_pw.txt) \
psql "postgresql://appuser@localhost:5432/postgres?sslmode=verify-full&sslrootcert=./infra/secrets/certs/ca-bundle.crt" -c "SELECT version();"

# Check TLS status
PGPASSWORD=$(cat ./infra/secrets/keys/postgres_app_user_pw.txt) \
psql "postgresql://appuser@localhost:5432/postgres?sslmode=require" \
-c "SELECT ssl, version, cipher, bits FROM pg_stat_ssl WHERE pid = pg_backend_pid();"

# View all SSL connections
PGPASSWORD=$(cat ./infra/secrets/keys/postgres_password.txt) \
psql "postgresql://postgres@localhost:5432/postgres?sslmode=require" \
-c "SELECT * FROM pg_stat_ssl;"
```

## Related Documentation

- [Secrets Management](../../SECRETS_MANAGEMENT.md) - Certificate generation and management
- [PostgreSQL SSL Documentation](https://www.postgresql.org/docs/current/ssl-tcp.html)
- [Security Configuration](../../security.md) - Overall security practices
