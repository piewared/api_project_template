#!/bin/bash
set -e

################################################################################
# deploy-config.sh
# 
# Syncs configuration from source files and deploys to Kubernetes
# 
# What it does:
# 1. Syncs config files from source locations to k8s ConfigMaps:
#    - .env → app-env ConfigMap
#    - config.yaml → app-config ConfigMap
#    - infra/docker/prod/postgres/* → postgres-config ConfigMap
#    - infra/docker/prod/postgres/verify-init.sh → postgres-verifier-config
# 2. Deploys all resources to Kubernetes
# 3. Optionally restarts the app to pick up config changes
#
# Usage:
#   ./k8s/scripts/deploy-config.sh [--restart] [--sync-only]
#
# Options:
#   --restart     Also restart the app deployment after updating ConfigMap
#   --sync-only   Only sync config files, don't deploy
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
K8S_DIR="$PROJECT_ROOT/k8s"
K8S_BASE="$K8S_DIR/base"
CONFIGMAPS_DIR="$K8S_BASE/configmaps"
ENV_FILE="$PROJECT_ROOT/.env"
K8S_ENV_FILE="$K8S_BASE/.env.k8s"

RESTART_APP=false
SYNC_ONLY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --restart)
      RESTART_APP=true
      shift
      ;;
    --sync-only)
      SYNC_ONLY=true
      shift
      ;;
    --help)
      head -n 21 "$0" | tail -n +3
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Run with --help for usage"
      exit 1
      ;;
  esac
done

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "==========================================="
echo "  Kubernetes Configuration Sync & Deploy"
echo "==========================================="
echo ""

# ============================================================================
# STEP 1: Sync .env file
# ============================================================================
echo -e "${YELLOW}Step 1: Syncing .env file${NC}"
echo "-------------------------------------------"

if [[ ! -f "$ENV_FILE" ]]; then
  echo -e "${RED}✗ Error: .env file not found at: $ENV_FILE${NC}"
  echo ""
  echo "Create it from .env.example:"
  echo "  cp .env.example .env"
  echo "  vim .env"
  exit 1
fi

echo -n "  .env → k8s/base/.env.k8s... "
cp "$ENV_FILE" "$K8S_ENV_FILE"
echo -e "${GREEN}✓${NC}"

# ============================================================================
# STEP 2: Sync config.yaml
# ============================================================================
echo ""
echo -e "${YELLOW}Step 2: Syncing config.yaml${NC}"
echo "-------------------------------------------"

CONFIG_FILE="$PROJECT_ROOT/config.yaml"
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo -e "${RED}✗ Error: config.yaml not found${NC}"
  exit 1
fi

echo -n "  Generating app-config ConfigMap... "
{
  echo "# Auto-generated from config.yaml by k8s/scripts/deploy-config.sh"
  echo "# DO NOT EDIT - Run ./k8s/scripts/deploy-config.sh to regenerate"
  echo ""
  echo "apiVersion: v1"
  echo "kind: ConfigMap"
  echo "metadata:"
  echo "  name: app-config"
  echo "  namespace: api-template-prod"
  echo "data:"
  echo "  config.yaml: |"
  sed 's/^/    /' "$CONFIG_FILE"
} > "$CONFIGMAPS_DIR/app-config.yaml"
echo -e "${GREEN}✓${NC}"

# ============================================================================
# STEP 3: Sync PostgreSQL configs
# ============================================================================
echo ""
echo -e "${YELLOW}Step 3: Syncing PostgreSQL configs${NC}"
echo "-------------------------------------------"

PG_DIR="$PROJECT_ROOT/infra/docker/prod/postgres"
PG_INIT_DIR="$PG_DIR/init-scripts"

if [[ ! -d "$PG_DIR" ]]; then
  echo -e "${RED}✗ Error: PostgreSQL config directory not found${NC}"
  exit 1
fi

echo -n "  Generating postgres-config ConfigMap... "
{
  echo "# Auto-generated from infra/docker/prod/postgres/ by k8s/scripts/deploy-config.sh"
  echo "# DO NOT EDIT - Run ./k8s/scripts/deploy-config.sh to regenerate"
  echo ""
  echo "apiVersion: v1"
  echo "kind: ConfigMap"
  echo "metadata:"
  echo "  name: postgres-config"
  echo "  namespace: api-template-prod"
  echo "  labels:"
  echo "    app.kubernetes.io/name: postgres"
  echo "    app.kubernetes.io/component: database"
  echo "data:"
  
  # PostgreSQL configuration file
  if [[ -f "$PG_DIR/postgresql.conf" ]]; then
    echo "  postgresql.conf: |"
    sed 's/^/    /' "$PG_DIR/postgresql.conf"
  fi
  
  echo ""
  
  # pg_hba.conf
  if [[ -f "$PG_DIR/pg_hba.conf" ]]; then
    echo "  pg_hba.conf: |"
    sed 's/^/    /' "$PG_DIR/pg_hba.conf"
  fi
  
  echo ""
  
  # Init script
  if [[ -f "$PG_INIT_DIR/01-init-app.sh" ]]; then
    echo "  01-init-app.sh: |"
    sed 's/^/    /' "$PG_INIT_DIR/01-init-app.sh"
  fi
} > "$CONFIGMAPS_DIR/postgres-config.yaml"
echo -e "${GREEN}✓${NC}"

