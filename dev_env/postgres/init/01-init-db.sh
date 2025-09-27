#!/bin/bash
set -e

# Create additional databases for testing and development
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create test database
    CREATE DATABASE testdb;
    GRANT ALL PRIVILEGES ON DATABASE testdb TO devuser;

    -- Create any additional schemas or initial data here
    -- Example:
    -- \c devdb;
    -- CREATE SCHEMA IF NOT EXISTS app_schema;
    -- GRANT USAGE ON SCHEMA app_schema TO devuser;
    -- GRANT CREATE ON SCHEMA app_schema TO devuser;
EOSQL

echo "PostgreSQL initialization completed."