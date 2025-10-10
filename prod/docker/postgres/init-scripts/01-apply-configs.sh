#!/bin/bash
# PostgreSQL initialization script for custom configurations

set -e

echo "Applying custom PostgreSQL configurations..."

# Apply custom postgresql.conf
if [ -f /tmp/postgresql.conf ]; then
    cp /tmp/postgresql.conf "$PGDATA/postgresql.conf"
    echo "Applied custom postgresql.conf"
fi

# Apply custom pg_hba.conf
if [ -f /tmp/pg_hba.conf ]; then
    cp /tmp/pg_hba.conf "$PGDATA/pg_hba.conf"
    echo "Applied custom pg_hba.conf"
fi

# Generate SSL certificates
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

echo "PostgreSQL custom configuration complete"