# ============================================================================
# STEP 4: Sync PostgreSQL verifier
# ============================================================================
echo -n "  Generating postgres-verifier-config ConfigMap... "
VERIFY_SCRIPT="$PG_DIR/verify-init.sh"

if [[ ! -f "$VERIFY_SCRIPT" ]]; then
  echo -e "${YELLOW}⚠ Warning: verify-init.sh not found, skipping${NC}"
else
  {
    echo "# Auto-generated from infra/docker/prod/postgres/verify-init.sh"
    echo "# DO NOT EDIT - Run ./k8s/scripts/deploy-config.sh to regenerate"
    echo ""
    echo "apiVersion: v1"
    echo "kind: ConfigMap"
    echo "metadata:"
      echo "  name: postgres-verifier-config"
    echo "  namespace: api-template-prod"
    echo "  labels:"
    echo "    app.kubernetes.io/name: postgres"
    echo "    app.kubernetes.io/component: database"
    echo "data:"
    echo "  verify-postgres.sh: |"
    sed 's/^/    /' "$VERIFY_SCRIPT"
  } > "$CONFIGMAPS_DIR/postgres-verifier-config.yaml"
  echo -e "${GREEN}✓${NC}"
fi

echo ""
echo -e "${GREEN}✓ All config files synced${NC}"

# Exit early if --sync-only flag was used
if [[ "$SYNC_ONLY" == "true" ]]; then
  echo ""
  echo "Sync complete! (--sync-only mode, not deploying)"
  echo ""
  echo "To deploy, run:"
  echo "  ./k8s/scripts/deploy-config.sh"
  exit 0
fi

# ============================================================================
# STEP 5: Validate Kustomize Configuration
# ============================================================================
echo ""
echo -e "${YELLOW}Step 4: Validating Kustomize${NC}"
echo "-------------------------------------------"

echo -n "  Testing kustomize build... "
if kubectl kustomize "$K8S_BASE" > /dev/null 2>&1; then
  echo -e "${GREEN}✓${NC}"
else
  echo -e "${RED}✗${NC}"
  echo ""
  echo "Kustomize build failed. Run this to see errors:"
  echo "  kubectl kustomize k8s/base/"
  exit 1
fi

# ============================================================================
# STEP 6: Preview Changes
# ============================================================================
echo ""
echo -e "${YELLOW}Step 5: Preview ConfigMaps${NC}"
echo "-------------------------------------------"
echo "Environment variables (first 10):"
kubectl kustomize "$K8S_BASE" | grep -A 50 "kind: ConfigMap" | grep -A 50 "name: app-env" | grep "  [A-Z]" | head -10
echo "  ..."
echo ""

# ============================================================================
# STEP 7: Deploy to Kubernetes
# ============================================================================
echo ""
echo -e "${YELLOW}Step 6: Deploy to Kubernetes${NC}"
echo "-------------------------------------------"

read -p "Deploy to Kubernetes? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Cancelled."
  exit 0
fi

echo ""
echo "Deploying..."
kubectl apply -k "$K8S_BASE"

echo ""
echo -e "${GREEN}✓ Deployment complete${NC}"

# Restart app if requested
if [[ "$RESTART_APP" == "true" ]]; then
  echo ""
  echo "Restarting app deployment..."
  kubectl rollout restart deployment/app -n api-template-prod
  echo -e "${GREEN}✓ App restarting${NC}"
fi

echo ""
echo "==========================================="
echo "  ✓ Configuration Deployed Successfully"
echo "==========================================="
echo ""
echo "What was synced:"
echo "  • .env → app-env ConfigMap"
echo "  • config.yaml → app-config ConfigMap"
echo "  • PostgreSQL configs → postgres-config ConfigMap"
echo "  • PostgreSQL verifier → postgres-verifier-config ConfigMap"
echo ""
echo "Next time you change config:"
echo "  1. Edit source files (.env, config.yaml, etc.)"
echo "  2. Run: ./k8s/scripts/deploy-config.sh --restart"
echo ""
echo "Or to just sync without deploying:"
echo "  ./k8s/scripts/deploy-config.sh --sync-only"
echo "==========================================="
