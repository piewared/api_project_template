# Temporal Authentication Guide

## 🔐 **Temporal Security Overview**

Your production Temporal setup now includes **enterprise-grade authentication** with:

1. **mTLS (Mutual TLS)** - Certificate-based authentication between services
2. **JWT Authorization** - Role-based access control for clients
3. **Encrypted Communication** - All traffic between client and server encrypted

---

## 🏗️ **Authentication Architecture**

```
┌─────────────────────────────────────────────────────────────┐
│                     Production Setup                        │
│                                                             │
│  ┌─────────────┐  mTLS + JWT   ┌─────────────────────────┐  │
│  │ FastAPI App │ ◄──────────► │    Temporal Server      │  │
│  │             │               │                         │  │
│  │ - Client    │               │ - mTLS enabled          │  │
│  │   cert      │               │ - JWT validation        │  │
│  │ - JWT token │               │ - Role-based access     │  │
│  └─────────────┘               └─────────────────────────┘  │
│                                             │               │
│                                             │ Encrypted     │
│                                             │ connection    │
│                                             ▼               │
│                                 ┌─────────────────────────┐  │
│                                 │    PostgreSQL           │  │
│                                 │                         │  │
│                                 │ - Temporal schemas      │  │
│                                 │ - Workflow data         │  │
│                                 └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔑 **Authentication Components**

### **1. TLS Certificates**

Generated automatically on first startup:

```bash
/etc/temporal/certs/
├── ca.crt                    # Certificate Authority
├── ca.key                    # CA private key
├── temporal-server.crt       # Server certificate
├── temporal-server.key       # Server private key
├── temporal-client.crt       # Client certificate
├── temporal-client.key       # Client private key
├── temporal-jwt-private.key  # JWT signing key
└── temporal-jwt-public.key   # JWT verification key
```

### **2. JWT Tokens**

Three types of access tokens:

| Token Type | Scope | Access Level | Usage |
|------------|-------|--------------|-------|
| **System** | `temporal-system` | Full admin | Server management, namespace admin |
| **Worker** | `temporal-worker` | Execute workflows | Worker processes |
| **Client** | `temporal-client` | Start workflows | Application clients |

### **3. Certificate Validation**

The server validates:
- ✅ Client certificate is signed by CA
- ✅ Certificate is not expired
- ✅ JWT token is valid and not expired
- ✅ JWT scope matches requested operation

---

## 🚀 **How to Use Authenticated Temporal**

### **1. From Your FastAPI Application**

```python
from temporalio.client import Client, TLSConfig
from pathlib import Path

async def get_temporal_client():
    # Read certificates
    certs_dir = Path("/etc/temporal/certs")
    
    tls_config = TLSConfig(
        client_cert=certs_dir.joinpath("temporal-client.crt").read_bytes(),
        client_private_key=certs_dir.joinpath("temporal-client.key").read_bytes(),
        server_root_ca_cert=certs_dir.joinpath("ca.crt").read_bytes(),
        domain="temporal-server"
    )
    
    # Read JWT token
    jwt_token = certs_dir.joinpath("client-token.jwt").read_text().strip()
    
    client = await Client.connect(
        "temporal:7233",
        tls=tls_config,
        rpc_metadata={"authorization": f"Bearer {jwt_token}"}
    )
    
    return client

# Use the client
async def start_my_workflow():
    client = await get_temporal_client()
    
    handle = await client.start_workflow(
        "MyWorkflow",
        "input-data",
        id="workflow-123",
        task_queue="my-queue"
    )
    
    return await handle.result()
```

### **2. From CLI (Temporal CLI)**

```bash
# First, get into the temporal container
docker exec -it app_data_temporal_server bash

# Use system token for admin operations
temporal workflow list \
  --address temporal:7233 \
  --tls-cert-path /etc/temporal/certs/temporal-client.crt \
  --tls-key-path /etc/temporal/certs/temporal-client.key \
  --tls-ca-path /etc/temporal/certs/ca.crt \
  --auth-plugin jwt \
  --auth-token-file /etc/temporal/certs/system-token.jwt

# Create a namespace
temporal namespace create my-namespace \
  --address temporal:7233 \
  --tls-cert-path /etc/temporal/certs/temporal-client.crt \
  --tls-key-path /etc/temporal/certs/temporal-client.key \
  --tls-ca-path /etc/temporal/certs/ca.crt \
  --auth-plugin jwt \
  --auth-token-file /etc/temporal/certs/system-token.jwt
```

### **3. From Worker Processes**

```python
from temporalio.worker import Worker
from temporalio.client import Client, TLSConfig

async def start_worker():
    # Get authenticated client
    client = await get_temporal_client()  # Same as above
    
    # Create worker with authenticated client
    worker = Worker(
        client,
        task_queue="my-task-queue",
        workflows=[MyWorkflow],
        activities=[my_activity]
    )
    
    await worker.run()
```

---

## 🔧 **Certificate Management**

### **Automatic Generation**

Certificates are automatically generated on first startup:

```bash
# Check certificate generation logs
docker logs app_data_temporal_server | grep -i cert

