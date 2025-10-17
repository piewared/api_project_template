#!/bin/sh
set -eu

APP_DB="${APP_DB:-${APP_DB:-appdb}}"
APP_USER="${APP_USER:-${APP_USER:-appuser}}"
APP_MIGRATION="${APP_MIGRATION:-${APP_MIGRATION:-backupuser}}"
APP_SCHEMA="${APP_SCHEMA:-app}"

# superuser psql (socket); add -h 127.0.0.1 if needed
PSQL_SUPER="psql -v ON_ERROR_STOP=1 -U postgres"
PSQL_APP="$PSQL_SUPER -d $APP_DB"

ok(){ printf "✅ %s\n" "$*"; }
bad(){ printf "❌ %s\n" "$*"; failed=1; }

failed=0

# helper: run psql -c with one inline \set
pset() {
  var="$1"; val="$2"; shift 2
  # delim newlines so \set is in the same session as the query
  $PSQL_SUPER -At -c "$(printf "\\set %s '%s'\n%s" "$var" "$val" "$*")"
}

# ---- roles LOGIN ----
pset r "$APP_USER"      "SELECT rolcanlogin FROM pg_authid WHERE rolname = :'r';" | grep -qx t \
  && ok "Role $APP_USER has LOGIN" || bad "Role $APP_USER missing LOGIN"

pset r "$APP_MIGRATION" "SELECT rolcanlogin FROM pg_authid WHERE rolname = :'r';" | grep -qx t \
  && ok "Role $APP_MIGRATION has LOGIN" || bad "Role $APP_MIGRATION missing LOGIN"

# ---- database owner ----
db_owner="$(pset db "$APP_DB" "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = :'db';" || true)"
[ -z "$db_owner" ] && bad "Database $APP_DB does not exist" || {
  [ "$db_owner" = "$APP_USER" ] && ok "Database $APP_DB owner is $APP_USER" \
                                 || bad "Database $APP_DB owner is '$db_owner' (expected $APP_USER)"
}

# ---- schema owner (in app DB) ----
schema_owner="$($PSQL_APP -At -c "$(printf "\\set s '%s'\n%s" "$APP_SCHEMA" \
"SELECT r.rolname
 FROM pg_namespace n JOIN pg_roles r ON r.oid = n.nspowner
 WHERE n.nspname = :'s';")" || true)"

[ -z "$schema_owner" ] && bad "Schema $APP_SCHEMA does not exist in $APP_DB" || {
  [ "$schema_owner" = "$APP_USER" ] && ok "Schema $APP_SCHEMA owner is $APP_USER" \
                                     || bad "Schema $APP_SCHEMA owner is '$schema_owner' (expected $APP_USER)"
}

# ---- schema privileges ----
for who in "$APP_MIGRATION:USAGE" "$APP_MIGRATION:CREATE" "$APP_USER:USAGE"; do
  role="${who%:*}"; priv="${who#*:}"
  $PSQL_APP -At -c "$(printf "\\set r '%s'\n\\set s '%s'\n\\set p '%s'\nSELECT has_schema_privilege(:'r', :'s', :'p');" "$role" "$APP_SCHEMA" "$priv")" \
    | grep -qx t \
    && ok "$role has $priv on $APP_SCHEMA" \
    || bad "$role missing $priv on $APP_SCHEMA"
done

# ---- DML on existing tables ----
missing_tbls="$($PSQL_APP -At -c "$(printf "\\set s '%s'\n\\set u '%s'\n%s" "$APP_SCHEMA" "$APP_USER" \
"WITH t AS (
   SELECT quote_ident(n.nspname)||'.'||quote_ident(c.relname) AS fq
   FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = :'s' AND c.relkind IN ('r','p')
 ),
 missing AS (
   SELECT fq FROM t
   WHERE NOT has_table_privilege(:'u', fq, 'SELECT')
      OR NOT has_table_privilege(:'u', fq, 'INSERT')
      OR NOT has_table_privilege(:'u', fq, 'UPDATE')
      OR NOT has_table_privilege(:'u', fq, 'DELETE')
 )
 SELECT COALESCE(string_agg(fq, ', '), '') FROM missing;")" || true)"

[ -z "$missing_tbls" ] \
  && ok "$APP_USER has DML on all tables in $APP_SCHEMA" \
  || bad "$APP_USER missing DML on: $missing_tbls"

# ---- sequences ----
missing_seqs="$($PSQL_APP -At -c "$(printf "\\set s '%s'\n\\set u '%s'\n%s" "$APP_SCHEMA" "$APP_USER" \
"WITH seqs AS (
   SELECT quote_ident(n.nspname)||'.'||quote_ident(c.relname) AS fq
   FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname = :'s' AND c.relkind = 'S'
 ),
 missing AS (
   SELECT fq FROM seqs
   WHERE NOT has_sequence_privilege(:'u', fq, 'USAGE')
      OR NOT has_sequence_privilege(:'u', fq, 'SELECT')
 )
 SELECT COALESCE(string_agg(fq, ', '), '') FROM missing;")" || true)"

[ -z "$missing_seqs" ] \
  && ok "$APP_USER has USAGE,SELECT on all sequences in $APP_SCHEMA" \
  || bad "$APP_USER missing sequence privs on: $missing_seqs"

# ---- summary ----
[ "${failed:-0}" -eq 0 ] && { echo "✅ Verification passed"; exit 0; } \
                         || { echo "❌ Verification failed"; exit 1; }
