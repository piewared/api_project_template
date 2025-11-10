# Kubernetes Automation Scripts

This directory contains automation scripts for building, deploying, and managing the Kubernetes resources.

## Scripts Overview

| Script | Purpose | Usage |
|--------|---------|-------|
| `build-images.sh` | Build all Docker images | `./build-images.sh` |
| `create-secrets.sh` | Create Kubernetes secrets | `./create-secrets.sh [namespace]` |
| `deploy-resources.sh` | Deploy all resources | `./deploy-resources.sh [namespace]` |

## Quick Start

For a complete fresh deployment:

```bash
# 1. Build images
./build-images.sh

# 2. Generate secrets (from project root)
cd ../../infra/secrets && ./generate_secrets.sh && cd -

# 3. Create Kubernetes secrets
./create-secrets.sh

# 4. Deploy everything
./deploy-resources.sh
```

## Script Details

### build-images.sh

Builds all required Docker images with proper build contexts.

**Requirements**:
- Docker installed and running
- Kubernetes cluster running (Minikube, kind, k3d, or Docker Desktop)

**What it does**:
- Detects your cluster type automatically
- Builds 4 images:
  - `app_data_postgres_image` - PostgreSQL with custom config
  - `app_data_redis_image` - Redis with custom config
  - `my-temporal-server:1.29.0` - Temporal server
  - `api-template-app:latest` - FastAPI application
- Loads images into cluster (Minikube/kind/k3d)
- Verifies all images exist

**Exit codes**:
- `0` - Success
- `1` - Build failed or images not found

---

### create-secrets.sh

Creates Kubernetes secrets from files in `infra/secrets/`.

**Requirements**:
- kubectl installed and configured
- Kubernetes cluster accessible
- Secrets generated in `infra/secrets/` (run `infra/secrets/generate_secrets.sh` first)

**Arguments**:
- `[namespace]` - Target namespace (default: `api-template-prod`)

**What it does**:
- Creates namespace if missing
- Deletes existing secrets (clean slate)
- Creates 5 secret resources:
  - `postgres-secrets` - Database passwords
  - `postgres-tls` - PostgreSQL TLS certificate and key
  - `postgres-ca` - CA bundle for TLS verification
  - `redis-secrets` - Redis password
  - `app-secrets` - Session and CSRF signing secrets
- Verifies all secrets exist

**Exit codes**:
- `0` - Success
- `1` - Prerequisites failed, secret files missing, or creation failed

**Example with custom namespace**:
```bash
./create-secrets.sh my-app-prod
```

---

### deploy-resources.sh

Deploys all Kubernetes resources in dependency order with health checks.

**Requirements**:
- kubectl installed and configured
- Kubernetes cluster accessible
- Docker images built (run `build-images.sh` first)
- Secrets created (run `create-secrets.sh` first)

**Arguments**:
- `[namespace]` - Target namespace (default: `api-template-prod`)

**What it does**:
1. **Checks prerequisites** - kubectl, cluster, secrets
2. **Deploys namespace** - Creates if missing
3. **Deploys storage** - PersistentVolumeClaims
4. **Deploys ConfigMaps** - All configuration files
5. **Deploys Services** - ClusterIP services for all components
6. **Deploys databases** - PostgreSQL and Redis
   - Waits up to 120s for each to be ready
7. **Initializes Temporal** - Runs schema setup job
   - Waits up to 300s for completion
8. **Deploys Temporal** - Temporal server and web UI
   - Waits up to 120s for server to be ready
9. **Deploys application** - FastAPI app
   - Waits up to 120s for app to be ready
10. **Verifies deployment** - Checks pod status and app health
11. **Displays next steps** - Commands for accessing services

**Exit codes**:
- `0` - Success
- `1` - Prerequisites failed, deployment failed, or health checks failed

**Example with custom namespace**:
```bash
./deploy-resources.sh staging
```

**Output**:
The script provides colored output:
- 🟢 Green - Info messages
- 🔵 Blue - Step progress
- 🟡 Yellow - Warnings
- 🔴 Red - Errors

---

## Troubleshooting

### Images not loading into cluster

**Symptom**: Script says images built successfully but pods show `ImagePullBackOff`

**Solution**:
```bash
# For Minikube, ensure you're using the Minikube Docker daemon
eval $(minikube docker-env)
./build-images.sh

# For kind, images should auto-load. If not, manually load:
kind load docker-image api-template-app:latest
kind load docker-image my-temporal-server:1.29.0
kind load docker-image app_data_postgres_image
kind load docker-image app_data_redis_image
```

### Secrets not found

**Symptom**: `deploy-resources.sh` fails with "Missing required secrets"

**Solution**:
```bash
# Generate secrets first
cd ../../infra/secrets
./generate_secrets.sh
cd -

# Then create Kubernetes secrets
./create-secrets.sh
```

### Deployment timeout

**Symptom**: Script waits forever for a pod to be ready

**Check pod status**:
```bash
kubectl get pods -n api-template-prod
kubectl describe pod <pod-name> -n api-template-prod
kubectl logs <pod-name> -n api-template-prod
```

**Common causes**:
- Image pull failure (wrong imagePullPolicy or missing image)
- Insufficient cluster resources (try `minikube config set memory 8192`)
- Configuration error (check ConfigMaps and Secrets)

### Permission denied running scripts

**Solution**:
```bash
chmod +x *.sh
```

---

## Development

### Adding a new resource

If you add a new Kubernetes resource, update `deploy-resources.sh`:

1. Add the file to the appropriate deployment step function
2. If it's a critical service, add a health check
3. Update the step count in log messages
4. Test the full deployment

### Modifying deployment order

The deployment order is critical:
1. Namespace (must exist first)
2. Storage (needed by stateful workloads)
3. ConfigMaps (needed by all pods)
4. Services (networking layer)
5. Databases (dependencies for other services)
6. Temporal setup (must complete before Temporal)
7. Temporal (dependency for app)
8. Application (final layer)

Do not change this order without thorough testing.

---

## CI/CD Integration

These scripts can be used in CI/CD pipelines:

**GitHub Actions example**:
```yaml
- name: Deploy to Kubernetes
  run: |
    ./k8s/scripts/build-images.sh
    ./k8s/scripts/create-secrets.sh production
    ./k8s/scripts/deploy-resources.sh production
```

**GitLab CI example**:
```yaml
deploy:
  script:
    - ./k8s/scripts/build-images.sh
    - ./k8s/scripts/create-secrets.sh production
    - ./k8s/scripts/deploy-resources.sh production
```

---

## See Also

- [../DEPLOYMENT_GUIDE.md](../DEPLOYMENT_GUIDE.md) - Complete deployment documentation
- [../BUILD_CONTEXTS.md](../BUILD_CONTEXTS.md) - Docker build context explanations
- [../LOCAL_TESTING.md](../LOCAL_TESTING.md) - Local testing guide
