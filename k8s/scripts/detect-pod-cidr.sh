#!/bin/bash
################################################################################
# detect-pod-cidr.sh
# 
# Detects the Kubernetes cluster's pod CIDR and optionally updates .env
#
# Usage:
#   ./k8s/scripts/detect-pod-cidr.sh              # Just print the pod CIDR
#   ./k8s/scripts/detect-pod-cidr.sh --update     # Update .env with detected CIDR
################################################################################

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

UPDATE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --update)
      UPDATE=true
      shift
      ;;
    --help)
      head -n 11 "$0" | tail -n +3
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Run with --help for usage"
      exit 1
      ;;
  esac
done

echo "==========================================="
echo "  Kubernetes Pod CIDR Detection"
echo "==========================================="
echo ""

# Method 1: Try to get from cluster-info dump
echo -e "${BLUE}[1/4]${NC} Checking cluster-info dump..."
POD_CIDR=$(kubectl cluster-info dump 2>/dev/null | grep -m 1 'cluster-cidr' | sed -E 's/.*--cluster-cidr=([0-9./]+).*/\1/' || echo "")

if [[ -n "$POD_CIDR" ]]; then
  echo -e "${GREEN}✓${NC} Found pod CIDR from cluster-info: $POD_CIDR"
else
  echo -e "${YELLOW}⚠${NC} Could not get pod CIDR from cluster-info"
  
  # Method 2: Try to get from node podCIDR
  echo -e "${BLUE}[2/4]${NC} Checking node podCIDR..."
  POD_CIDR=$(kubectl get nodes -o jsonpath='{.items[0].spec.podCIDR}' 2>/dev/null || echo "")
  
  if [[ -n "$POD_CIDR" ]]; then
    echo -e "${GREEN}✓${NC} Found pod CIDR from node spec: $POD_CIDR"
  else
    echo -e "${YELLOW}⚠${NC} Could not get pod CIDR from node spec"
    
    # Method 3: Try to infer from existing pod IPs
    echo -e "${BLUE}[3/4]${NC} Inferring from pod IPs..."
    POD_IP=$(kubectl get pods -A -o jsonpath='{.items[0].status.podIP}' 2>/dev/null || echo "")
    
    if [[ -n "$POD_IP" ]]; then
      # Extract first 2 octets and assume /16
      FIRST_TWO_OCTETS=$(echo "$POD_IP" | cut -d. -f1-2)
      POD_CIDR="${FIRST_TWO_OCTETS}.0.0/16"
      echo -e "${YELLOW}⚠${NC} Inferred pod CIDR from pod IP ($POD_IP): $POD_CIDR"
      echo -e "${YELLOW}  Note: This is an educated guess. Verify with your cluster admin.${NC}"
    else
      echo -e "${RED}✗${NC} Could not infer pod CIDR"
      
      # Method 4: Common defaults
      echo -e "${BLUE}[4/4]${NC} Using common default..."
      POD_CIDR="10.244.0.0/16"
      echo -e "${YELLOW}⚠${NC} Using default pod CIDR: $POD_CIDR"
      echo -e "${YELLOW}  This is Kubernetes' default. May not match your cluster!${NC}"
    fi
  fi
fi

echo ""
echo "==========================================="
echo -e "${GREEN}Detected Pod CIDR: $POD_CIDR${NC}"
echo "==========================================="

# Update .env if requested
if [[ "$UPDATE" == "true" ]]; then
  if [[ ! -f "$ENV_FILE" ]]; then
    echo -e "${RED}✗ Error: .env file not found at: $ENV_FILE${NC}"
    exit 1
  fi
  
  echo ""
  echo "Updating .env file..."
  
  # Check if K8S_POD_CIDR already exists
  if grep -q "^K8S_POD_CIDR=" "$ENV_FILE"; then
    # Update existing value
    sed -i "s|^K8S_POD_CIDR=.*|K8S_POD_CIDR=$POD_CIDR|" "$ENV_FILE"
    echo -e "${GREEN}✓${NC} Updated K8S_POD_CIDR=$POD_CIDR in .env"
  else
    # Add new value
    echo "" >> "$ENV_FILE"
    echo "# Kubernetes Pod Network CIDR (auto-detected)" >> "$ENV_FILE"
    echo "K8S_POD_CIDR=$POD_CIDR" >> "$ENV_FILE"
    echo -e "${GREEN}✓${NC} Added K8S_POD_CIDR=$POD_CIDR to .env"
  fi
  
  echo ""
  echo -e "${YELLOW}Next steps:${NC}"
  echo "  1. Update pg_hba.conf with this CIDR (if not already)"
  echo "  2. Run: ./k8s/scripts/deploy-config.sh --sync-only"
  echo "  3. Run: kubectl apply -k k8s/base/"
  echo "  4. Run: kubectl rollout restart deployment postgres -n api-forge-prod"
fi

echo ""
echo "==========================================="
echo -e "${BLUE}Common Pod CIDRs by Platform:${NC}"
echo "  • Default Kubernetes:  10.244.0.0/16"
echo "  • k3s:                 10.42.0.0/16"
echo "  • Calico:              192.168.0.0/16"
echo "  • Flannel:             10.244.0.0/16"
echo "  • Weave:               10.32.0.0/12"
echo ""
echo "To verify your cluster's pod CIDR:"
echo "  kubectl cluster-info dump | grep -m 1 cluster-cidr"
echo "  kubectl get nodes -o jsonpath='{.items[*].spec.podCIDR}'"
echo "==========================================="
