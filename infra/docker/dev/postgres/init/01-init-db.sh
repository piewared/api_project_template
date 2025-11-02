#!/bin/bash
set -eu

# Required env (provided by your entrypoint/compose)
: "${APP_DB:?missing APP_DB}"
: "${APP_DB_USER:?missing APP_DB_USER}"
: "${APP_DB_USER_PW:?missing APP_DB_USER_PW}"

echo "==> Initializing db ${APP_DB} for user ${APP_DB_USER}"

psql -v ON_ERROR_STOP=1  -v APP_DB="${APP_DB}" -v APP_DB_USER="${APP_DB_USER}" -v APP_DB_USER_PW="${APP_DB_USER_PW}" <<'PSQL'
\set ON_ERROR_STOP on

\echo === Creating roles and database for :'APP_DB' ===

-- App: LOGIN user with password
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'APP_DB_USER', :'APP_DB_USER_PW')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'APP_DB_USER')\gexec

-- App: database owned by user
SELECT format('CREATE DATABASE %I OWNER %I', :'APP_DB', :'APP_DB_USER')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'APP_DB')\gexec


PSQL

echo "==> Init completed"


