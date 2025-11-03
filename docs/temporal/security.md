# Temporal Security

This document covers security considerations for Temporal deployments, focusing on communication security between Temporal clients, workers, and the Temporal server.

## Overview

Temporal supports multiple layers of security to protect workflow data and prevent unauthorized access:

1. **Transport Security (TLS/mTLS)** - Encrypts communication between components
2. **Authentication** - Verifies identity of clients and workers
3. **Authorization** - Controls access to namespaces and operations
4. **Data Encryption** - Protects sensitive workflow data at rest and in transit

## Current Implementation Status

### ✅ Implemented
- Basic connectivity to Temporal server
- Insecure development mode (no TLS)
- Configuration structure for TLS settings

### ⚠️ Not Yet Implemented
- **mTLS (Mutual TLS)** - Preferred security method
- Certificate generation and management
- JWT authentication
- Role-based access control (RBAC)
- Data encryption for sensitive payloads

## Security in Development vs. Production

### Development Environment

The current development setup (`docker-compose.dev.yml`) runs **without security** for ease of development:

```yaml
temporal:
  image: temporalio/auto-setup:1.28.1
  ports:
    - 7234:7233  # Exposed on localhost
  # No TLS configuration
```

**Security Characteristics**:
- ✓ Only accessible from localhost
- ✓ Docker network isolation (containers only)
- ✗ No encryption
- ✗ No authentication
- ✗ No authorization

**Acceptable for**:
- Local development
- Running on trusted single-developer machines
- Prototyping and testing

**Not acceptable for**:
- Production deployments
- Multi-tenant environments
- Networks with untrusted users
- Internet-facing services

---

### Production Requirements

Production deployments **must** implement security measures. The recommended approach is **mTLS (mutual TLS)**.

## Mutual TLS (mTLS) - Recommended Approach

### What is mTLS?

Mutual TLS provides:
1. **Encryption**: All communication is encrypted via TLS
2. **Server Authentication**: Clients verify the server's identity using its certificate
3. **Client Authentication**: Server verifies the client's identity using its certificate
4. **Authorization**: Certificates can encode roles and permissions

### Why mTLS for Temporal?

- **Industry Standard**: Widely used for service-to-service communication
- **Strong Security**: Both parties authenticate each other
- **No Credential Leakage**: No passwords or API keys in environment variables
- **Certificate Rotation**: Supports regular rotation of credentials
- **Namespace Isolation**: Different certificates for different namespaces/environments

### mTLS Architecture

```
┌─────────────────┐                              ┌──────────────────┐
│  FastAPI App    │                              │ Temporal Server  │
│  (Client)       │◄────TLS Handshake───────────▶│                  │
│                 │  1. Server sends cert        │  Server Cert:    │
│  Client Cert:   │  2. Client verifies          │  - temporal.crt  │
│  - client.crt   │  3. Client sends cert        │  - temporal.key  │
│  - client.key   │  4. Server verifies          │                  │
│  - ca.crt       │                              │  Trusted CA:     │
└─────────────────┘                              │  - ca.crt        │
                                                  └──────────────────┘
        │                                                 │
        └─────────TLS Encrypted Communication────────────┘
```

### Certificate Requirements

You need the following certificates:

#### 1. **Certificate Authority (CA)** 
- **Purpose**: Root of trust for signing all other certificates
- **Files**: `ca.crt` (public), `ca.key` (private, highly sensitive)
- **Lifetime**: 5-10 years
- **Rotation**: Rare, requires rotating all other certificates

#### 2. **Temporal Server Certificate**
- **Purpose**: Identifies the Temporal server
- **Files**: `temporal-server.crt`, `temporal-server.key`
- **Common Name (CN)**: `temporal-server` or server's hostname
- **Subject Alternative Names (SANs)**: All server hostnames/IPs
- **Lifetime**: 1-2 years
- **Rotation**: Annual or biannual

#### 3. **Client Certificates** (one per client/worker)
- **Purpose**: Identifies clients and workers
- **Files**: `temporal-client.crt`, `temporal-client.key`
- **Common Name (CN)**: Client identifier (e.g., `api-worker-1`)
- **Organization (O)**: Can encode namespace or team
- **Lifetime**: 90 days to 1 year
- **Rotation**: Quarterly or when compromised

### Implementation Roadmap

#### Phase 1: Certificate Generation (Not Yet Implemented)

