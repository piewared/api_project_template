# Secrets Directory

This directory contains sensitive configuration files, credentials, and PKI certificates for production deployments.

## � **Documentation**

For comprehensive documentation, see:
- **[Secrets Management Guide](../docs/prod/secrets/SECRETS_MANAGEMENT.md)** - Complete documentation on secrets, passwords, and PKI
- **[TLS Verification Testing](../docs/prod/secrets/TLS_VERIFICATION.md)** - Guide to testing TLS connectivity and certificate verification

## 🚀 **Quick Start**

Use the automated `generate_secrets.sh` script to create all required secrets and certificates:

```bash
# Generate all secrets and PKI certificates
./secrets/generate_secrets.sh

# Verify all secrets and certificates
./secrets/generate_secrets.sh -v

# List all generated files
./secrets/generate_secrets.sh -l
```

## 🔧 **Secret Generation Script**

The `generate_secrets.sh` script provides automated generation of:
- **Passwords and secrets** - Cryptographically secure random values
- **PKI certificates** - Complete certificate authority and server certificates
- **CA bundles** - Combined certificate chains for client verification

### **Usage**

```bash
./generate_secrets.sh [OPTIONS]

Options:
  -h, --help           Show this help message and exit
  -f, --force          Overwrite existing secrets without backup
  -b, --backup-only    Only backup existing secrets, don't generate new ones
  -v, --verify         Verify existing secrets and certificates
  -l, --list           List all secret files, certificates, and their details
  -s, --skip-pki       Skip PKI certificate generation (only generate passwords)
```

### **What Gets Generated**

#### **Passwords & Secrets** (`keys/` directory)
- Database passwords (postgres, app users)
- Session signing secrets
- CSRF protection keys
- OAuth/OIDC client secrets
- Backup encryption passwords

#### **PKI Certificates** (`certs/` directory)
- Root CA certificate and key
- Intermediate CA certificate and key
- Server certificates for PostgreSQL, Redis, Temporal
- Certificate chains (with and without root CA)
- **CA bundle** (`ca-bundle.crt`) - For client-side verification

See [Secrets Management Guide](../docs/prod/secrets/SECRETS_MANAGEMENT.md) for complete file listings and purposes.

### **Security Features**

- **Cryptographically Secure**: Uses OpenSSL and `/dev/urandom`
- **Automatic Backups**: Timestamped backups before regeneration
- **Secure Permissions**: Files created with 600/400 permissions
- **Certificate Validation**: Verifies certificate chains and expiration
- **Serial Number Tracking**: Maintains `.srl` files for CA operations

### **Common Commands**

```bash
# First-time setup - generate everything
./secrets/generate_secrets.sh

# Check status of all secrets and certificates
./secrets/generate_secrets.sh -v

# View all generated files with details
./secrets/generate_secrets.sh -l

# Regenerate only passwords (skip PKI)
./secrets/generate_secrets.sh -s

# Force regeneration (careful!)
./secrets/generate_secrets.sh -f

# Backup existing secrets without generating new ones
./secrets/generate_secrets.sh -b
```

## 🔐 **Testing TLS Connections**

After generating certificates, test PostgreSQL TLS connectivity:

```bash
# Test basic TLS connection
PGPASSWORD=$(cat ./secrets/keys/postgres_app_user_pw.txt) \
psql "postgresql://appuser@localhost:5432/postgres?sslmode=require" \
-c "SELECT version();"

# Test with full certificate verification
PGPASSWORD=$(cat ./secrets/keys/postgres_app_user_pw.txt) \
psql "postgresql://appuser@localhost:5432/postgres?sslmode=verify-full&sslrootcert=./secrets/certs/ca-bundle.crt" \
-c "SELECT version();"

# Check TLS protocol and cipher
PGPASSWORD=$(cat ./secrets/keys/postgres_app_user_pw.txt) \
psql "postgresql://appuser@localhost:5432/postgres?sslmode=require" \
-c "SELECT ssl, version, cipher, bits FROM pg_stat_ssl WHERE pid = pg_backend_pid();"
```

See [TLS Verification Guide](../docs/prod/secrets/TLS_VERIFICATION.md) for comprehensive testing procedures.

## 📁 **Directory Structure**

```
secrets/
├── generate_secrets.sh          # Automated generation script
├── README.md                    # This file
├── keys/                        # Passwords and secrets (600 permissions)
│   ├── postgres_password.txt
│   ├── postgres_app_user_pw.txt
│   ├── session_signing_secret.txt
│   └── ...
├── certs/                       # PKI certificates (400/644 permissions)
│   ├── ca-bundle.crt           # Combined CA bundle for clients
│   ├── root-ca.crt
│   ├── intermediate-ca.crt
│   ├── postgres/
│   │   ├── server.crt
│   │   ├── server.key
│   │   └── server-chain-no-root.crt
│   ├── redis/
│   └── temporal/
└── backup_YYYYMMDD_HHMMSS/     # Timestamped backups
```

## 🔒 **Manual Secret Creation**

If you need to create specific secrets manually:

