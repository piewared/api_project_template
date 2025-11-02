# Secrets Management Documentation

This document provides comprehensive guidance on managing secrets in the application infrastructure, including password generation, PKI certificate management, and Docker Compose integration.

## Table of Contents

1. [Overview](#overview)
2. [Secret Generation Script](#secret-generation-script)
3. [File Structure and Purposes](#file-structure-and-purposes)
4. [Docker Compose Integration](#docker-compose-integration)
5. [PKI Certificate Management](#pki-certificate-management)
6. [Security Best Practices](#security-best-practices)
7. [Deployment Scenarios](#deployment-scenarios)
8. [Troubleshooting](#troubleshooting)

## Overview

The application uses a centralized secrets management system based on:

- **File-based secrets**: Stored in `./infra/secrets/` directory
- **Docker Compose secrets**: Mounted as files in containers
- **PKI infrastructure**: Internal certificate authority for TLS
- **Universal entrypoint**: Secure secret handling in containers

### Key Features

- ✅ **Cryptographically secure** password generation
- ✅ **Complete PKI infrastructure** with root and intermediate CAs
- ✅ **Comprehensive TLS certificates** with Docker and Fly.io SANs
- ✅ **Automated backup** of existing secrets
- ✅ **Permission management** (600 for keys, 644 for certificates)
- ✅ **Verification tools** for secret validation

## Secret Generation Script

The `secrets/generate_secrets.sh` script is the central tool for managing all application secrets and certificates.

### Basic Usage

```bash
# Generate all secrets (passwords and OIDC client secrets)
./infra/secrets/generate_secrets.sh

# Generate PKI certificates only
./infra/secrets/generate_secrets.sh --generate-pki

# Generate everything (secrets + PKI)
./infra/secrets/generate_secrets.sh --generate-pki

# List all generated files
./infra/secrets/generate_secrets.sh --list

# Verify existing secrets
./infra/secrets/generate_secrets.sh --verify

# Show help
./infra/secrets/generate_secrets.sh --help
```

### Advanced Options

```bash
# Force overwrite without backup
./infra/secrets/generate_secrets.sh --force

# Force regenerate CA certificates (dangerous!)
./infra/secrets/generate_secrets.sh --generate-pki --force-ca

# Backup existing secrets only
./infra/secrets/generate_secrets.sh --backup-only

# Verify secrets meet security requirements
./infra/secrets/generate_secrets.sh --verify
```

## File Structure and Purposes

### Directory Structure

```
infra/secrets/
├── keys/                           # Application passwords and secrets
├── certs/                          # PKI certificates and keys
│   ├── root-ca.crt                # Root Certificate Authority (public)
│   ├── root-ca.key                # Root CA private key (sensitive)
│   ├── root-ca.srl                # Root CA serial number tracker
│   ├── intermediate-ca.crt        # Intermediate Certificate Authority (public)
│   ├── intermediate-ca.key        # Intermediate CA private key (sensitive)
│   ├── intermediate-ca.srl        # Intermediate CA serial number tracker
│   ├── ca-bundle.crt              # CA bundle for client cert validation
│   ├── postgres/                  # PostgreSQL TLS certificates
│   ├── redis/                     # Redis TLS certificates
│   └── temporal/                  # Temporal TLS certificates
└── backup_YYYYMMDD_HHMMSS/        # Automatic backups
```

### Application Secrets (keys/ directory)

| File | Purpose | Used By | Security Level |
|------|---------|---------|----------------|
| `postgres_password.txt` | PostgreSQL superuser password | Database superuser | **Critical** |
| `postgres_app_user_pw.txt` | Application database user password | App connections | **High** |
| `postgres_app_owner_pw.txt` | Database owner user password | Schema management | **High** |
| `postgres_app_ro_pw.txt` | Read-only database user password | Backup/reporting | **Medium** |
| `redis_password.txt` | Redis authentication password | Cache/sessions | **High** |
| `session_signing_secret.txt` | JWT session signing key | Authentication | **Critical** |
| `csrf_signing_secret.txt` | CSRF protection secret | Security middleware | **High** |
| `oidc_google_client_secret.txt` | Google OAuth client secret | Google SSO | **Medium** |
| `oidc_microsoft_client_secret.txt` | Microsoft OAuth client secret | Microsoft SSO | **Medium** |
| `oidc_keycloak_client_secret.txt` | Keycloak client secret | Internal SSO | **Medium** |

### PKI Certificates (certs/ directory)

#### Root Certificate Authority

| File | Purpose | Validity | Key Size |
|------|---------|----------|----------|
| `root-ca.crt` | Root CA public certificate | 10 years | 4096-bit |
| `root-ca.key` | Root CA private key | - | 4096-bit |
| `root-ca.srl` | Root CA serial number tracker | - | Text file |

#### Intermediate Certificate Authority

| File | Purpose | Validity | Key Size |
|------|---------|----------|----------|
| `intermediate-ca.crt` | Intermediate CA public certificate | 5 years | 4096-bit |
| `intermediate-ca.key` | Intermediate CA private key | - | 4096-bit |
| `intermediate-ca.srl` | Intermediate CA serial number tracker | - | Text file |

#### CA Bundle

| File | Purpose | Contents |
|------|---------|----------|
| `ca-bundle.crt` | Client certificate validation | Intermediate CA + Root CA |

#### Service Certificates (per service: postgres, redis, temporal)

| File | Purpose | Validity | Key Size |
|------|---------|----------|----------|
| `server.crt` | Service certificate | 1 year | 2048-bit |
| `server.key` | Service private key | - | 2048-bit |
| `server-chain.crt` | Full certificate chain | - | Combined |
| `server-chain-no-root.crt` | Chain without root CA | - | Combined |

#### Certificate Chain Options

**Full Chain (`server-chain.crt`)**:
- Service Certificate + Intermediate CA + Root CA
- **Recommended for internal PKI**
- Self-contained, simpler deployment
- Perfect for Docker containers

**Chain Without Root (`server-chain-no-root.crt`)**:
- Service Certificate + Intermediate CA only
- Industry standard for public CAs
- Requires root CA in client trust store
- Smaller network overhead

#### Subject Alternative Names (SANs)

Each service certificate includes comprehensive SANs for different deployment scenarios:

**PostgreSQL**:
- `postgres`, `postgres.backend`, `app_data_postgres_db`
- `database`, `db`, `localhost`
- `*.fly.dev`, `*.internal`
- IP: `127.0.0.1`, `::1`

**Redis**:
- `redis`, `redis.backend`, `cache`
- `localhost`, `*.fly.dev`, `*.internal`
- IP: `127.0.0.1`, `::1`

**Temporal**:
- `temporal`, `temporal.backend`, `temporal-server`
- `workflow`, `localhost`, `*.fly.dev`, `*.internal`
- IP: `127.0.0.1`, `::1`

## Docker Compose Integration

### Test Environment (docker-compose.test.yml)

The test environment uses Docker Compose native secrets management:

```yaml
services:
  postgres:
    secrets:
      - postgres_password
      - postgres_app_owner_pw
      - postgres_app_user_pw
      - postgres_app_ro_pw
      - source: postgres_tls_cert
        target: server.crt
        mode: 0400
      - source: postgres_tls_key
        target: server.key
        mode: 0400

secrets:
  postgres_password:
    file: ./infra/secrets/keys/postgres_password.txt
  postgres_tls_cert:
    file: ./infra/secrets/certs/postgres/server.crt
  postgres_tls_key:
    file: ./infra/secrets/certs/postgres/server.key
```

#### Universal Entrypoint Integration

Services use the universal entrypoint for secure secret handling:

```yaml
environment:
  SECRETS_SOURCE_DIR: /run/secrets      # Docker secrets mount point
  SECRETS_TARGET_DIR: /app/secrets      # Application secrets directory
  CERTS_TARGET_DIR: /etc/postgresql/ssl # Certificate target directory
  CREATE_ENV_VARS: "true"              # Create environment variables
  SKIP_USER_SWITCH: "false"            # Enable user switching
```

### Production Environment (docker-compose.prod.yml)

Production uses a hybrid approach with volume mounts and tmpfs:

```yaml
services:
  app:
    volumes:
      # Mount host secrets (readable by root)
      - ./secrets:/mnt/host_secrets:ro
    tmpfs:
      # Secure tmpfs for runtime secrets (owned by appuser)
      - /run/secrets:rw,noexec,nosuid,nodev,size=64k,uid=1001,gid=1001
```

#### Security Features

- **Volume mounts**: Host secrets mounted read-only
- **tmpfs**: Runtime secrets in memory-only filesystem
- **User isolation**: Secrets owned by application user
- **Restricted permissions**: `noexec`, `nosuid`, `nodev`

### Secret Access Patterns

#### In Containers

Secrets are accessible via multiple methods:

1. **File-based** (recommended):
   ```bash
   POSTGRES_PASSWORD=$(cat /run/secrets/postgres_password)
   ```

2. **Environment variables** (when CREATE_ENV_VARS=true):
   ```bash
   echo $POSTGRES_PASSWORD
   ```

3. **Application configuration**:
   ```python
   # Python example
   with open('/run/secrets/postgres_password') as f:
       password = f.read().strip()
   ```

#### PostgreSQL TLS Configuration

**Option 1: Full Certificate Chain (Recommended)**
```bash
ssl_cert_file = '/etc/ssl/certs/server-chain.crt'
ssl_key_file = '/etc/ssl/private/server.key'
ssl_ca_file = '/etc/ssl/certs/ca-bundle.crt'
```

**Option 2: Chain Without Root CA**
```bash
ssl_cert_file = '/etc/ssl/certs/server-chain-no-root.crt'
ssl_key_file = '/etc/ssl/private/server.key'
ssl_ca_file = '/etc/ssl/certs/ca-bundle.crt'
```

#### Redis TLS Configuration

```bash
tls-cert-file /etc/redis/ssl/server-chain.crt
tls-key-file /etc/redis/ssl/server.key
tls-ca-cert-file /etc/redis/ssl/ca-bundle.crt
```

## PKI Certificate Management

### Certificate Hierarchy

```
Root CA (10 years, 4096-bit)
└── Intermediate CA (5 years, 4096-bit, pathlen:0)
    ├── PostgreSQL Certificate (1 year, 2048-bit)
    ├── Redis Certificate (1 year, 2048-bit)
    └── Temporal Certificate (1 year, 2048-bit)
```

### Certificate Serial Number Files (.srl)

The `.srl` files are **certificate serial number trackers** that maintain the next serial number to be assigned by each Certificate Authority. These files are critical for PKI operations:

#### Purpose
- **Unique identification**: Each certificate must have a unique serial number within a CA
- **Certificate revocation**: Serial numbers are used in Certificate Revocation Lists (CRLs)
- **Audit trails**: Track the sequence of certificate issuance
- **Standards compliance**: Required by X.509 certificate standards

#### Contents
- **Single line**: Contains the next serial number in hexadecimal format
- **Auto-increment**: Updated automatically each time a certificate is issued
- **Persistence**: Must be preserved to avoid serial number collisions

#### Example
```bash
# View current serial number
cat certs/root-ca.srl
# Output: 1000000000000002

cat certs/intermediate-ca.srl  
# Output: 1000000000000003
```

#### Importance
- **NEVER delete** these files - serial number collisions can break PKI trust
- **Backup with CA keys** - essential for CA recovery
- **Monitor growth** - indicates certificate issuance activity

### Certificate Extensions

#### Root CA
- `basicConstraints = critical, CA:TRUE`
- `keyUsage = critical, keyCertSign, cRLSign`
- `subjectKeyIdentifier = hash`
- `authorityKeyIdentifier = keyid:always,issuer:always`

#### Intermediate CA
- `basicConstraints = critical, CA:TRUE, pathlen:0`
- `keyUsage = critical, keyCertSign, cRLSign`
- `subjectKeyIdentifier = hash`
- `authorityKeyIdentifier = keyid:always,issuer:always`

#### Service Certificates
- `basicConstraints = CA:FALSE`
- `keyUsage = critical, digitalSignature, keyEncipherment`
- `extendedKeyUsage = serverAuth, clientAuth`
- `subjectKeyIdentifier = hash`
- `authorityKeyIdentifier = keyid:always,issuer:always`
- `subjectAltName = [comprehensive DNS and IP names]`

### Certificate Renewal

Service certificates expire after 1 year and should be renewed:

```bash
# Regenerate all service certificates (keeps existing CAs)
./infra/secrets/generate_secrets.sh --generate-pki

# Force regenerate everything including CAs (use with caution)
./infra/secrets/generate_secrets.sh --generate-pki --force-ca
```

### Certificate Verification

```bash
# Verify all secrets and certificates
./infra/secrets/generate_secrets.sh --verify

# Manual certificate verification
openssl x509 -in certs/postgres/server.crt -text -noout
openssl verify -CAfile certs/root-ca.crt -untrusted certs/intermediate-ca.crt certs/postgres/server.crt
```

## Security Best Practices

### File Permissions

| File Type | Permissions | Owner | Purpose |
|-----------|-------------|-------|---------|
| Private keys (*.key) | 600 | app user | Read/write by owner only |
| Certificates (*.crt) | 644 | app user | Read by all, write by owner |
| Passwords (*.txt) | 600 | app user | Read/write by owner only |

### Password Security

- **Minimum lengths**: 24 characters for database passwords, 32+ for signing secrets
- **Character sets**: Mixed case, numbers, safe special characters
- **Generation**: Cryptographically secure random generation using OpenSSL
- **Storage**: File-based with restrictive permissions

### Certificate Security

- **Key sizes**: 4096-bit for CAs, 2048-bit for service certificates
- **Validity periods**: Long for CAs (5-10 years), short for services (1 year)
- **Path length constraints**: Intermediate CA has `pathlen:0`
- **Extensions**: Appropriate key usage and extended key usage
- **Serial number integrity**: `.srl` files must be preserved to prevent serial collisions
- **Serial number backup**: Include `.srl` files in CA backup procedures

### Backup Strategy

- **Automatic backups**: Created before regenerating secrets
- **Timestamped directories**: `backup_YYYYMMDD_HHMMSS/`
- **Complete structure**: Preserves directory hierarchy
- **Retention**: Manual cleanup recommended

## Deployment Scenarios

### Development Environment

```bash
# Generate all secrets for development
./infra/secrets/generate_secrets.sh --generate-pki

# Start test environment
docker-compose -f docker-compose.test.yml up
```

### Production Environment

```bash
# Generate production secrets
./infra/secrets/generate_secrets.sh --generate-pki

# Verify security
./infra/secrets/generate_secrets.sh --verify

# Deploy to production
docker-compose -f docker-compose.prod.yml up -d
```

### Fly.io Deployment

The certificates include `*.fly.dev` SANs for Fly.io compatibility:

```bash
# Certificates already include Fly.io SANs
# Deploy with generated certificates
fly deploy
```

### Kubernetes Deployment

Convert file-based secrets to Kubernetes secrets:

```bash
# Create Kubernetes secrets from files
kubectl create secret generic postgres-secrets \
  --from-file=password=secrets/keys/postgres_password.txt \
  --from-file=app-user-pw=secrets/keys/postgres_app_user_pw.txt

kubectl create secret tls postgres-tls \
  --cert=secrets/certs/postgres/server-chain.crt \
  --key=secrets/certs/postgres/server.key
```

## Troubleshooting

### Common Issues

#### Permission Denied Errors

```bash
# Fix file permissions
./infra/secrets/generate_secrets.sh --verify
# or manually:
chmod 600 secrets/keys/*.txt
chmod 600 secrets/certs/*/*.key
chmod 644 secrets/certs/*.crt
```

#### Certificate Validation Errors

```bash
# Check certificate chain
openssl crl2pkcs7 -nocrl -certfile secrets/certs/postgres/server-chain.crt | \
  openssl pkcs7 -print_certs -noout

# Verify certificate against CA
openssl verify -CAfile secrets/certs/root-ca.crt \
  -untrusted secrets/certs/intermediate-ca.crt \
  infra/secrets/certs/postgres/server.crt
```

#### Docker Secrets Not Found

```bash
# Check file paths in docker-compose.yml
ls -la secrets/keys/postgres_password.txt
ls -la secrets/certs/postgres/server.crt

# Verify Docker Compose syntax
docker-compose config
```

#### TLS Handshake Failures

1. **Check certificate expiration**:
   ```bash
   openssl x509 -in secrets/certs/postgres/server.crt -noout -dates
   ```

2. **Verify SANs match hostname**:
   ```bash
   openssl x509 -in secrets/certs/postgres/server.crt -noout -ext subjectAltName
   ```

3. **Test TLS connection**:
   ```bash
   openssl s_client -connect postgres:5432 -starttls postgres
   ```

### Regeneration Scenarios

#### Compromised Secrets

```bash
# Backup existing secrets
./infra/secrets/generate_secrets.sh --backup-only

# Force regenerate all secrets
./infra/secrets/generate_secrets.sh --force --generate-pki --force-ca

# Restart services
docker-compose down && docker-compose up -d
```

#### Certificate Expiration

```bash
# Check expiration dates
./infra/secrets/generate_secrets.sh --verify

# Regenerate service certificates only (preserves CA)
./infra/secrets/generate_secrets.sh --generate-pki

# Restart affected services
docker-compose restart postgres redis temporal
```

#### Serial Number File Issues

```bash
# Check serial number file contents
cat secrets/certs/root-ca.srl
cat secrets/certs/intermediate-ca.srl

# Missing serial files (⚠️ DANGER: May cause serial collisions)
# If .srl files are accidentally deleted, you can recreate them:
echo "1000000000000001" > secrets/certs/root-ca.srl
echo "1000000000000001" > secrets/certs/intermediate-ca.srl
# ⚠️ WARNING: Only do this if you're certain no certificates exist with those serials

# Corrupted serial files
# Restore from backup or increment to a safe value:
echo "$(printf '%040X' $((0x$(cat secrets/certs/root-ca.srl) + 100)))" > secrets/certs/root-ca.srl
```

#### CA Certificate Compromise

```bash
# ⚠️  WARNING: This invalidates all existing certificates!
./infra/secrets/generate_secrets.sh --generate-pki --force-ca

# All services must be restarted
docker-compose down && docker-compose up -d
```

### Monitoring and Maintenance

#### Regular Tasks

1. **Weekly**: Verify secret integrity
   ```bash
   ./infra/secrets/generate_secrets.sh --verify
   ```

2. **Monthly**: Check certificate expiration
   ```bash
   find secrets/certs -name "*.crt" -exec openssl x509 -in {} -noout -subject -dates \;
   ```

3. **Annually**: Rotate service certificates
   ```bash
   ./infra/secrets/generate_secrets.sh --generate-pki
   ```

4. **5 years**: Plan intermediate CA renewal
5. **10 years**: Plan root CA renewal

#### Backup Verification

```bash
# Test backup restoration
cp -r secrets/backup_YYYYMMDD_HHMMSS/* secrets/
./infra/secrets/generate_secrets.sh --verify
```

---

## Summary

This secrets management system provides:

- **Complete automation** for password and certificate generation
- **Production-ready security** with proper permissions and encryption
- **Flexible deployment** support for Docker, Kubernetes, and cloud platforms
- **Comprehensive PKI** with industry-standard certificate hierarchy
- **Operational simplicity** with backup, verification, and monitoring tools

The system balances security, automation, and operational simplicity to provide a robust foundation for application secrets management across all deployment scenarios.