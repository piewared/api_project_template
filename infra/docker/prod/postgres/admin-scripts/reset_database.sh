#!/bin/bash
# reset_database.sh - Comprehensive PostgreSQL database reset script
# This script properly cleans up Docker volumes, containers, and local bind mount directories

set -e

echo "🗑️  PostgreSQL Database Reset Script"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="postgres"
COMPOSE_FILE="docker-compose.prod.yml"
DATA_DIR="./data"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if script is run from project root
check_project_root() {
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        print_error "docker-compose.prod.yml not found. Please run this script from the project root directory."
        exit 1
    fi
}

# Function to stop and remove containers
cleanup_containers() {
    print_status "Stopping and removing PostgreSQL containers..."
    
    # Stop PostgreSQL service using docker-compose
    docker-compose -f "$COMPOSE_FILE" stop "$SERVICE_NAME" 2>/dev/null || true
    print_status "PostgreSQL service stopped"
    
    # Remove containers using docker-compose
    docker-compose -f "$COMPOSE_FILE" rm -f "$SERVICE_NAME" 2>/dev/null || true
    print_success "PostgreSQL containers removed"
}

# Function to remove Docker volumes
cleanup_volumes() {
    print_status "Removing Docker volumes..."
    
    # Remove named volumes using docker-compose
    docker-compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true
    
    # Also remove any volumes that might be associated with our container name
    local volumes=$(docker volume ls -q | grep -E "(postgres_data|postgres_backups)" || true)
    if [[ -n "$volumes" ]]; then
        print_status "Removing PostgreSQL volumes: $volumes"
        echo "$volumes" | xargs docker volume rm 2>/dev/null || true
    fi
    
    print_success "Docker volumes cleaned up"
}

# Function to clean up local bind mount directories
cleanup_local_data() {
    print_status "Cleaning up local data directories..."
    
    # Remove PostgreSQL data directory
    if [[ -d "$DATA_DIR/postgres" ]]; then
        print_status "Removing local PostgreSQL data: $DATA_DIR/postgres"
        sudo rm -rf "$DATA_DIR/postgres"
        mkdir -p "$DATA_DIR/postgres"
        print_success "PostgreSQL data directory reset"
    else
        print_status "PostgreSQL data directory not found, creating fresh: $DATA_DIR/postgres"
        mkdir -p "$DATA_DIR/postgres"
    fi
    
    # Remove PostgreSQL backup directory if it exists
    if [[ -d "$DATA_DIR/postgres-backups" ]]; then
        print_status "Removing PostgreSQL backups: $DATA_DIR/postgres-backups"
        sudo rm -rf "$DATA_DIR/postgres-backups"
        mkdir -p "$DATA_DIR/postgres-backups"
        print_success "PostgreSQL backup directory reset"
    else
        print_status "Creating PostgreSQL backup directory: $DATA_DIR/postgres-backups"
        mkdir -p "$DATA_DIR/postgres-backups"
    fi
    
    # Ensure proper ownership (optional, uncomment if needed)
    # sudo chown -R $(id -u):$(id -g) "$DATA_DIR"
}

# Function to clean up networks
cleanup_networks() {
    print_status "Cleaning up Docker networks..."
    
    # Remove project networks if they exist
    docker-compose -f "$COMPOSE_FILE" down --remove-orphans 2>/dev/null || true
    
    print_success "Docker networks cleaned up"
}

# Function to remove Docker images (optional)
cleanup_images() {
    if [[ "$1" == "--remove-images" ]]; then
        print_status "Removing PostgreSQL Docker images..."
        
        # Remove the PostgreSQL container image if it exists
        docker rmi "${CONTAINER_NAME}_postgres" 2>/dev/null || true
        
        # Optionally remove base PostgreSQL images (uncomment if desired)
        # docker rmi postgres:16-alpine 2>/dev/null || true
    fi
}

# Function to verify cleanup
verify_cleanup() {
    print_status "Verifying cleanup..."
    
    # Check for remaining containers
    local containers=$(docker-compose -f "$COMPOSE_FILE" ps -q "$SERVICE_NAME" 2>/dev/null || true)
    if [[ -n "$containers" ]]; then
        print_warning "PostgreSQL container still exists"
    else
        print_success "✓ No PostgreSQL containers found"
    fi
    
    # Check for remaining volumes
    local volumes=$(docker volume ls -q | grep -E "(postgres_data|postgres_backups)" || true)
    if [[ -n "$volumes" ]]; then
        print_warning "Some PostgreSQL volumes still exist: $volumes"
    else
        print_success "✓ No PostgreSQL volumes found"
    fi
    
    # Check local data directories
    if [[ -d "$DATA_DIR/postgres" ]] && [[ -z "$(ls -A "$DATA_DIR/postgres" 2>/dev/null)" ]]; then
        print_success "✓ PostgreSQL data directory is empty"
    elif [[ ! -d "$DATA_DIR/postgres" ]]; then
        print_success "✓ PostgreSQL data directory doesn't exist"
    else
        print_warning "PostgreSQL data directory is not empty"
    fi
}

# Main execution
main() {
    echo
    print_status "Starting PostgreSQL database reset..."
    
    # Parse command line arguments
    local remove_images=false
    for arg in "$@"; do
        case $arg in
            --remove-images)
                remove_images=true
                ;;
            --help|-h)
                echo "Usage: $0 [--remove-images] [--help]"
                echo ""
                echo "Options:"
                echo "  --remove-images    Also remove Docker images"
                echo "  --help, -h         Show this help message"
                echo ""
                echo "This script performs a complete cleanup of PostgreSQL:"
                echo "  - Stops and removes containers"
                echo "  - Removes Docker volumes"
                echo "  - Cleans up local bind mount directories"
                echo "  - Removes Docker networks"
                echo "  - Optionally removes Docker images"
                exit 0
                ;;
        esac
    done
    
    # Check prerequisites
    check_project_root
    
    # Confirm action
    echo
    print_warning "This will completely remove all PostgreSQL data!"
    print_warning "Database contents will be permanently lost."
    echo
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Operation cancelled"
        exit 0
    fi
    
    echo
    print_status "Proceeding with database reset..."
    
    # Execute cleanup steps
    cleanup_containers
    cleanup_volumes
    cleanup_local_data
    cleanup_networks
    
    if [[ "$remove_images" == "true" ]]; then
        cleanup_images --remove-images
    fi
    
    # Verify results
    echo
    verify_cleanup
    
    echo
    print_success "🎉 PostgreSQL database reset completed successfully!"
    echo
    print_status "To start fresh PostgreSQL:"
    print_status "  docker-compose -f $COMPOSE_FILE up postgres"
    echo
}

# Run main function with all arguments
main "$@"