# Kubernetes Deployment Guide

This directory contains production-ready Kubernetes manifests for the API Template application, organized using best practices and Kustomize for easy management.

## 📁 Directory Structure

```
k8s/
├── base/                          # Base Kubernetes manifests
│   ├── namespace/                 # Namespace definition
│   │   └── namespace.yaml
│   ├── storage/                   # PersistentVolumeClaims
│   │   └── persistentvolumeclaims.yaml
│   ├── configmaps/                # Configuration data
│   │   ├── env-config.yaml        # Environment variables
│   │   ├── postgres-config.yaml   # PostgreSQL configuration
│   │   ├── postgres-verifier-config.yaml
│   │   ├── temporal-config.yaml   # Temporal configuration
│   │   └── app-config.yaml        # Application configuration
│   ├── services/                  # Kubernetes Services
│   │   └── services.yaml
│   ├── deployments/               # Application deployments
│   │   ├── postgres.yaml
│   │   ├── redis.yaml
│   │   ├── temporal.yaml
│   │   ├── temporal-web.yaml
│   │   └── app.yaml
│   ├── jobs/                      # Initialization jobs
│   │   ├── postgres-verifier.yaml
│   │   ├── temporal-schema-setup.yaml
│   │   └── temporal-namespace-init.yaml
│   └── kustomization.yaml         # Kustomize configuration
└── scripts/                       # Helper scripts
    └── create-secrets.sh          # Secret creation script
```

## 🚀 Quick Start

### Prerequisites

1. **Kubernetes Cluster**: Running cluster with kubectl configured
2. **kubectl**: Version 1.21+ installed
3. **Kustomize**: Version 4.0+ (or use kubectl apply -k)
4. **Secrets**: Generated using `infra/secrets/generate_secrets.sh`

### Step 1: Generate Secrets

Before deploying, you must generate the required secrets:

```bash
# Navigate to project root
cd /path/to/api_project_template3

# Generate secrets if not already done
./infra/secrets/generate_secrets.sh

# Verify secrets exist
ls -la infra/secrets/keys/
ls -la infra/secrets/certs/
```

### Step 2: Create Kubernetes Secrets

Run the secret creation script to create all Kubernetes secrets:

```bash
# Create secrets in default namespace (api-template-prod)
./k8s/scripts/create-secrets.sh

# Or specify a custom namespace
./k8s/scripts/create-secrets.sh my-namespace
```

This script creates:
- `postgres-secrets`: All PostgreSQL passwords
- `postgres-tls`: PostgreSQL TLS certificates
- `postgres-ca`: CA certificate bundle
- `redis-secrets`: Redis password
- `app-secrets`: Session and CSRF signing secrets

### Step 3: Build and Push Docker Images

Build all images using the automated build script:

```bash
# Build all images with correct build contexts
./k8s/scripts/build-images.sh

# This script automatically:
# - Detects if you're using Minikube/kind/k3d
# - Builds all 4 images with correct contexts
# - Loads images into local cluster (if kind/k3d)
# - Verifies all images were built successfully
```

**Manual Build (if needed):**

```bash
# PostgreSQL (context: infra/docker/prod)
cd infra/docker/prod
docker build -f postgres/Dockerfile -t app_data_postgres_image:latest .
cd ../../..

# Redis (context: infra/docker/prod/redis)
cd infra/docker/prod/redis
docker build -t app_data_redis_image:latest .
cd ../../../..

# Temporal (context: infra/docker/prod/temporal)
cd infra/docker/prod/temporal
docker build -t my-temporal-server:1.29.0 .
cd ../../../..

# Application (context: project root)
docker build -f Dockerfile -t api-template-app:latest .
```

**For Production (with registry):**

```bash
# Tag and push to your registry
docker tag api-template-app:latest your-registry.io/api-template-app:1.0.0
docker tag app_data_postgres_image:latest your-registry.io/postgres:latest
docker tag app_data_redis_image:latest your-registry.io/redis:latest
docker tag my-temporal-server:1.29.0 your-registry.io/temporal:1.29.0

# Push all images
docker push your-registry.io/api-template-app:1.0.0
docker push your-registry.io/postgres:latest
docker push your-registry.io/redis:latest
docker push your-registry.io/temporal:1.29.0

# Update image references in manifests
# Edit k8s/base/deployments/*.yaml to use your registry URLs
```

### Step 4: Deploy to Kubernetes

