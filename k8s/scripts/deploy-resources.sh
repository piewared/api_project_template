#!/bin/bash
# Kubernetes Resource Deployment Script
# This script deploys all Kubernetes resources in the correct order
# Usage: ./deploy-resources.sh [namespace]

set -euo pipefail

# Configuration
NAMESPACE="${1:-api-template-prod}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_BASE="${SCRIPT_DIR}/../base"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    if [ ! -d "${K8S_BASE}" ]; then
        log_error "Kubernetes base directory not found: ${K8S_BASE}"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

check_secrets() {
    log_info "Checking if required secrets exist..."
    
    local secrets=(
        "postgres-secrets"
        "postgres-tls"
        "postgres-ca"
        "redis-secrets"
        "app-secrets"
    )
    
    local missing_secrets=()
    for secret in "${secrets[@]}"; do
        if ! kubectl get secret "${secret}" -n "${NAMESPACE}" &> /dev/null; then
            missing_secrets+=("${secret}")
        fi
    done
    
    if [ ${#missing_secrets[@]} -gt 0 ]; then
        log_error "Missing required secrets: ${missing_secrets[*]}"
        log_error "Please run: ./create-secrets.sh ${NAMESPACE}"
        exit 1
    fi
    
    log_info "All required secrets are present"
}

deploy_namespace() {
    log_step "1/9 - Creating namespace..."
    kubectl apply -f "${K8S_BASE}/namespace/namespace.yaml"
    log_info "✓ Namespace created"
    echo ""
}

deploy_storage() {
    log_step "2/9 - Creating persistent volume claims..."
    kubectl apply -f "${K8S_BASE}/storage/persistentvolumeclaims.yaml"
    log_info "✓ Storage resources created"
    echo ""
}

deploy_configmaps() {
    log_step "3/9 - Creating ConfigMaps..."
    kubectl apply -f "${K8S_BASE}/configmaps/env-config.yaml"
    kubectl apply -f "${K8S_BASE}/configmaps/app-env.yaml"
    kubectl apply -f "${K8S_BASE}/configmaps/app-config.yaml"
    kubectl apply -f "${K8S_BASE}/configmaps/postgres-config.yaml"
    kubectl apply -f "${K8S_BASE}/configmaps/postgres-verifier-config.yaml"
    kubectl apply -f "${K8S_BASE}/configmaps/temporal-config.yaml"
    log_info "✓ ConfigMaps created"
    echo ""
}

deploy_services() {
    log_step "4/9 - Creating Services..."
    kubectl apply -f "${K8S_BASE}/services/services.yaml"
    log_info "✓ Services created"
    echo ""
}

deploy_databases() {
    log_step "5/9 - Deploying databases and caches..."
    kubectl apply -f "${K8S_BASE}/deployments/postgres.yaml"
    kubectl apply -f "${K8S_BASE}/deployments/redis.yaml"
    
    log_info "Waiting for PostgreSQL to be ready..."
    if kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=postgres -n "${NAMESPACE}" --timeout=120s; then
        log_info "✓ PostgreSQL is ready"
    else
        log_error "PostgreSQL failed to become ready"
        exit 1
    fi
    
    log_info "Waiting for Redis to be ready..."
    if kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=redis -n "${NAMESPACE}" --timeout=120s; then
        log_info "✓ Redis is ready"
    else
        log_error "Redis failed to become ready"
        exit 1
    fi
    echo ""
}

deploy_temporal_setup() {
    log_step "6/9 - Initializing Temporal schemas..."
    kubectl apply -f "${K8S_BASE}/jobs/temporal-schema-setup.yaml"
    
    log_info "Waiting for Temporal schema setup to complete (this may take a few minutes)..."
    if kubectl wait --for=condition=complete job/temporal-schema-setup -n "${NAMESPACE}" --timeout=300s; then
        log_info "✓ Temporal schemas initialized"
    else
        log_error "Temporal schema setup failed"
        log_info "Checking job logs..."
        kubectl logs -n "${NAMESPACE}" job/temporal-schema-setup --tail=50
        exit 1
    fi
    echo ""
}

deploy_temporal() {
    log_step "7/9 - Deploying Temporal..."
    kubectl apply -f "${K8S_BASE}/deployments/temporal.yaml"
    kubectl apply -f "${K8S_BASE}/deployments/temporal-web.yaml"
    
    log_info "Waiting for Temporal to be ready..."
    if kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=temporal -n "${NAMESPACE}" --timeout=120s; then
        log_info "✓ Temporal is ready"
    else
        log_error "Temporal failed to become ready"
        log_info "Checking Temporal logs..."
        kubectl logs -n "${NAMESPACE}" -l app.kubernetes.io/name=temporal --tail=50
        exit 1
    fi
    echo ""
}

deploy_app() {
    log_step "8/9 - Deploying application..."
    kubectl apply -f "${K8S_BASE}/deployments/app.yaml"
    
    log_info "Waiting for application to be ready..."
    if kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=app -n "${NAMESPACE}" --timeout=120s; then
        log_info "✓ Application is ready"
    else
        log_error "Application failed to become ready"
        log_info "Checking application logs..."
        kubectl logs -n "${NAMESPACE}" -l app.kubernetes.io/name=app --tail=50
        exit 1
    fi
    echo ""
}

verify_deployment() {
    log_step "9/9 - Verifying deployment..."
    
    echo ""
    log_info "Pod Status:"
    kubectl get pods -n "${NAMESPACE}" -o wide
    
    echo ""
    log_info "Service Status:"
    kubectl get svc -n "${NAMESPACE}"
    
    echo ""
    log_info "Checking application health..."
    
    # Get app pod name
    local app_pod=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=app -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [ -n "${app_pod}" ]; then
        log_info "Checking app logs for health status..."
        if kubectl logs -n "${NAMESPACE}" "${app_pod}" | grep -q "Application startup complete"; then
            log_info "✓ Application started successfully"
            
            # Check for healthy services
            if kubectl logs -n "${NAMESPACE}" "${app_pod}" | grep -q "✓ Database is healthy"; then
                log_info "  ✓ Database is healthy"
            fi
            if kubectl logs -n "${NAMESPACE}" "${app_pod}" | grep -q "✓ Redis is healthy"; then
                log_info "  ✓ Redis is healthy"
            fi
            if kubectl logs -n "${NAMESPACE}" "${app_pod}" | grep -q "✓ Temporal is healthy"; then
                log_info "  ✓ Temporal is healthy"
            fi
        else
            log_warn "Application may not have started properly. Recent logs:"
            kubectl logs -n "${NAMESPACE}" "${app_pod}" --tail=20
        fi
    fi
    echo ""
}

print_next_steps() {
    log_info "=== Deployment Complete ==="
    echo ""
    log_info "Next steps:"
    echo "  1. Access the application:"
    echo "     kubectl port-forward -n ${NAMESPACE} svc/app 8000:8000"
    echo "     curl http://localhost:8000/health"
    echo ""
    echo "  2. Access Temporal Web UI:"
    echo "     kubectl port-forward -n ${NAMESPACE} svc/temporal-web 8080:8080"
    echo "     open http://localhost:8080"
    echo ""
    echo "  3. View logs:"
    echo "     kubectl logs -n ${NAMESPACE} -l app.kubernetes.io/name=app -f"
    echo ""
    echo "  4. Check pod status:"
    echo "     kubectl get pods -n ${NAMESPACE}"
    echo ""
}

main() {
    log_info "Starting Kubernetes resource deployment to namespace: ${NAMESPACE}"
    log_info "Kubernetes base directory: ${K8S_BASE}"
    echo ""
    
    check_prerequisites
    check_secrets
    
    echo ""
    deploy_namespace
    deploy_storage
    deploy_configmaps
    deploy_services
    deploy_databases
    deploy_temporal_setup
    deploy_temporal
    deploy_app
    verify_deployment
    
    echo ""
    log_info "✓✓✓ Deployment completed successfully! ✓✓✓"
    echo ""
    print_next_steps
}

# Run main function
main
