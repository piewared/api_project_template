#!/bin/bash
# Temporal production entrypoint script with authentication

set -e

echo "Starting Temporal Server in production mode with authentication..."

# Read PostgreSQL password from secret file if provided
if [ -f "$POSTGRES_PWD_FILE" ]; then
    export POSTGRES_PWD=$(cat "$POSTGRES_PWD_FILE")
    echo "PostgreSQL password loaded from secret file: $POSTGRES_PWD_FILE"
elif [ -n "$POSTGRES_PWD" ]; then
    echo "PostgreSQL password loaded from environment variable"
else
    echo "Warning: No PostgreSQL password configured"
fi

# Generate TLS certificates if they don't exist
CERTS_DIR="/etc/temporal/certs"
if [ ! -f "$CERTS_DIR/temporal-server.crt" ]; then
    echo "Generating Temporal TLS certificates..."
    /usr/local/bin/generate-certs.sh
fi

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until pg_isready -h "$POSTGRES_SEEDS" -p "$DB_PORT" -U "$POSTGRES_USER"; do
    echo "PostgreSQL is unavailable - sleeping"
    sleep 2
done
echo "PostgreSQL is ready!"

# Set database connection parameters
export POSTGRES_SEEDS
export POSTGRES_USER
export POSTGRES_TLS_ENABLED="${POSTGRES_TLS_ENABLED:-false}"

# Update config template with actual password
sed -i "s/password: temporal/password: $POSTGRES_PWD/g" /etc/temporal/config/config_template.yaml

# Initialize database schema if needed
if [ "${SKIP_SCHEMA_SETUP:-false}" != "true" ]; then
    echo "Setting up Temporal schema..."
    temporal-sql-tool \
        --plugin postgres \
        --ep "$POSTGRES_SEEDS" \
        --p "$DB_PORT" \
        --u "$POSTGRES_USER" \
        --pw "$POSTGRES_PWD" \
        --db "$POSTGRES_DB" \
        setup-schema -v 0.0
    
    echo "Creating default namespace..."
    temporal-sql-tool \
        --plugin postgres \
        --ep "$POSTGRES_SEEDS" \
        --p "$DB_PORT" \
        --u "$POSTGRES_USER" \
        --pw "$POSTGRES_PWD" \
        --db "$POSTGRES_DB" \
        update-schema -d /etc/temporal/schema/postgresql/v96/temporal/versioned
fi

# Start Temporal server
echo "Starting Temporal server..."
exec temporal-server "$@"