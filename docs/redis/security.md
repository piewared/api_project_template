# Redis Security

This document covers security considerations for Redis in development and production environments.

## Table of Contents

- [Security Overview](#security-overview)
- [Development Security](#development-security)
- [Production Security Requirements](#production-security-requirements)
- [Authentication](#authentication)
- [Network Security](#network-security)
- [Data Encryption](#data-encryption)
- [Access Control Lists (ACLs)](#access-control-lists-acls)
- [Dangerous Commands](#dangerous-commands)
- [Secrets Management](#secrets-management)
- [Attack Vectors and Mitigations](#attack-vectors-and-mitigations)
- [Security Checklist](#security-checklist)
- [Incident Response](#incident-response)

## Security Overview

### Development vs Production

| Security Feature | Development | Production |
|-----------------|-------------|------------|
| Authentication | None | Password required |
| Network Binding | `0.0.0.0:6380` (exposed to host) | `127.0.0.1:6379` (localhost only) |
| TLS/SSL | Disabled | Optional (recommended) |
| Dangerous Commands | Enabled | Disabled |
| ACLs | Not configured | Optional |
| Resource Limits | None | 512MB memory limit |
| Monitoring | Basic | Required (metrics, alerts) |
| Backups | Optional | Required (daily) |

### Threat Model

**Development** (Low Risk):
- Running on localhost
- No sensitive production data
- Trusted developer access only
- Fast iteration required

**Production** (High Risk):
- Stores user sessions and tokens
- Internet-facing application
- Potential data breach impact
- Compliance requirements (GDPR, HIPAA, etc.)

## Development Security

### Configuration

```yaml
# docker-compose.dev.yml
redis:
  image: redis:7-alpine
  container_name: api-forge-redis-dev
  ports:
    - "6380:6379"  # Exposed to host
  command: redis-server --appendonly yes
  networks:
    - dev-network
```

### Access

```bash
# Connect without password (development only)
redis-cli -p 6380 ping
# Returns: PONG

# All commands enabled
redis-cli -p 6380 KEYS '*'
redis-cli -p 6380 FLUSHDB
```

### Security Risks (Acceptable for Development)

⚠️ **No Authentication**: Any process on host can connect  
⚠️ **All Commands Enabled**: Can wipe database with FLUSHDB  
⚠️ **No Encryption**: Data transmitted in plaintext  
⚠️ **No Resource Limits**: Can exhaust memory  
⚠️ **No Monitoring**: No alerts for suspicious activity

**Why Acceptable**:
- Running on trusted developer machine
- No production data
- Fast development iteration
- Easy debugging

**Still Follow Basic Hygiene**:
- ✅ Don't expose to network (use localhost only)
- ✅ Don't store real user data in development
- ✅ Use separate Redis instance from production
- ✅ Clear data regularly

## Production Security Requirements

### Minimum Security Standards

1. ✅ **Password authentication enabled**
2. ✅ **Bound to localhost** (not exposed to internet)
3. ✅ **Dangerous commands disabled** (FLUSHDB, KEYS, etc.)
4. ⚠️ **TLS/SSL encryption** (optional but recommended)
5. ⚠️ **ACLs configured** (optional for fine-grained access)
6. ✅ **Resource limits enforced** (memory, connections)
7. ✅ **Monitoring and alerting** (health checks, metrics)
8. ✅ **Regular backups** (RDB + AOF)

### Configuration

```yaml
# docker-compose.prod.yml
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

## Authentication

### Password Authentication

#### Setting Password

**Generate Secure Password**:
```bash
# Generate 32-byte random password
openssl rand -base64 32 > infra/secrets/keys/redis_password.txt

# Example output: vX8kL3mP9qR2wT5nY7jH1dF6gK4bN0cM
```

**Store in Secrets**:
```bash
# Create secrets directory
mkdir -p infra/secrets/keys

# Set permissions (owner read-only)
chmod 600 infra/secrets/keys/redis_password.txt

# Add to .env
echo "REDIS_PASSWORD=$(cat infra/secrets/keys/redis_password.txt)" >> .env
```

**Docker Secrets** (Production):
```yaml
# docker-compose.prod.yml
secrets:
  redis_password:
    file: ./infra/secrets/keys/redis_password.txt

services:
  redis:
    secrets:
      - redis_password
    command: |
      sh -c '
        REDIS_PASSWORD=$$(cat /run/secrets/redis_password)
        redis-server /usr/local/etc/redis/redis.conf --requirepass "$$REDIS_PASSWORD"
      '
```

#### Client Configuration

**Connection String with Password**:
```yaml
# config.yaml
redis:
  url: redis://:${REDIS_PASSWORD}@localhost:6379
```

**Note**: `:` before password is required syntax for Redis URLs.

**Alternative (Separate Password Config)**:
```yaml
# config.yaml
redis:
  url: redis://localhost:6379
  password: ${REDIS_PASSWORD}
```

#### Testing Authentication

```bash
# Without password (should fail)
redis-cli -p 6379 ping
# (error) NOAUTH Authentication required

# With password (should succeed)
redis-cli -p 6379 -a "your-password" ping
# Warning: Using a password with '-a' or '-u' option on the command line interface may not be safe.
# PONG

# Suppress warning
redis-cli -p 6379 --no-auth-warning -a "your-password" ping
# PONG
```

### Password Rotation

**Process**:
1. Generate new password
2. Update secrets file
3. Restart Redis with new password
4. Update application configuration
5. Restart application

**Note**: This application uses a centralized secrets management script that generates and rotates secrets for all services (PostgreSQL, Redis, Temporal, OIDC providers, etc.). See [Secrets Management Documentation](../../docs/secrets_management.md) for details.

**Quick Rotation**:
```bash
# Regenerate all secrets (backs up old ones)
./infra/secrets/generate_secrets.sh

# Or regenerate only Redis password manually
openssl rand -base64 32 > infra/secrets/keys/redis_password.txt
chmod 600 infra/secrets/keys/redis_password.txt

# Restart services to apply new password
docker-compose -f docker-compose.prod.yml restart redis
docker-compose -f docker-compose.prod.yml restart app
```

**Frequency**: Rotate passwords every 90 days or after security incident

## Network Security

### Network Binding

#### Localhost-Only (Recommended)

```yaml
# docker-compose.prod.yml
ports:
  - "127.0.0.1:6379:6379"
```

**Behavior**:
- Only connections from `127.0.0.1` (localhost) allowed
- Cannot connect from external IP addresses
- Secure by default

**Test**:
```bash
# From localhost (should work)
redis-cli -p 6379 ping

# From external IP (should fail)
redis-cli -h 192.168.1.100 -p 6379 ping
# Could not connect to Redis at 192.168.1.100:6379: Connection refused
```

#### Docker Internal Network (Most Secure)

```yaml
# docker-compose.prod.yml
services:
  redis:
    # No ports exposed to host at all
    networks:
      - app-network

  app:
    environment:
      - REDIS_URL=redis://redis:6379  # Use container name
    networks:
      - app-network

networks:
  app-network:
    driver: bridge
```

**Benefits**:
- Redis not accessible from host at all
- Only accessible to containers on same network
- Best security posture

**Trade-off**:
- Cannot access Redis CLI from host
- Requires `docker exec` for debugging

#### External Exposure (Not Recommended)

```yaml
# ⚠️ DANGEROUS - Exposes to network
ports:
  - "0.0.0.0:6379:6379"
```

**Only use if**:
- Behind firewall with restricted IP whitelist
- VPN-only access
- Strong authentication (password + TLS + ACLs)
- Monitoring and intrusion detection in place

### Firewall Rules

**iptables** (Linux):
```bash
# Allow only from specific IP
sudo iptables -A INPUT -p tcp --dport 6379 -s 192.168.1.100 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 6379 -j DROP

# Allow only from VPN subnet
sudo iptables -A INPUT -p tcp --dport 6379 -s 10.8.0.0/24 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 6379 -j DROP
```

**UFW** (Simplified firewall):
```bash
# Deny by default
sudo ufw default deny incoming

# Allow from specific IP
sudo ufw allow from 192.168.1.100 to any port 6379

# Enable firewall
sudo ufw enable
```

### VPN/Bastion Access

For remote access, use VPN or bastion host:

```
Developer → VPN → Bastion Host → Redis (localhost only)
```

**SSH Tunnel** (for debugging):
```bash
# From local machine
ssh -L 6379:localhost:6379 user@production-server

# Now access Redis on local port 6379
redis-cli -p 6379 -a "password" ping
```

## Data Encryption

### Encryption in Transit (TLS/SSL)

#### Generate Certificates

```bash
# Create certificate directory
mkdir -p infra/certs/redis

# Generate CA (Certificate Authority)
openssl genrsa -out infra/certs/redis/ca.key 4096
openssl req -new -x509 -key infra/certs/redis/ca.key -out infra/certs/redis/ca.crt -days 3650 \
  -subj "/C=US/ST=State/L=City/O=Organization/OU=IT/CN=Redis CA"

# Generate Redis server certificate
openssl genrsa -out infra/certs/redis/redis.key 4096
openssl req -new -key infra/certs/redis/redis.key -out infra/certs/redis/redis.csr \
  -subj "/C=US/ST=State/L=City/O=Organization/OU=IT/CN=redis"

# Sign server certificate with CA
openssl x509 -req -in infra/certs/redis/redis.csr \
  -CA infra/certs/redis/ca.crt \
  -CAkey infra/certs/redis/ca.key \
  -CAcreateserial \
  -out infra/certs/redis/redis.crt \
  -days 3650

# Generate client certificate (optional, for mTLS)
openssl genrsa -out infra/certs/redis/client.key 4096
openssl req -new -key infra/certs/redis/client.key -out infra/certs/redis/client.csr \
  -subj "/C=US/ST=State/L=City/O=Organization/OU=IT/CN=redis-client"
openssl x509 -req -in infra/certs/redis/client.csr \
  -CA infra/certs/redis/ca.crt \
  -CAkey infra/certs/redis/ca.key \
  -CAcreateserial \
  -out infra/certs/redis/client.crt \
  -days 3650

# Set permissions
chmod 600 infra/certs/redis/*.key
chmod 644 infra/certs/redis/*.crt
```

#### Redis Configuration

```conf
# infra/docker/prod/redis/redis.conf

# Enable TLS
tls-port 6379
port 0  # Disable unencrypted port

# Server certificates
tls-cert-file /certs/redis.crt
tls-key-file /certs/redis.key
tls-ca-cert-file /certs/ca.crt

# Mutual TLS (optional - require client certificates)
tls-auth-clients yes

# TLS protocol versions
tls-protocols "TLSv1.2 TLSv1.3"

# Cipher suites (strong ciphers only)
tls-ciphers "HIGH:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!MD5:!PSK:!SRP:!CAMELLIA"

# Prefer server ciphers
tls-prefer-server-ciphers yes
```

#### Docker Configuration

```yaml
# docker-compose.prod.yml
redis:
  volumes:
    - ./infra/certs/redis:/certs:ro
  command: redis-server /usr/local/etc/redis/redis.conf
```

#### Client Configuration

```yaml
# config.yaml
redis:
  url: rediss://localhost:6379  # Note: rediss:// (double 's' for TLS)
  password: ${REDIS_PASSWORD}
  tls_cert_file: infra/certs/redis/client.crt  # For mTLS
  tls_key_file: infra/certs/redis/client.key
  tls_ca_cert_file: infra/certs/redis/ca.crt
```

**Python Client** (with TLS):
```python
import redis.asyncio as redis
import ssl

# Create SSL context
ssl_context = ssl.create_default_context(
    cafile="infra/certs/redis/ca.crt"
)

# For mTLS (client certificate authentication)
ssl_context.load_cert_chain(
    certfile="infra/certs/redis/client.crt",
    keyfile="infra/certs/redis/client.key"
)

# Connect with TLS
redis_client = await redis.from_url(
    "rediss://localhost:6379",
    password="your-password",
    ssl=ssl_context,
    ssl_cert_reqs="required"  # Verify server certificate
)
```

#### Testing TLS

```bash
# Connect with TLS
redis-cli --tls \
  --cert infra/certs/redis/client.crt \
  --key infra/certs/redis/client.key \
  --cacert infra/certs/redis/ca.crt \
  -p 6379 \
  -a "your-password" \
  ping
# PONG
```

### Encryption at Rest

Redis itself does **not** encrypt data on disk. Use OS-level encryption:

#### Linux (LUKS)

```bash
# Create encrypted volume
sudo cryptsetup luksFormat /dev/sdb1
sudo cryptsetup luksOpen /dev/sdb1 encrypted_redis

# Create filesystem
sudo mkfs.ext4 /dev/mapper/encrypted_redis

# Mount
sudo mkdir -p /mnt/encrypted_redis
sudo mount /dev/mapper/encrypted_redis /mnt/encrypted_redis

# Configure Redis to use encrypted volume
# Update docker volume mount to /mnt/encrypted_redis
```

#### Cloud Provider Encryption

**AWS EBS**:
```terraform
resource "aws_ebs_volume" "redis_data" {
  availability_zone = "us-east-1a"
  size              = 10
  encrypted         = true
  kms_key_id        = aws_kms_key.redis.arn
}
```

**GCP Persistent Disk**:
```terraform
resource "google_compute_disk" "redis_data" {
  name  = "redis-data"
  type  = "pd-ssd"
  zone  = "us-central1-a"
  size  = 10
  
  disk_encryption_key {
    kms_key_name = google_kms_crypto_key.redis.id
  }
}
```

**Azure Managed Disk**:
```terraform
resource "azurerm_managed_disk" "redis_data" {
  name                 = "redis-data"
  location             = "East US"
  resource_group_name  = azurerm_resource_group.main.name
  storage_account_type = "Premium_LRS"
  create_option        = "Empty"
  disk_size_gb         = 10
  
  encryption_settings {
    enabled = true
  }
}
```

### Application-Level Encryption

For highly sensitive data (PII, tokens), encrypt at application level:

```python
from cryptography.fernet import Fernet
import json

class EncryptedSessionStorage:
    def __init__(self, storage: SessionStorage, encryption_key: bytes):
        self.storage = storage
        self.cipher = Fernet(encryption_key)
    
    async def set(self, key: str, value: dict, ttl_seconds: int):
        """Encrypt data before storing."""
        json_data = json.dumps(value)
        encrypted_data = self.cipher.encrypt(json_data.encode())
        await self.storage.set(key, encrypted_data.decode(), ttl_seconds)
    
    async def get(self, key: str) -> dict | None:
        """Decrypt data after retrieving."""
        encrypted_data = await self.storage.get(key, model_class=str)
        if encrypted_data is None:
            return None
        
        decrypted_data = self.cipher.decrypt(encrypted_data.encode())
        return json.loads(decrypted_data.decode())

# Usage
encryption_key = Fernet.generate_key()  # Store securely!
encrypted_storage = EncryptedSessionStorage(session_storage, encryption_key)

await encrypted_storage.set("user:123", {"token": "secret"}, 3600)
```

**Trade-offs**:
- ✅ Maximum security (Redis admin can't read data)
- ✅ Protects against disk theft
- ✗ Performance overhead (~10-20% slower)
- ✗ Can't search/filter encrypted data

## Access Control Lists (ACLs)

Redis 6+ supports fine-grained user permissions.

### Configure ACLs

```conf
# infra/docker/prod/redis/redis.conf

# Default user (admin access)
user default on >admin-password ~* &* +@all

# Read-only user
user readonly on >readonly-password ~* &* +@read -@write -@dangerous

# Session storage user (limited permissions)
user sessionapp on >sessionapp-password ~user:* ~auth:* +get +set +del +expire +ttl +exists

# Monitoring user (read-only, safe commands)
user monitor on >monitor-password ~* &* +@read +ping +info +config|get +slowlog
```

### ACL Syntax

**User**: `user <username>`  
**Status**: `on` (enabled) or `off` (disabled)  
**Password**: `>password` (plaintext) or `#hash` (SHA256)  
**Key Patterns**: `~pattern` (allow access) or `%W~pattern` (write-only) or `%R~pattern` (read-only)  
**Channels**: `&channel` (pub/sub channels)  
**Commands**: `+command` (allow) or `-command` (deny)  
**Command Categories**: `+@category` (e.g., `+@read`, `+@write`, `+@dangerous`)

### ACL Categories

| Category | Description | Commands |
|----------|-------------|----------|
| `@read` | Read-only commands | GET, MGET, HGETALL, SCAN, etc. |
| `@write` | Write commands | SET, DEL, HSET, LPUSH, etc. |
| `@dangerous` | Dangerous commands | FLUSHDB, KEYS, CONFIG, EVAL, etc. |
| `@admin` | Administrative | CONFIG, SHUTDOWN, SAVE, etc. |
| `@slow` | Potentially slow | KEYS, SORT, SUNION, etc. |
| `@all` | All commands | Everything |

### Application Configuration

```yaml
# config.yaml
redis:
  url: redis://sessionapp:sessionapp-password@localhost:6379
```

### Testing ACLs

```bash
# Connect as sessionapp user
redis-cli -p 6379 --user sessionapp -a sessionapp-password

# Allowed: Access user sessions
> SET user:123 "data"
OK
> GET user:123
"data"

# Denied: Access other keys
> SET admin:config "value"
(error) NOPERM this user has no permissions to run the 'set' command on key 'admin:config'

# Denied: Dangerous commands
> FLUSHDB
(error) NOPERM this user has no permissions to run the 'flushdb' command
```

### ACL Management

```bash
# List all users
> ACL LIST
1) "user default on #... ~* &* +@all"
2) "user readonly on #... ~* &* +@read -@write"
3) "user sessionapp on #... ~user:* +get +set +del"

# View user permissions
> ACL GETUSER sessionapp
 1) "flags"
 2) 1) "on"
 3) "passwords"
 4) 1) "..."
 5) "commands"
 6) "+get +set +del"
 7) "keys"
 8) "~user:*"

# Create user at runtime
> ACL SETUSER newuser on >password ~* +@read
OK

# Save ACLs to file
> ACL SAVE
OK
```

## Dangerous Commands

### Disabled in Production

```conf
# infra/docker/prod/redis/redis.conf

# Wipe database
rename-command FLUSHDB ""
rename-command FLUSHALL ""

# Dangerous O(N) operations
rename-command KEYS ""

# Configuration changes
rename-command CONFIG ""

# Debugging
rename-command DEBUG ""

# Shutdown
rename-command SHUTDOWN ""

# Arbitrary code execution
rename-command EVAL ""
rename-command EVALSHA ""
rename-command SCRIPT ""

# Replication (if single-node)
rename-command SLAVEOF ""
rename-command REPLICAOF ""
```

### Why Disable These Commands

**FLUSHDB/FLUSHALL**:
- Wipes entire database instantly
- No confirmation prompt
- Cannot undo (unless backup)
- **Risk**: Accidental data loss

**KEYS**:
- Blocks server while scanning all keys
- O(N) time complexity (N = total keys)
- Can timeout all clients
- **Risk**: Denial of service
- **Alternative**: Use SCAN (non-blocking)

**CONFIG**:
- Allows runtime reconfiguration
- Can disable authentication
- Can change persistence settings
- **Risk**: Security bypass

**EVAL/EVALSHA**:
- Executes Lua scripts
- Can access filesystem
- Can call arbitrary Redis commands
- **Risk**: Code injection

**SHUTDOWN**:
- Stops Redis server
- **Risk**: Availability loss

### Testing Disabled Commands

```bash
# Try disabled command
redis-cli -p 6379 -a "password" FLUSHDB
# (error) ERR unknown command 'FLUSHDB'

# Alternative: SCAN instead of KEYS
redis-cli -p 6379 -a "password" SCAN 0 MATCH "user:*" COUNT 100
```

## Secrets Management

### Development

```bash
# Store in .env (gitignored)
echo "REDIS_PASSWORD=dev-password-123" >> .env
```

### Production

#### Option 1: Docker Secrets

```bash
# Create secrets directory
mkdir -p infra/secrets/keys

# Generate password
openssl rand -base64 32 > infra/secrets/keys/redis_password.txt
chmod 600 infra/secrets/keys/redis_password.txt

# Reference in docker-compose.prod.yml
secrets:
  redis_password:
    file: ./infra/secrets/keys/redis_password.txt
```

#### Option 2: AWS Secrets Manager

```python
import boto3
from botocore.exceptions import ClientError

def get_redis_password():
    client = boto3.client('secretsmanager', region_name='us-east-1')
    
    try:
        response = client.get_secret_value(SecretId='prod/redis/password')
        return response['SecretString']
    except ClientError as e:
        raise Exception(f"Failed to retrieve secret: {e}")

# Use in application
redis_password = get_redis_password()
redis_url = f"redis://:{redis_password}@localhost:6379"
```

#### Option 3: HashiCorp Vault

```bash
# Store secret
vault kv put secret/redis password="your-password"

# Retrieve secret
vault kv get -field=password secret/redis
```

**Application Integration**:
```python
import hvac

client = hvac.Client(url='http://vault:8200', token='your-vault-token')
secret = client.secrets.kv.v2.read_secret_version(path='redis')
redis_password = secret['data']['data']['password']
```

### Secret Rotation

See [Password Rotation](#password-rotation) section above.

## Attack Vectors and Mitigations

### 1. Unauthorized Access

**Attack**: Attacker connects to Redis without authentication  
**Mitigation**:
- ✅ Enable password authentication
- ✅ Bind to localhost only
- ✅ Use firewall rules
- ✅ Monitor failed authentication attempts

### 2. Command Injection

**Attack**: Application passes unsanitized user input to Redis commands  
**Example**:
```python
# VULNERABLE CODE
user_input = request.query_params['key']  # User provides: "key' || DEL user:*"
await redis_client.get(user_input)  # Executes DEL user:*
```

**Mitigation**:
- ✅ Never interpolate user input into commands
- ✅ Use parameterized queries (Redis client handles escaping)
- ✅ Validate and sanitize all input
- ✅ Use ACLs to limit command access

**Safe Code**:
```python
# Safe - client handles escaping
user_input = request.query_params['key']
await redis_client.get(user_input)  # Only gets exactly that key
```

### 3. Denial of Service (DoS)

**Attack**: Attacker runs expensive operations (KEYS, large SCAN)  
**Mitigation**:
- ✅ Disable KEYS command
- ✅ Use SCAN with small COUNT
- ✅ Set connection limits (maxclients)
- ✅ Implement rate limiting
- ✅ Monitor CPU and memory usage

### 4. Data Exfiltration

**Attack**: Attacker dumps entire database  
**Mitigation**:
- ✅ Disable KEYS command
- ✅ Use ACLs (limit key access patterns)
- ✅ Encrypt data at application level
- ✅ Monitor for suspicious SCAN patterns
- ✅ Audit all access

### 5. Session Hijacking

**Attack**: Attacker steals session ID and impersonates user  
**Mitigation**:
- ✅ Use HttpOnly cookies (not accessible to JavaScript)
- ✅ Use Secure flag (HTTPS only)
- ✅ Use SameSite=Strict (CSRF protection)
- ✅ Validate client fingerprint
- ✅ Rotate sessions after sensitive operations
- ✅ Short session TTLs (1 hour)

See [Session Security](../security.md#session-management) for more details.

### 6. Man-in-the-Middle (MITM)

**Attack**: Attacker intercepts Redis traffic  
**Mitigation**:
- ✅ Use TLS/SSL for all connections
- ✅ Verify server certificates
- ✅ Use mTLS (client certificates)
- ✅ Use VPN for remote access

## Security Checklist

### Production Deployment Checklist

- [ ] **Authentication**
  - [ ] Strong password set (32+ characters, random)
  - [ ] Password stored in secrets management
  - [ ] Password rotation schedule defined (90 days)

- [ ] **Network Security**
  - [ ] Redis bound to localhost (`127.0.0.1:6379`)
  - [ ] Firewall rules configured (if exposed)
  - [ ] TLS/SSL enabled (optional but recommended)
  - [ ] VPN/bastion access for remote administration

- [ ] **Access Control**
  - [ ] Dangerous commands disabled
  - [ ] ACLs configured (optional)
  - [ ] Minimum required permissions granted

- [ ] **Data Protection**
  - [ ] Encryption at rest enabled (OS-level or cloud)
  - [ ] Sensitive data encrypted at application level
  - [ ] Backups encrypted
  - [ ] Backup retention policy defined

- [ ] **Monitoring**
  - [ ] Health checks configured
  - [ ] Metrics collection enabled
  - [ ] Alerts configured (memory, latency, errors)
  - [ ] Audit logging enabled

- [ ] **Compliance**
  - [ ] Data residency requirements met
  - [ ] PII handling compliant with regulations
  - [ ] Security assessment completed
  - [ ] Incident response plan documented

### Security Testing

```bash
# Test authentication
redis-cli -p 6379 ping
# Expected: (error) NOAUTH Authentication required

# Test network binding
redis-cli -h <external-ip> -p 6379 ping
# Expected: Connection refused

# Test disabled commands
redis-cli -p 6379 -a "password" FLUSHDB
# Expected: (error) ERR unknown command 'FLUSHDB'

# Test ACLs
redis-cli -p 6379 --user readonly -a "password" SET key value
# Expected: (error) NOPERM
```

## Incident Response

### Suspected Breach

**Immediate Actions**:
1. **Isolate**: Disconnect Redis from network
2. **Assess**: Check logs for unauthorized access
3. **Contain**: Change all passwords immediately
4. **Investigate**: Audit all data access

**Commands**:
```bash
# Check recent connections
redis-cli -p 6379 -a "password" CLIENT LIST

# Check slow log for suspicious commands
redis-cli -p 6379 -a "password" SLOWLOG GET 100

# Check command statistics
redis-cli -p 6379 -a "password" INFO commandstats
```

### Data Loss

**Recovery**:
1. **Stop writes**: Take application offline
2. **Restore backup**: Load latest RDB snapshot
3. **Replay AOF**: Apply incremental changes
4. **Verify integrity**: Test restored data
5. **Resume operations**: Bring application online

**Commands**:
```bash
# Stop Redis
docker stop api-forge-redis

# Restore from backup
docker cp backup-20240315.rdb api-forge-redis:/data/dump.rdb

# Start Redis
docker start api-forge-redis

# Verify data
redis-cli -p 6379 -a "password" DBSIZE
```

### Performance Degradation

**Diagnosis**:
```bash
# Check latency
redis-cli -p 6379 -a "password" --latency

# Check slow log
redis-cli -p 6379 -a "password" SLOWLOG GET 10

# Check memory usage
redis-cli -p 6379 -a "password" INFO memory

# Check connected clients
redis-cli -p 6379 -a "password" CLIENT LIST
```

**Mitigation**:
- Increase memory limit
- Scale to Redis Cluster
- Optimize queries (avoid KEYS, large SCAN)
- Increase connection pool size

## Next Steps

- [Main Overview](./main.md) - Understand Redis architecture
- [Configuration](./configuration.md) - Configure security settings
- [Usage Guide](./usage.md) - Implement secure patterns
- [CLI Access](./redis-cli-access.md) - Securely access Redis CLI