Generate certificates using OpenSSL or cfssl:

```bash
# 1. Generate CA
openssl req -x509 -newkey rsa:4096 -keyout ca.key -out ca.crt -days 3650 -nodes \
  -subj "/CN=Temporal CA/O=MyOrg"

# 2. Generate Server Certificate
openssl req -newkey rsa:4096 -keyout temporal-server.key -out temporal-server.csr -nodes \
  -subj "/CN=temporal-server/O=MyOrg"

# Sign server cert with CA
openssl x509 -req -in temporal-server.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out temporal-server.crt -days 730 \
  -extfile <(echo "subjectAltName=DNS:temporal,DNS:temporal-server,DNS:localhost")

# 3. Generate Client Certificate
openssl req -newkey rsa:4096 -keyout temporal-client.key -out temporal-client.csr -nodes \
  -subj "/CN=api-client/O=MyOrg"

# Sign client cert with CA
openssl x509 -req -in temporal-client.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out temporal-client.crt -days 365
```

**Storage**: Certificates should be stored in:
- **Development**: `data/temporal-certs/` (gitignored)
- **Production**: Kubernetes secrets, AWS Secrets Manager, HashiCorp Vault

#### Phase 2: Temporal Server Configuration (Not Yet Implemented)

Update `docker-compose.prod.yml` to enable mTLS:

```yaml
temporal:
  image: temporalio/auto-setup:1.28.1
  environment:
    - TEMPORAL_TLS_REQUIRE_CLIENT_AUTH=true
    - TEMPORAL_TLS_SERVER_CERT=/etc/temporal/certs/temporal-server.crt
    - TEMPORAL_TLS_SERVER_KEY=/etc/temporal/certs/temporal-server.key
    - TEMPORAL_TLS_CLIENT_CA=/etc/temporal/certs/ca.crt
  volumes:
    - ./data/temporal-certs:/etc/temporal/certs:ro
```

For self-hosted Temporal (not auto-setup), configure in `temporal.yaml`:

```yaml
services:
  frontend:
    rpc:
      grpcPort: 7233
      bindOnIP: "0.0.0.0"
      
  tls:
    internode:
      server:
        requireClientAuth: true
        certFile: /etc/temporal/certs/temporal-server.crt
        keyFile: /etc/temporal/certs/temporal-server.key
        clientCaFiles:
          - /etc/temporal/certs/ca.crt
    
    frontend:
      server:
        requireClientAuth: true
        certFile: /etc/temporal/certs/temporal-server.crt
        keyFile: /etc/temporal/certs/temporal-server.key
        clientCaFiles:
          - /etc/temporal/certs/ca.crt
```

#### Phase 3: Client/Worker Configuration (Partially Implemented)

Update `src/app/core/services/temporal/temporal_client.py`:

```python
from temporalio.client import Client, TLSConfig

async def _connect(self) -> Client:
    """Establish connection to Temporal server with mTLS."""
    
    if self._config.tls:
        # Read certificates from file
        with open("/etc/temporal/certs/temporal-client.crt", "rb") as f:
            client_cert = f.read()
        with open("/etc/temporal/certs/temporal-client.key", "rb") as f:
            client_key = f.read()
        with open("/etc/temporal/certs/ca.crt", "rb") as f:
            ca_cert = f.read()
        
        # Configure TLS
        tls_config = TLSConfig(
            client_cert=client_cert,
            client_private_key=client_key,
            server_root_ca_cert=ca_cert,
            domain="temporal-server"  # Must match server cert CN
        )
        
        client = await Client.connect(
            self._config.url,
            namespace=self._config.namespace,
            tls=tls_config,
            data_converter=pydantic_data_converter,
        )
    else:
        # Insecure mode (development only)
        client = await Client.connect(
            self._config.url,
            namespace=self._config.namespace,
            data_converter=pydantic_data_converter,
        )
    
    return client
```

**Configuration** (`config.yaml`):

```yaml
temporal:
  enabled: true
  url: "temporal-prod.internal:7233"
  tls: true  # Enable TLS
  namespace: "production"
  cert_path: "/etc/temporal/certs"  # Base path for certificates
```

**Environment Variables**:
```bash
export TEMPORAL_TLS_ENABLED="true"
export TEMPORAL_CERT_PATH="/etc/temporal/certs"
```

#### Phase 4: Certificate Management (Not Yet Implemented)

Implement certificate rotation and renewal:

