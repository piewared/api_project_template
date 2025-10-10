#!/bin/bash
# Initialize production database with security hardening

set -e

# Create application database and user
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create extensions
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
    CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
    CREATE EXTENSION IF NOT EXISTS "pgcrypto";
    
    -- Create application schema
    CREATE SCHEMA IF NOT EXISTS app;
    
    -- Set search path
    ALTER DATABASE $POSTGRES_DB SET search_path TO app, public;
    
    -- Create backup user with limited privileges
    CREATE USER backup WITH PASSWORD '$BACKUP_PASSWORD';
    GRANT CONNECT ON DATABASE $POSTGRES_DB TO backup;
    GRANT USAGE ON SCHEMA app TO backup;
    GRANT SELECT ON ALL TABLES IN SCHEMA app TO backup;
    ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT SELECT ON TABLES TO backup;
    
    -- Security: Revoke public schema access
    REVOKE ALL ON SCHEMA public FROM public;
    GRANT USAGE ON SCHEMA public TO $POSTGRES_USER;
EOSQL

echo "Database initialization completed successfully"