# Expected output:
# Generating Temporal TLS certificates...
# ✅ Temporal TLS certificates generated successfully
```

### **Manual Certificate Regeneration**

```bash
# Regenerate certificates (if needed)
docker exec app_data_temporal_server /usr/local/bin/generate-certs.sh

# Regenerate JWT tokens
docker exec app_data_temporal_server /usr/local/bin/generate-jwt-tokens.sh
```

### **Certificate Rotation**

For production certificate rotation:

```bash
# 1. Generate new certificates
docker exec app_data_temporal_server /usr/local/bin/generate-certs.sh

# 2. Restart temporal service
docker-compose -f docker-compose.prod.yml restart temporal

# 3. Update application clients with new certificates
# (Applications automatically get new certs from mounted volume)
```

---

## 🛡️ **Security Benefits**

### **Before (Insecure)**
```
❌ No encryption - traffic in plain text
❌ No authentication - anyone can connect
❌ No authorization - all operations allowed
❌ No audit trail - can't track who did what
```

### **After (Secure)**
```
✅ mTLS encryption - all traffic encrypted
✅ Certificate authentication - only trusted clients
✅ JWT authorization - role-based access control
✅ Audit logging - all operations logged
```

---

## 🧪 **Testing Authentication**

### **Test 1: Verify TLS is Working**
```bash
# Should fail without certificates
curl https://temporal:7233
# Expected: SSL certificate problem

# Should work with proper certificates
docker exec app_data_fastapi_app curl \
  --cert /etc/temporal/certs/temporal-client.crt \
  --key /etc/temporal/certs/temporal-client.key \
  --cacert /etc/temporal/certs/ca.crt \
  https://temporal:7233/health
```

### **Test 2: Verify JWT Authorization**
```bash
# Should fail without JWT token
temporal workflow list --address temporal:7233 \
  --tls-cert-path /etc/temporal/certs/temporal-client.crt \
  --tls-key-path /etc/temporal/certs/temporal-client.key \
  --tls-ca-path /etc/temporal/certs/ca.crt
# Expected: Unauthorized

# Should work with valid JWT token
temporal workflow list --address temporal:7233 \
  --tls-cert-path /etc/temporal/certs/temporal-client.crt \
  --tls-key-path /etc/temporal/certs/temporal-client.key \
  --tls-ca-path /etc/temporal/certs/ca.crt \
  --auth-plugin jwt \
  --auth-token-file /etc/temporal/certs/client-token.jwt
# Expected: Success
```

### **Test 3: Role-Based Access**
```bash
# Client token can list workflows but not admin operations
temporal workflow list --auth-token-file /etc/temporal/certs/client-token.jwt
# ✅ Success

temporal namespace create test --auth-token-file /etc/temporal/certs/client-token.jwt
# ❌ Forbidden (need system token)

temporal namespace create test --auth-token-file /etc/temporal/certs/system-token.jwt
# ✅ Success
```

---

## 🚨 **Troubleshooting**

### **Common Issues**

#### **1. Certificate Not Found**
```bash
# Error: Certificate file not found
# Solution: Check if certificates were generated
docker exec app_data_temporal_server ls -la /etc/temporal/certs/

# If empty, regenerate:
docker exec app_data_temporal_server /usr/local/bin/generate-certs.sh
```

#### **2. JWT Token Expired**
```bash
# Error: Token is expired
# Solution: Generate new tokens
docker exec app_data_temporal_server /usr/local/bin/generate-jwt-tokens.sh

# Check token expiry:
docker exec app_data_temporal_server bash -c '
  TOKEN=$(cat /etc/temporal/certs/client-token.jwt)
  echo $TOKEN | cut -d. -f2 | base64 -d | jq .exp
'
```

#### **3. TLS Handshake Failed**
```bash
# Error: TLS handshake failed
# Solution: Verify certificate hostname matches
docker exec app_data_temporal_server openssl x509 -in /etc/temporal/certs/temporal-server.crt -text -noout | grep -A3 "Subject Alternative Name"
# Should include: DNS:temporal, DNS:temporal-server
```

#### **4. Authorization Failed**
```bash
# Error: Insufficient permissions
# Solution: Check JWT token scope
docker exec app_data_temporal_server bash -c '
  TOKEN=$(cat /etc/temporal/certs/client-token.jwt)
  echo $TOKEN | cut -d. -f2 | base64 -d | jq .scope
'
# Use system-token.jwt for admin operations
```

---

## 📋 **Quick Reference**

### **Certificate Locations**
```bash
/etc/temporal/certs/ca.crt                    # Root CA
/etc/temporal/certs/temporal-client.crt       # Client cert
/etc/temporal/certs/temporal-client.key       # Client key
```

### **Token Files**
```bash
/etc/temporal/certs/system-token.jwt          # Admin access
/etc/temporal/certs/worker-token.jwt          # Worker access  
/etc/temporal/certs/client-token.jwt          # Client access
```

### **Environment Variables**
```bash
TEMPORAL_TLS_ENABLED=true                     # Enable TLS
TEMPORAL_AUTH_ENABLED=true                    # Enable auth
```

This authentication setup provides **bank-grade security** for your Temporal workflows while maintaining ease of use for development and operations!