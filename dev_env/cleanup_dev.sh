#!/bin/bash

# Development environment cleanup script
# This script stops and removes the Keycloak container and data

set -e

DEV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🧹 Cleaning up development environment..."

cd "$DEV_DIR"

# Stop and remove containers
echo "🛑 Stopping containers..."
docker-compose down

# Remove volumes (optional)
if [ "$1" = "--remove-data" ]; then
    echo "🗑️  Removing persistent data..."
    docker-compose down -v
    rm -rf keycloak-data/
fi

echo "✅ Development environment cleaned up!"
echo ""
echo "To restart the environment:"
echo "  ./setup_dev.sh"