1. **Monitoring**: Alert when certificates are close to expiration
2. **Rotation**: Automated process to renew certificates
3. **Distribution**: Safely distribute new certificates to all components
4. **Rollback**: Ability to revert to old certificates if needed

**Tools to consider**:
- [cert-manager](https://cert-manager.io/) (Kubernetes)
- [HashiCorp Vault PKI](https://www.vaultproject.io/docs/secrets/pki)
- [AWS Certificate Manager](https://aws.amazon.com/certificate-manager/)

---

## Alternative Security Approaches

### JWT Authentication (Not Implemented)

Temporal Cloud and some self-hosted deployments support JWT-based authentication:

```python
client = await Client.connect(
    "temporal-cloud.example.com:7233",
    namespace="my-namespace",
    rpc_metadata={
        "authorization": f"Bearer {jwt_token}"
    },
    tls=True  # TLS still required for encryption
)
```

**When to use**:
- Temporal Cloud deployments
- Integration with existing OAuth/OIDC providers
- Dynamic credential issuance

**Not recommended for**:
- Self-hosted Temporal (mTLS is simpler)
- Service-to-service communication (mTLS is more secure)

### API Key Authentication (Not Recommended)

Some deployments use API keys in headers:

```python
client = await Client.connect(
    "temporal.example.com:7233",
    rpc_metadata={
        "api-key": "secret-api-key-here"
    },
    tls=True
)
```

**⚠️ Drawbacks**:
- API keys can leak in logs/code
- Harder to rotate than certificates
- No cryptographic proof of identity
- Less secure than mTLS

---

## Data Encryption

### Encryption in Transit

- **With mTLS**: All communication is encrypted via TLS 1.2+ with strong cipher suites
- **Without TLS**: Data is transmitted in plaintext (development only!)

### Encryption at Rest

Temporal stores workflow state in a database (PostgreSQL in this project). Protect sensitive data:

#### 1. **Database Encryption**

Enable encryption at rest for PostgreSQL:

```yaml
postgres:
  environment:
    - POSTGRES_INITDB_ARGS=--data-checksums --encoding=UTF8
  volumes:
    - type: volume
      source: postgres_data
      target: /var/lib/postgresql/data
      volume:
        driver_opts:
          type: none
          o: bind
          device: /encrypted/volume/path
```

Use encrypted volumes (LUKS, dm-crypt, or cloud provider encryption).

#### 2. **Application-Level Encryption**

Encrypt sensitive workflow inputs before passing to Temporal:

```python
from cryptography.fernet import Fernet

class EncryptedWorkflowInput(BaseModel):
    encrypted_data: str
    
    @classmethod
    def from_sensitive_data(cls, data: SensitiveData, key: bytes):
        f = Fernet(key)
        encrypted = f.encrypt(data.model_dump_json().encode())
        return cls(encrypted_data=encrypted.decode())
    
    def decrypt(self, key: bytes) -> SensitiveData:
        f = Fernet(key)
        decrypted = f.decrypt(self.encrypted_data.encode())
        return SensitiveData.model_validate_json(decrypted)

# In your workflow
@workflow.run
async def run(self, input: EncryptedWorkflowInput) -> Output:
    # Decrypt inside workflow
    sensitive_data = input.decrypt(encryption_key)
    # Process...
```

**Key Management**:
- Store encryption keys in secrets management (Vault, AWS Secrets Manager)
- Rotate keys regularly
- Never commit keys to version control

#### 3. **Temporal's Data Converter**

Temporal supports custom data converters for automatic encryption:

```python
from temporalio.converter import DataConverter, EncryptionCodec

# Custom encryption codec
class MyEncryptionCodec(EncryptionCodec):
    async def encode(self, payloads):
        # Encrypt payloads
        pass
    
    async def decode(self, payloads):
        # Decrypt payloads
        pass

# Use in client
client = await Client.connect(
    "temporal:7233",
    data_converter=DataConverter(
        payload_codec=MyEncryptionCodec()
    )
)
```

---

## Network Security

### Firewall Rules

Restrict access to Temporal server:

```bash
# Allow only from application servers
iptables -A INPUT -p tcp --dport 7233 -s 10.0.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 7233 -j DROP

# Allow Temporal UI only from VPN
iptables -A INPUT -p tcp --dport 8082 -s 10.0.2.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 8082 -j DROP
```

### Network Segmentation

Isolate Temporal components:

```
┌────────────────┐
│  Public DMZ    │
│  (Web Tier)    │
└───────┬────────┘
        │
┌───────▼────────┐
│  Private Net   │
│  (App Tier)    │ ◄── FastAPI App (Temporal Client)
└───────┬────────┘
        │
┌───────▼────────┐
│  Backend Net   │
│  (Data Tier)   │ ◄── Temporal Server + PostgreSQL
└────────────────┘
```

**Network Policies** (Kubernetes):
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: temporal-server
spec:
  podSelector:
    matchLabels:
      app: temporal-server
  ingress:
  - from:
    - podSelector:
        matchLabels:
          role: temporal-client  # Only clients
    ports:
    - port: 7233
      protocol: TCP
```

---

## Security Best Practices

### 1. **Principle of Least Privilege**
- Grant minimal permissions to each client/worker
- Use namespace-level isolation
- Implement RBAC when available

### 2. **Defense in Depth**
- Use mTLS for communication security
- Encrypt sensitive data at application level
- Secure database with encryption at rest
- Implement network segmentation

### 3. **Certificate Hygiene**
- Rotate certificates regularly (90 days for clients)
- Monitor certificate expiration
- Secure private keys (never commit to git)
- Use hardware security modules (HSMs) for CA keys in production

### 4. **Audit Logging**
- Enable Temporal audit logs
- Monitor for suspicious activity
- Correlate logs with SIEM systems

### 5. **Security Updates**
- Keep Temporal server updated
- Monitor security advisories
- Test updates in staging first

---

## Monitoring and Alerting

### Certificate Expiration Monitoring

```python
from cryptography import x509
from datetime import datetime, timedelta

def check_cert_expiration(cert_path: str) -> int:
    """Return days until certificate expires."""
    with open(cert_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    
    expiry = cert.not_valid_after
    days_left = (expiry - datetime.utcnow()).days
    
    return days_left

# In health check endpoint
days_left = check_cert_expiration("/etc/temporal/certs/temporal-client.crt")
if days_left < 30:
    logger.warning(f"Client certificate expires in {days_left} days!")
```

### Connection Security Monitoring

```python
async def verify_tls_connection():
    """Verify TLS is enabled and working."""
    client = await temporal_service.get_client()
    
    # Check if connection is encrypted
    if not client._client._connection._tls:
        raise SecurityError("Temporal connection is not encrypted!")
```

---

## Security Checklist

### Development ✓
- [x] Temporal server running locally
- [x] Access restricted to localhost
- [x] Docker network isolation
- [ ] TLS enabled (not required for local dev)

### Staging/Production ⚠️
- [ ] mTLS implemented and tested
- [ ] Certificates generated with proper lifetimes
- [ ] Certificate rotation process defined
- [ ] Firewall rules restricting Temporal access
- [ ] Network segmentation implemented
- [ ] Database encryption at rest enabled
- [ ] Audit logging enabled
- [ ] Monitoring and alerting configured
- [ ] Security testing completed
- [ ] Incident response plan documented

---

## Future Enhancements

1. **Automated Certificate Management**
   - Integration with cert-manager or Vault PKI
   - Automatic renewal and distribution
   - Certificate expiration alerts

2. **Role-Based Access Control (RBAC)**
   - Namespace-level permissions
   - Per-workflow authorization
   - Integration with corporate LDAP/AD

3. **End-to-End Encryption**
   - Custom data converter for automatic encryption
   - Key rotation mechanism
   - Searchable encryption for Temporal visibility

4. **Security Auditing**
   - Comprehensive audit logs
   - SIEM integration
   - Compliance reporting (SOC2, HIPAA, PCI-DSS)

---

## Related Documentation

- [Main Overview](./main.md) - Temporal concepts and architecture
- [Configuration](./configuration.md) - Configure Temporal settings
- [Usage Guide](./usage.md) - Execute workflows from FastAPI
- [Temporal Web UI](./temporal-web-ui.md) - Access the management interface

## External Resources

- [Temporal Security Documentation](https://docs.temporal.io/security)
- [Temporal Cloud Security Whitepaper](https://temporal.io/pages/cloud-security-white-paper)
- [OpenSSL Certificate Creation](https://www.openssl.org/docs/man1.1.1/man1/openssl-req.html)
- [OWASP Transport Layer Protection Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Protection_Cheat_Sheet.html)
