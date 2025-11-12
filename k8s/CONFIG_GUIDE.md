# Kubernetes Configuration: Simple Guide

## Overview

Your Kubernetes configuration is automatically generated from your `.env` file. No manual YAML editing needed.

## How It Works

```
.env  →  copy to k8s/base/.env.k8s  →  Kustomize  →  ConfigMap  →  Your app
```

1. You edit `.env` in the project root
2. The deploy script copies it to `k8s/base/.env.k8s` (kustomize security requirement)
3. Kustomize reads `k8s/base/.env.k8s` and generates a ConfigMap
4. Your app gets the config as environment variables

## Setup (Already Done)

The `k8s/base/kustomization.yaml` file has this section:

```yaml
configMapGenerator:
  - name: app-env
    envs:
      - .env.k8s
    options:
      disableNameSuffixHash: true
```

This tells Kustomize: "Generate a ConfigMap named `app-env` from `.env.k8s` (in the same directory)."

**Note:** Kustomize has a security restriction - it can only read files in the same directory or subdirectories. That's why the deploy script copies your `.env` to `k8s/base/.env.k8s` before deploying.

## Daily Workflow

### Change configuration

```bash
vim .env
```

### Deploy changes

```bash
./k8s/scripts/deploy-config.sh --restart
```

That's it! The script:
- Validates your `.env` file
- Generates the ConfigMap from `.env`
- Deploys to Kubernetes
- Restarts your app to pick up changes

## Manual Deployment

If you prefer to run commands directly:

```bash
# Deploy (ConfigMap auto-generated from .env)
kubectl apply -k k8s/base/

# Restart app to pick up config changes
kubectl rollout restart deployment/app -n api-template-prod
```

## What Goes in .env

**Non-sensitive configuration only:**
- Database URLs (without passwords)
- Redis URLs (without passwords)
- Feature flags
- API endpoints
- Port numbers
- Environment name (development/production)

**NOT secrets:**
- Passwords → Use Kubernetes Secrets
- API keys → Use Kubernetes Secrets
- Tokens → Use Kubernetes Secrets
- Certificates → Use Kubernetes Secrets

## Environment-Specific Values

Your `.env` file should use the `PRODUCTION_*` and `DEVELOPMENT_*` pattern:

```bash
APP_ENVIRONMENT=production

DEVELOPMENT_DATABASE_URL=postgresql://user@localhost:5433/db
PRODUCTION_DATABASE_URL=postgresql://user@postgres:5432/db

DEVELOPMENT_REDIS_URL=redis://localhost:6380
PRODUCTION_REDIS_URL=redis://redis:6379
```

Your app's `config.yaml` decides which to use based on `APP_ENVIRONMENT`.

## Troubleshooting

### ConfigMap not updating

The ConfigMap only updates when you run `kubectl apply -k k8s/base/`. Changes to `.env` don't automatically deploy.

**Solution:** Run the deploy script or `kubectl apply -k k8s/base/`

### App not picking up new config

Your app reads config at startup. It won't see changes until it restarts.

**Solution:** Add `--restart` flag to the deploy script, or manually:
```bash
kubectl rollout restart deployment/app -n api-template-prod
```

### "unable to find file .env.k8s"

The deploy script failed to copy `.env` to `k8s/base/.env.k8s`.

**Solution:** 
```bash
# Make sure .env exists
cp .env.example .env
vim .env  # Add real values

# Run deploy script (it will copy .env to k8s/.env.k8s)
./k8s/scripts/deploy-config.sh
```

## Advanced: Preview Without Deploying

```bash
# See what would be generated
kubectl kustomize k8s/base/ | less

# See just the ConfigMap
kubectl kustomize k8s/base/ | grep -A 100 "kind: ConfigMap"
```

## Files You Care About

```
.env                           # Your configuration (edit this)
k8s/base/.env.k8s              # Copy of .env (auto-generated, gitignored)
k8s/base/kustomization.yaml    # Has configMapGenerator (don't touch)
k8s/scripts/deploy-config.sh   # Deployment script (run this)
```

## Summary

**What you do:**
1. Edit `.env`
2. Run `./k8s/scripts/deploy-config.sh --restart`

**What happens automatically:**
1. Kustomize reads `.env`
2. Generates ConfigMap with all your vars
3. Deploys to Kubernetes
4. App restarts with new config

**No manual YAML editing. No extra files. Simple.**