Deploy all resources using Kustomize:

```bash
# Deploy everything
kubectl apply -k k8s/base/

# Watch deployment progress
kubectl get pods -n api-template-prod -w
```

## 📊 Deployment Order

The kustomization.yaml ensures resources are deployed in the correct order:

1. **Namespace** - Creates the namespace
2. **Storage** - Creates PersistentVolumeClaims
3. **ConfigMaps** - Loads configuration data
4. **Services** - Creates network services
5. **Deployments** - Deploys applications
6. **Jobs** - Runs initialization tasks

## 🔍 Verification

### Check Deployment Status

```bash
# Check all resources
kubectl get all -n api-template-prod

# Check pods
kubectl get pods -n api-template-prod

# Check services
kubectl get svc -n api-template-prod

# Check PVCs
kubectl get pvc -n api-template-prod

# Check jobs
kubectl get jobs -n api-template-prod
```

### Check Pod Logs

```bash
# PostgreSQL logs
kubectl logs -n api-template-prod deployment/postgres -f

# Redis logs
kubectl logs -n api-template-prod deployment/redis -f

# Temporal logs
kubectl logs -n api-template-prod deployment/temporal -f

# Application logs
kubectl logs -n api-template-prod deployment/app -f

# Job logs
kubectl logs -n api-template-prod job/postgres-verifier
kubectl logs -n api-template-prod job/temporal-schema-setup
kubectl logs -n api-template-prod job/temporal-namespace-init
```

### Health Checks

```bash
# Port-forward to application
kubectl port-forward -n api-template-prod svc/app 8000:8000

# Test health endpoint
curl http://localhost:8000/health

# Port-forward to Temporal UI
kubectl port-forward -n api-template-prod svc/temporal-web 8080:8080

# Access at http://localhost:8080
```

## 🔧 Configuration

### Environment Variables

Edit `k8s/base/configmaps/env-config.yaml` to change:
- `APP_ENVIRONMENT`: production, staging, development
- `LOG_LEVEL`: DEBUG, INFO, WARNING, ERROR
- `TZ`: Timezone (default: UTC)

### Application Configuration

Edit `k8s/base/configmaps/app-config.yaml` to configure:
- Database connection settings
- Redis settings
- OIDC providers
- Session management
- CORS settings

### Resource Limits

Adjust resources in deployment files:

```yaml
resources:
  requests:
    cpu: 250m      # Minimum CPU
    memory: 128Mi  # Minimum memory
  limits:
    cpu: 1000m     # Maximum CPU
    memory: 512Mi  # Maximum memory
```

### Storage Sizes

Edit `k8s/base/storage/persistentvolumeclaims.yaml` to adjust storage:

```yaml
resources:
  requests:
    storage: 20Gi  # Adjust as needed
```

## 🔐 Security Features

### 1. Secret Management
- Secrets created imperatively (not committed to git)
- Read-only mounts with 0400 permissions
- Individual file mounts (not directories)

### 2. Security Contexts
- All containers run as non-root users
- Capabilities dropped to minimum required
- Seccomp profile enabled
- Read-only root filesystem where possible

### 3. Network Policies
Services use ClusterIP (internal only). To expose externally:

```yaml
# Add Ingress or LoadBalancer
apiVersion: v1
kind: Service
metadata:
  name: app
spec:
  type: LoadBalancer  # or use Ingress
```

### 4. TLS/mTLS
- PostgreSQL: TLS-only connections enforced
- Redis: Password authentication
- Temporal: TLS for database connections

## 🛠 Troubleshooting

### Pods Not Starting

```bash
# Describe pod to see events
kubectl describe pod -n api-template-prod <pod-name>

# Check pod logs
kubectl logs -n api-template-prod <pod-name>

# Check previous pod logs (if crashed)
kubectl logs -n api-template-prod <pod-name> --previous
```

### Common Issues

#### 1. ImagePullBackOff
```bash
# Issue: Cannot pull custom images
# Solution: Ensure images are built and available
docker images | grep api-template

# For local testing with kind/minikube
kind load docker-image api-template-app:latest
```

#### 2. CrashLoopBackOff
```bash
# Check logs for errors
kubectl logs -n api-template-prod deployment/app

# Common causes:
# - Missing secrets
# - Database connection issues
# - Configuration errors
```

#### 3. Secrets Not Found
```bash
# Verify secrets exist
kubectl get secrets -n api-template-prod

# Re-create secrets
./k8s/scripts/create-secrets.sh api-template-prod
```

