# Docker Build Context Reference

This document explains the correct build contexts for each Dockerfile in the project.

## Why Different Build Contexts?

Each Dockerfile references files using relative paths from its expected build context. The build context determines which files are available to the `COPY` commands in the Dockerfile.

---

## Build Contexts Summary

| Image | Dockerfile Location | Build Context | Reason |
|-------|-------------------|---------------|--------|
| **PostgreSQL** | `infra/docker/prod/postgres/Dockerfile` | `infra/docker/prod` | References `postgres/`, `scripts/` dirs |
| **Redis** | `infra/docker/prod/redis/Dockerfile` | `infra/docker/prod/redis` | All files in same dir |
| **Temporal** | `infra/docker/prod/temporal/Dockerfile` | `infra/docker/prod/temporal` | Downloads binary, no local files |
| **Application** | `Dockerfile` | Project root | References `src/`, `pyproject.toml`, etc. |

---

## Detailed Explanation

### 1. PostgreSQL Image

**Dockerfile**: `infra/docker/prod/postgres/Dockerfile`

**Build Context**: `infra/docker/prod`

**Why?** The Dockerfile contains these COPY commands:
```dockerfile
COPY postgres/start-scripts/ /opt/entry/start-scripts/
COPY postgres/admin-scripts/ /opt/entry/admin-scripts/
COPY postgres/init-scripts/ /docker-entrypoint-initdb.d/
COPY scripts/universal-entrypoint.sh /opt/entry/start-scripts/
```

These paths are relative to `infra/docker/prod`, so the build context must be set there.

**Correct Build Command**:
```bash
cd infra/docker/prod
docker build -f postgres/Dockerfile -t app_data_postgres_image:latest .
cd ../../..
```

**Directory Structure Expected**:
```
infra/docker/prod/          ← Build context
├── postgres/               ← Dockerfile references this
│   ├── Dockerfile
│   ├── start-scripts/
│   ├── admin-scripts/
│   └── init-scripts/
└── scripts/                ← Dockerfile references this
    └── universal-entrypoint.sh
```

---

### 2. Redis Image

**Dockerfile**: `infra/docker/prod/redis/Dockerfile`

**Build Context**: `infra/docker/prod/redis`

**Why?** The Dockerfile contains these COPY commands:
```dockerfile
COPY redis.conf /usr/local/etc/redis/redis.conf
COPY backup-scripts/ /usr/local/bin/
COPY docker-entrypoint.sh /usr/local/bin/
```

All referenced files are in the same directory as the Dockerfile.

**Correct Build Command**:
```bash
cd infra/docker/prod/redis
docker build -t app_data_redis_image:latest .
cd ../../../..
```

**Directory Structure Expected**:
```
infra/docker/prod/redis/    ← Build context
├── Dockerfile
├── redis.conf              ← Referenced files
├── backup-scripts/
└── docker-entrypoint.sh
```

---

### 3. Temporal Image

**Dockerfile**: `infra/docker/prod/temporal/Dockerfile`

**Build Context**: `infra/docker/prod/temporal` (or any directory)

**Why?** The Dockerfile only downloads a binary from the internet:
```dockerfile
FROM temporalio/server:1.29.0
USER root
ADD --chmod=755 https://github.com/grpc-ecosystem/grpc-health-probe/... /usr/local/bin/grpc_health_probe
USER temporal
```

No local files are referenced, so the build context doesn't matter much.

**Correct Build Command**:
```bash
cd infra/docker/prod/temporal
docker build -t my-temporal-server:1.29.0 .
cd ../../../..
```

---

### 4. Application Image (FastAPI)

**Dockerfile**: `Dockerfile` (project root)

**Build Context**: Project root

**Why?** The Dockerfile contains these COPY commands:
```dockerfile
COPY pyproject.toml uv.lock ./
COPY src/ src/
COPY src_main.py ./
COPY config.yaml ./
COPY infra/docker/prod/scripts/universal-entrypoint.sh /usr/local/bin/
```

All these paths are relative to the project root.

**Correct Build Command**:
```bash
# From project root
docker build -f Dockerfile -t api-template-app:latest .
```

**Directory Structure Expected**:
```
/                           ← Build context (project root)
├── Dockerfile
├── pyproject.toml          ← Referenced files
├── uv.lock
├── config.yaml
├── src_main.py
├── src/
└── infra/docker/prod/scripts/
    └── universal-entrypoint.sh
```

---

## Common Mistakes

