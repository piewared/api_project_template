#!/bin/bash
set -e

################################################################################
# deploy-config.sh
# 
# Simple deployment script for Kubernetes configuration
# 
# What it does:
# 1. Validates your .env file exists
# 2. Deploys all resources (including auto-generated ConfigMap from .env)
# 3. Optionally restarts the app to pick up config changes
#
# Usage:
#   ./k8s/scripts/deploy-config.sh [--restart]
#
# Options:
#   --restart    Also restart the app deployment after updating ConfigMap
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
K8S_DIR="$PROJECT_ROOT/k8s"
K8S_BASE="$K8S_DIR/base"
ENV_FILE="$PROJECT_ROOT/.env"
K8S_ENV_FILE="$K8S_BASE/.env.k8s"

RESTART_APP=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --restart)
      RESTART_APP=true
      shift
      ;;
    --help)
      head -n 18 "$0" | tail -n +3
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

echo "================================"
echo "  Kubernetes Config Deployment"
echo "================================"
echo ""

# Validate .env exists
if [[ ! -f "$ENV_FILE" ]]; then
  echo -e "${RED}✗ Error: .env file not found at: $ENV_FILE${NC}"
  echo ""
  echo "Create it from .env.example:"
  echo "  cp .env.example .env"
  echo "  vim .env"
  exit 1
fi

echo -e "${GREEN}✓${NC} Found .env file"

# Copy .env to k8s/base/.env.k8s (kustomize security: files must be in same directory)
echo -n "Copying .env to k8s/base/.env.k8s... "
cp "$ENV_FILE" "$K8S_ENV_FILE"
echo -e "${GREEN}✓${NC}"

# Validate kustomization.yaml has configMapGenerator
if ! grep -q "configMapGenerator:" "$K8S_BASE/kustomization.yaml"; then
  echo -e "${RED}✗ Error: kustomization.yaml missing configMapGenerator section${NC}"
  echo ""
  echo "Your kustomization.yaml should have:"
  echo ""
  echo "  configMapGenerator:"
  echo "    - name: app-env"
  echo "      envs:"
  echo "        - .env.k8s"
  echo "      options:"
  echo "        disableNameSuffixHash: true"
  echo ""
  exit 1
fi

echo -e "${GREEN}✓${NC} ConfigMap generator configured"

# Test kustomize build
echo -n "Testing kustomize build... "
if kubectl kustomize "$K8S_BASE" > /dev/null 2>&1; then
  echo -e "${GREEN}✓${NC}"
else
  echo -e "${RED}✗${NC}"
  echo ""
  echo "Kustomize build failed. Run this to see errors:"
  echo "  kubectl kustomize k8s/base/"
  exit 1
fi

# Show what will be deployed
echo ""
echo "Preview ConfigMap (first 10 vars):"
echo "-----------------------------------"
kubectl kustomize "$K8S_BASE" | grep -A 50 "kind: ConfigMap" | grep -A 50 "name: app-env" | grep "  [A-Z]" | head -10
echo "  ..."
echo ""

# Confirm deployment
read -p "Deploy to Kubernetes? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Cancelled."
  exit 0
fi

# Deploy
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
echo "================================"
echo "Done!"
echo ""
echo "Next time you change config:"
echo "  1. Edit .env"
echo "  2. Run: ./k8s/scripts/deploy-config.sh --restart"
echo "================================"
