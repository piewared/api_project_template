#!/bin/bash

# Development environment setup script
# This script sets up a local Keycloak instance with test realm and client configuration

set -e

DEV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$DEV_DIR")"

echo "🚀 Setting up development environment..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Create and set permissions for keycloak-data directory
echo "📁 Setting up keycloak data directory..."
mkdir -p "$DEV_DIR/keycloak-data"
# Set ownership to current user
chown -R $(id -u):$(id -g) "$DEV_DIR/keycloak-data"
chmod -R 755 "$DEV_DIR/keycloak-data"

# Start Keycloak
echo "📦 Starting Keycloak container..."
cd "$DEV_DIR"
docker-compose up -d keycloak

# Wait for Keycloak to be ready
echo "⏳ Waiting for Keycloak to be ready..."
timeout=300
counter=0

while ! curl -sf http://localhost:8080/realms/master > /dev/null 2>&1; do
    if [ $counter -ge $timeout ]; then
        echo "❌ Timeout waiting for Keycloak to start"
        exit 1
    fi
    echo "Waiting for Keycloak... ($counter/${timeout}s)"
    sleep 5
    counter=$((counter + 5))
done

echo "✅ Keycloak is ready!"

# Configure Keycloak realm and client
echo "⚙️  Configuring Keycloak realm and client..."
python3 "$DEV_DIR/setup_keycloak.py"

echo ""
echo "🎉 Development environment ready!"
echo ""
echo "Keycloak Admin Console: http://localhost:8080"
echo "  Username: admin"
echo "  Password: admin"
echo ""
echo "Test Realm: test-realm"
echo "Test Client: test-client"
echo "Test Users:"
echo "  - testuser1@example.com / password123"
echo "  - testuser2@example.com / password123"
echo ""
echo "To stop the environment:"
echo "  cd dev && docker-compose down"
echo ""