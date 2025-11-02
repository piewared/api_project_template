#!/bin/bash
# Quick setup script for production app service

set -e

echo "🚀 Setting up FastAPI App Service for Production"
echo "================================================"
echo ""

# Step 1: Generate secrets
echo "📝 Step 1: Generating secrets..."
if [ ! -f infra/secrets/keys/session_signing_secret.txt ] || [ ! -f infra/secrets/keys/csrf_signing_secret.txt ]; then
    cd infra/secrets
    ./generate_secrets.sh
    cd ../..
    echo "✅ Secrets generated"
else
    echo "✅ Secrets already exist"
fi
echo ""

# Step 2: Create log directory
echo "📁 Step 2: Creating log directory..."
mkdir -p data/app-logs
# Try to set permissions, but don't fail if we can't (e.g., if Docker owns it)
chmod 755 data/app-logs 2>/dev/null || echo "   Note: Directory already exists with existing permissions"
echo "✅ Log directory ready"
echo ""

# Step 3: Check .env file
echo "🔧 Step 3: Checking .env file..."
if [ ! -f .env ]; then
    echo "⚠️  WARNING: .env file not found!"
    echo "Creating .env from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ .env file created from example"
        echo "⚠️  IMPORTANT: Review and update .env with production values!"
    else
        echo "❌ ERROR: .env.example not found. Please create .env manually."
        exit 1
    fi
else
    echo "✅ .env file exists"
fi
echo ""

# Step 4: Verify required secrets exist
echo "🔐 Step 4: Verifying required secrets..."
MISSING_SECRETS=0
for secret in postgres_app_user_pw redis_password session_signing_secret csrf_signing_secret; do
    if [ ! -f "infra/secrets/keys/${secret}.txt" ]; then
        echo "❌ Missing: infra/secrets/keys/${secret}.txt"
        MISSING_SECRETS=1
    else
        echo "✅ Found: ${secret}.txt"
    fi
done

if [ $MISSING_SECRETS -eq 1 ]; then
    echo ""
    echo "⚠️  Some secrets are missing. Run: cd infra/secrets && ./generate_secrets.sh"
    exit 1
fi
echo ""

# Step 5: Build app image
echo "🔨 Step 5: Building app image..."
docker compose -f docker-compose.prod.yml build app
echo "✅ App image built"
echo ""

# Step 6: Start services
echo "🚢 Step 6: Starting services..."
docker compose -f docker-compose.prod.yml up -d
echo "✅ Services started"
echo ""

# Step 7: Wait for health check
echo "🏥 Step 7: Waiting for app to be healthy..."
echo "This may take up to 60 seconds..."
SECONDS=0
MAX_WAIT=90

while [ $SECONDS -lt $MAX_WAIT ]; do
    if docker compose -f docker-compose.prod.yml ps app | grep -q "(healthy)"; then
        echo "✅ App is healthy!"
        break
    fi
    
    if [ $((SECONDS % 10)) -eq 0 ]; then
        echo "   Still waiting... ($SECONDS/$MAX_WAIT seconds)"
    fi
    
    sleep 2
done

if [ $SECONDS -ge $MAX_WAIT ]; then
    echo "⚠️  App health check timed out. Checking logs..."
    docker compose -f docker-compose.prod.yml logs --tail=50 app
    exit 1
fi
echo ""

# Step 8: Test health endpoint
echo "🧪 Step 8: Testing health endpoint..."
sleep 5  # Give it a moment
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Health endpoint responding"
    echo ""
    echo "🎉 SUCCESS! App service is running"
else
    echo "❌ Health endpoint not responding"
    echo "Check logs: docker compose -f docker-compose.prod.yml logs app"
    exit 1
fi
echo ""

# Final status
echo "================================================"
echo "✨ Setup Complete!"
echo "================================================"
echo ""
echo "📊 Service Status:"
docker compose -f docker-compose.prod.yml ps app
echo ""
echo "🌐 Endpoints:"
echo "  - API:         http://localhost:8000"
echo "  - Health:      http://localhost:8000/health"
echo "  - Docs:        http://localhost:8000/docs"
echo "  - Temporal UI: http://localhost:8081"
echo ""
echo "📋 Useful Commands:"
echo "  - View logs:   docker compose -f docker-compose.prod.yml logs -f app"
echo "  - Restart:     docker compose -f docker-compose.prod.yml restart app"
echo "  - Stop:        docker compose -f docker-compose.prod.yml stop app"
echo "  - Shell:       docker compose -f docker-compose.prod.yml exec app sh"
echo ""
echo "📚 Documentation:"
echo "  - Setup Guide: docs/prod/APP_SERVICE_SETUP.md"
echo "  - Changes:     docs/prod/DOCKER_COMPOSE_APP_UPDATE.md"
echo ""