```bash
# Database passwords
echo "your-secure-password-here" > secrets/keys/postgres_password.txt
chmod 600 secrets/keys/postgres_password.txt

# Session secrets (use base64 encoded values)
openssl rand -base64 32 > secrets/keys/session_signing_secret.txt
chmod 600 secrets/keys/session_signing_secret.txt
```

**Recommendation**: Use the automated script instead of manual creation to ensure proper entropy and security.

## 🛡️ **Security Best Practices**

### **File Permissions**
```bash
# Passwords and keys (read/write by owner only)
chmod 600 secrets/keys/*

# Certificates (read-only by owner)
chmod 400 secrets/certs/*/*.key

# Public certificates and chains
chmod 644 secrets/certs/*.crt
chmod 644 secrets/certs/*/*.crt
```

### **Password Requirements**
- **Minimum 24 characters** for database passwords
- **Mix of letters, numbers, and symbols**
- **No dictionary words**
- **Unique per environment** (dev/staging/prod)
- **Regular rotation** (every 90 days recommended)

### **Certificate Management**
- **Monitor expiration dates** (certificates are valid for 1 year)
- **Keep serial number files** (`.srl`) for CA operations
- **Maintain CA bundle** for client verification
- **Test TLS connectivity** after regeneration

### **Credential Management**
- Use **password managers** or **vault solutions** (HashiCorp Vault, AWS Secrets Manager)
- **Never commit** secrets to version control (`.gitignore` is configured)
- **Backup secrets securely** outside of the repository
- **Document access** in team password manager


## 🚨 **Security Checklist**

Before deploying to production:

- [ ] Run `./secrets/generate_secrets.sh` to generate all secrets and certificates
- [ ] Verify with `./secrets/generate_secrets.sh -v` (all checks should pass)
- [ ] Confirm file permissions with `./secrets/generate_secrets.sh -l`
- [ ] Test TLS connectivity (see [TLS Verification Guide](../docs/prod/secrets/TLS_VERIFICATION.md))
- [ ] Backup secrets securely outside the repository
- [ ] Use different credentials per environment (dev/staging/prod)
- [ ] Document certificate expiration dates
- [ ] Establish rotation schedule (90 days recommended)
- [ ] Configure monitoring for certificate expiration

## 🔄 **Secret Rotation**

### **Regular Rotation (Every 90 Days)**

```bash
# 1. Backup current secrets
./secrets/generate_secrets.sh -b

# 2. Generate new secrets (keeps PKI certificates)
./secrets/generate_secrets.sh -s

# 3. Restart services with new credentials
docker compose -f docker-compose.prod.yml restart

# 4. Verify services are healthy
docker compose -f docker-compose.prod.yml ps
```

### **Certificate Rotation (Before Expiration)**

```bash
# 1. Check certificate expiration
./secrets/generate_secrets.sh -v | grep "expires"

# 2. Backup everything
./secrets/generate_secrets.sh -b

# 3. Regenerate all (passwords + PKI)
./secrets/generate_secrets.sh

# 4. Restart all services
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d

# 5. Test TLS connectivity
# See docs/prod/secrets/TLS_VERIFICATION.md
```

### **Emergency Rotation (Compromise Suspected)**

```bash
# 1. Immediately stop services
docker compose -f docker-compose.prod.yml down

# 2. Force regenerate everything
./secrets/generate_secrets.sh -f

# 3. Restart with new secrets
docker compose -f docker-compose.prod.yml up -d

# 4. Monitor logs
docker compose -f docker-compose.prod.yml logs -f

# 5. Verify TLS is working
# Follow TLS verification procedures
```

## 📚 **Additional Resources**

- **[Secrets Management Guide](../docs/prod/secrets/SECRETS_MANAGEMENT.md)** - Complete reference for all secrets and certificates
- **[TLS Verification Testing](../docs/prod/secrets/TLS_VERIFICATION.md)** - Step-by-step TLS testing procedures
- **[Security Configuration](../docs/security.md)** - Overall security best practices
- **[Production Deployment](../docs/prod/PRODUCTION_DEPLOYMENT.md)** - Full deployment guide

## 🆘 **Troubleshooting**

### **Script won't generate secrets**
```bash
# Check dependencies
which openssl  # Should return path to openssl
test -c /dev/urandom && echo "OK" || echo "FAIL"

# Check permissions
ls -la secrets/
# Should show directories are writable
```

### **Certificate verification fails**
```bash
# Verify CA bundle
openssl crl2pkcs7 -nocrl -certfile secrets/certs/ca-bundle.crt | openssl pkcs7 -print_certs -noout

# Verify server certificate chain
openssl verify -CAfile secrets/certs/ca-bundle.crt secrets/certs/postgres/server-chain-no-root.crt

# Regenerate if needed
./secrets/generate_secrets.sh
```

### **TLS connection fails**
See the comprehensive troubleshooting section in [TLS Verification Guide](../docs/prod/secrets/TLS_VERIFICATION.md).

---

**⚠️ IMPORTANT SECURITY NOTICE**

- This entire `secrets/` directory is git-ignored
- **Never commit** actual secret values to version control
- **Always backup** secrets before regeneration
- **Test thoroughly** after any secret rotation
- **Monitor** certificate expiration dates
- **Use different credentials** for each environment

For questions or issues, see the detailed documentation in `docs/prod/secrets/`.