#!/bin/bash
# Custom entrypoint for PostgreSQL with security configurations

set -e

# Function to apply custom configurations
apply_custom_configs() {
    echo "Applying custom PostgreSQL configurations..."
    
    # Set PGDATA if not already set
    if [ -z "$PGDATA" ]; then
        export PGDATA=/var/lib/postgresql/data
    fi
    
    # Wait for data directory to be initialized
    while [ ! -f "$PGDATA/PG_VERSION" ]; do
        echo "Waiting for PostgreSQL data directory to be initialized..."
        sleep 2
    done
    
    # Apply custom configurations if they exist
    if [ -f /tmp/postgresql.conf ]; then
        cp /tmp/postgresql.conf "$PGDATA/postgresql.conf"
        echo "Applied custom postgresql.conf"
    fi

    if [ -f /tmp/pg_hba.conf ]; then
        cp /tmp/pg_hba.conf "$PGDATA/pg_hba.conf"
        echo "Applied custom pg_hba.conf"
    fi

    # Generate SSL certificates if not provided
    if [ ! -f "$PGDATA/server.crt" ]; then
        echo "Generating self-signed SSL certificates..."
        openssl req -new -x509 -days 365 -nodes -text \
            -out "$PGDATA/server.crt" \
            -keyout "$PGDATA/server.key" \
            -subj "/CN=postgres"
        
        # Set proper permissions
        chmod 600 "$PGDATA/server.key"
        chmod 644 "$PGDATA/server.crt"
        chown postgres:postgres "$PGDATA/server.key" "$PGDATA/server.crt"
        echo "SSL certificates generated"
    fi
}

# If this is the first argument is postgres, apply configurations in background
if [ "$1" = 'postgres' ]; then
    # Apply configurations in background after PostgreSQL starts
    (
        sleep 5
        apply_custom_configs
    ) &
fi

# Call the original PostgreSQL entrypoint
exec /usr/local/bin/docker-entrypoint.sh "$@"