#!/bin/sh
set -eu

# 1) generate or load certs (idempotent)
#    generator should honor POSTGRES_SSL_* env if you use them
/opt/entry/start-scripts/pg-ssl-generate.sh


# 2) ensure PATH includes postgres binaries
PG_MAJOR="${PG_MAJOR:-15}"
export PATH="/usr/lib/postgresql/${PG_MAJOR}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

# 3) start Postgres with your config files
exec docker-entrypoint.sh postgres \
  -c config_file=/etc/postgresql/postgresql.conf \
  -c hba_file=/etc/postgresql/pg_hba.conf
