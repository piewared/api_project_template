#!/bin/bash
set -eu

# Required env (provided by your entrypoint/compose)
: "${APP_DB:?missing APP_DB}"
: "${APP_DB_USER:?missing APP_DB_USER}"

echo "==> Initializing db ${APP_DB} for user ${APP_DB_USER}"

psql -v ON_ERROR_STOP=1  -v APP_DB="${APP_DB}" -v APP_DB_USER="${APP_DB_USER}" <<'PSQL'
\set ON_ERROR_STOP on

\echo === Creating roles and database for :'APP_DB' ===

-- App: NOLOGIN owner (ownership container / default privileges anchor)
SELECT format('CREATE ROLE %I NOLOGIN', :'APP_DB_USER')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'APP_DB_USER')\gexec

-- App: database owned by NOLOGIN owner
SELECT format('CREATE DATABASE %I OWNER %I', :'APP_DB', :'APP_DB_USER')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'APP_DB')\gexec


PSQL

echo "==> Init completed"