#### 4. Jobs Failing
```bash
# Check job status
kubectl get jobs -n api-template-prod

# Check job logs
kubectl logs -n api-template-prod job/postgres-verifier

# Delete and re-run job
kubectl delete job -n api-template-prod postgres-verifier
kubectl apply -f k8s/base/jobs/postgres-verifier.yaml
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
kubectl exec -it -n api-template-prod deployment/postgres -- psql -U appuser -d appdb

# Test Redis connection
kubectl exec -it -n api-template-prod deployment/redis -- redis-cli ping
```

## 🔄 Updates and Rollbacks

### Rolling Update

```bash
# Update application image
kubectl set image deployment/app app=api-template-app:1.1.0 -n api-template-prod

# Watch rollout
kubectl rollout status deployment/app -n api-template-prod
```

### Rollback

```bash
# View rollout history
kubectl rollout history deployment/app -n api-template-prod

# Rollback to previous version
kubectl rollout undo deployment/app -n api-template-prod

# Rollback to specific revision
kubectl rollout undo deployment/app --to-revision=2 -n api-template-prod
```

## 🧹 Cleanup

### Delete Everything

```bash
# Delete all resources
kubectl delete -k k8s/base/

# Or delete namespace (removes everything)
kubectl delete namespace api-template-prod
```

### Preserve Data

To keep PersistentVolumes after deletion:

```bash
# Delete deployments but keep PVCs
kubectl delete deployment --all -n api-template-prod
kubectl delete svc --all -n api-template-prod

# PVCs remain for data persistence
```

## 📈 Scaling

### Horizontal Scaling

```bash
# Scale application
kubectl scale deployment/app --replicas=3 -n api-template-prod

# Auto-scaling with HPA
kubectl autoscale deployment/app --min=2 --max=10 --cpu-percent=80 -n api-template-prod
```

**Note**: PostgreSQL and Redis should remain at 1 replica unless using replication.

## 🔗 Accessing Services

### From Within Cluster

Services are accessible via DNS:
- PostgreSQL: `postgres.api-template-prod.svc.cluster.local:5432`
- Redis: `redis.api-template-prod.svc.cluster.local:6379`
- Temporal: `temporal.api-template-prod.svc.cluster.local:7233`
- App: `app.api-template-prod.svc.cluster.local:8000`

### From Outside Cluster

Use port-forwarding for testing:

```bash
# Application
kubectl port-forward -n api-template-prod svc/app 8000:8000

# Temporal UI
kubectl port-forward -n api-template-prod svc/temporal-web 8080:8080

# PostgreSQL (for debugging only)
kubectl port-forward -n api-template-prod svc/postgres 5432:5432
```

For production, use Ingress:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
  namespace: api-template-prod
spec:
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: app
                port:
                  number: 8000
```

## 📚 Additional Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Kustomize Documentation](https://kustomize.io/)
- [PostgreSQL on Kubernetes](https://www.postgresql.org/docs/)
- [Temporal Documentation](https://docs.temporal.io/)

## 🤝 Contributing

When modifying manifests:
1. Test in development environment first
2. Update this README if adding new resources
3. Maintain consistent labels and annotations
4. Follow security best practices

## 📝 Notes

### Differences from Docker Compose

| Feature | Docker Compose | Kubernetes |
|---------|---------------|------------|
| Secrets | File-based | Kubernetes Secrets API |
| Networking | Named networks | Services + DNS |
| Storage | Bind mounts | PersistentVolumeClaims |
| Health Checks | Built-in | Liveness/Readiness Probes |
| Dependencies | depends_on | Init Containers/Jobs |
| Timezone | /etc/localtime mount | TZ environment variable |

### Best Practices Applied

✅ Consolidated ConfigMaps (5 vs 12 original)  
✅ Consolidated Secrets (5 vs 11 original)  
✅ Jobs instead of Pods for init tasks  
✅ Proper security contexts on all resources  
✅ Resource limits and requests defined  
✅ Liveness and readiness probes  
✅ Correct secret mount paths  
✅ Fixed healthcheck commands  
✅ Standard memory/CPU units (Mi, m)  
✅ Namespace isolation  
✅ Kustomize for easy management  
✅ Comprehensive documentation  

---

**Version**: 1.0.0  
**Last Updated**: 2025-11-09  
**Maintained By**: DevOps Team
