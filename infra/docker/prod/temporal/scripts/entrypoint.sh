#!/bin/bash

# Read mounted password secret file and export as env variable
if [ -f /run/secrets/postgres_temporal_pw ]; then
    export PW_FILE="/run/secrets/postgres_temporal_pw"
    export POSTGRES_PWD="$(cat /run/secrets/postgres_temporal_pw)"
else
    echo "❌ Password file not found: /run/secrets/postgres_temporal_pw" >&2
    exit 1
fi


echo $POSTGRES_PWD

#exit

# Now call the original entrypoint script
exec /etc/temporal/entrypoint.sh