### ❌ Incorrect: Building from Wrong Context

```bash
# WRONG - PostgreSQL from project root
docker build -f infra/docker/prod/postgres/Dockerfile -t app_data_postgres_image:latest .
# Error: COPY failed: file not found in build context

# WRONG - Redis from parent directory
cd infra/docker/prod
docker build -f redis/Dockerfile -t app_data_redis_image:latest .
# Error: redis.conf not found
```

### ✅ Correct: Using Proper Build Context

```bash
# CORRECT - PostgreSQL
cd infra/docker/prod
docker build -f postgres/Dockerfile -t app_data_postgres_image:latest .
cd ../../..

# CORRECT - Redis
cd infra/docker/prod/redis
docker build -t app_data_redis_image:latest .
cd ../../../..

# CORRECT - Application
docker build -f Dockerfile -t api-template-app:latest .
```

---

## Automated Build Script

**Use the provided script to avoid context issues**:

```bash
./k8s/scripts/build-images.sh
```

This script:
- ✅ Automatically changes to correct directories
- ✅ Uses correct build contexts for each image
- ✅ Detects Minikube/kind/k3d and loads images
- ✅ Validates all images were built successfully
- ✅ Provides colored output for easy debugging

---

## Docker Compose vs Kubernetes

### Docker Compose (docker-compose.prod.yml)

In Docker Compose, the build context is specified explicitly:

```yaml
services:
  postgres:
    build:
      context: ./infra/docker/prod    # ← Explicit context
      dockerfile: postgres/Dockerfile
```

### Kubernetes (Manual Builds)

In Kubernetes, you build images manually, so you must:
1. Navigate to the correct directory (context)
2. Run `docker build` with the right Dockerfile path
3. Tag appropriately
4. Push to registry (for production)

---

## Troubleshooting

### "COPY failed: file not found in build context"

**Cause**: Wrong build context directory

**Solution**: Check the `COPY` commands in the Dockerfile and ensure the build context includes those files.

**Example**:
```
Dockerfile: infra/docker/prod/postgres/Dockerfile
COPY command: COPY postgres/start-scripts/ ...
Build context must be: infra/docker/prod  (where postgres/ dir exists)
```

### "no such file or directory"

**Cause**: Dockerfile path is wrong or you're in the wrong directory

**Solution**: 
1. Verify the Dockerfile exists: `ls -la path/to/Dockerfile`
2. Use the build script: `./k8s/scripts/build-images.sh`

### Images work in Docker Compose but fail in Kubernetes

**Cause**: Docker Compose specifies build context automatically, but you built images with wrong context for Kubernetes

**Solution**: Use `./k8s/scripts/build-images.sh` which handles correct contexts

---

## Quick Reference Commands

```bash
# Build all images (recommended)
./k8s/scripts/build-images.sh

# Build individual images manually

# PostgreSQL
(cd infra/docker/prod && docker build -f postgres/Dockerfile -t app_data_postgres_image:latest .)

# Redis
(cd infra/docker/prod/redis && docker build -t app_data_redis_image:latest .)

# Temporal
(cd infra/docker/prod/temporal && docker build -t my-temporal-server:1.29.0 .)

# Application
docker build -f Dockerfile -t api-template-app:latest .
```

---

## For CI/CD Pipelines

If building in CI/CD, use absolute paths or ensure working directory:

```yaml
# Example GitHub Actions
- name: Build PostgreSQL Image
  run: |
    cd infra/docker/prod
    docker build -f postgres/Dockerfile -t app_data_postgres_image:latest .
  
- name: Build Redis Image
  run: |
    cd infra/docker/prod/redis
    docker build -t app_data_redis_image:latest .

- name: Build Temporal Image
  run: |
    cd infra/docker/prod/temporal
    docker build -t my-temporal-server:1.29.0 .

- name: Build Application Image
  run: docker build -f Dockerfile -t api-template-app:latest .
```

Or use the automated script:

```yaml
- name: Build All Images
  run: ./k8s/scripts/build-images.sh
```

---

## Summary

| Command | What It Does |
|---------|--------------|
| `./k8s/scripts/build-images.sh` | **Recommended**: Builds all images with correct contexts |
| Manual builds | See "Quick Reference Commands" above |
| Verify images | `docker images \| grep -E "app_data\|temporal\|api-template"` |
| Load into kind | Automatic with build script, or `kind load docker-image <image>` |
| Load into k3d | Automatic with build script, or `k3d image import <image>` |
