#!/usr/bin/env sh
set -euo pipefail

# ---- Required env ----
: "${TEMPORAL_DB:?missing DB (database name, e.g. temporal)}"
: "${TEMPORAL_VIS_DB:?missing DB (database name, e.g. temporal_visibility)}"
: "${TEMPORAL_DB_USER:?missing PG_USER (e.g. temporal_user)}"
: "${PW_FILE:?missing PW_FILE (password file for temporal user)}"
: "${EP:?missing EP (Postgres host, e.g. postgres)}"


# Optional env
PG_PORT="${PG_PORT:-5432}"
PLUGIN="${PLUGIN:-postgres12}"    # postgres12 for PG >= 12, use postgres for older

# Read password securely from Docker secret
PGPASSWORD="$(cat "$PW_FILE")"
export PGPASSWORD


# TLS (defaults; override via env if needed)
SSL_MODE="${SSL_MODE:-verify-ca}"                         # or 'require' / 'verify-full'
TLS_ENABLE="${TLS_ENABLE:-true}"
TLS_CA_FILE="${TLS_CA_FILE:-/run/secrets/postgres_server_ca}"
TLS_SERVER_NAME="${TLS_SERVER_NAME:-postgres}"  # MUST match a SAN in the server cert

export PGSSLMODE="${SSL_MODE:-verify-ca}"

# Helper wrapper
run_sql_tool () {
  local DB="$1"   # temporal | temporal_visibility
  local action="$2"          # setup-schema ... | update-schema ...

  echo "Running temporal-sql-tool on DB '$1' with action '$2' with user '$TEMPORAL_DB_USER'"
  echo "DB=$DB host=$EP port=$PG_PORT user=$TEMPORAL_DB_USER"

  temporal-sql-tool \
    --plugin "$PLUGIN" \
    --ep "$EP" -p "$PG_PORT" \
    -u "$TEMPORAL_DB_USER" -pw "$PGPASSWORD" \
    --db "$DB" \
    --tls="$TLS_ENABLE" \
    --tls-ca-file "$TLS_CA_FILE" \
    --tls-server-name "$TLS_SERVER_NAME" \
    $action
}
echo "== Temporal schema setup =="
echo "Main schema=$TEMPORAL_DB, Visibility schema=$TEMPORAL_VIS_DB"

# --- Main store ---
echo "--> Creating/updating main store in schema: $TEMPORAL_DB"
run_sql_tool "$TEMPORAL_DB" "setup-schema -v 0.0" || true
run_sql_tool "$TEMPORAL_DB" "update-schema --schema-name postgresql/v12/temporal"

# --- Visibility store ---
echo "--> Creating/updating visibility store in schema: $TEMPORAL_VIS_DB"
run_sql_tool "$TEMPORAL_VIS_DB" "setup-schema -v 0.0" || true
run_sql_tool "$TEMPORAL_VIS_DB" "update-schema --schema-name postgresql/v12/visibility"


echo "== Temporal schema setup complete =="
