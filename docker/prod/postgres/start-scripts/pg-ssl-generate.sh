#!/bin/sh
set -eu

SSL_DIR=${POSTGRES_SSL_DIR:-/etc/postgresql/ssl}
CERT=${POSTGRES_SSL_CERT:-$SSL_DIR/server.crt}
KEY=${POSTGRES_SSL_KEY:-$SSL_DIR/server.key}
DAYS=${POSTGRES_SSL_DAYS:-365}
CN=${POSTGRES_SSL_CN:-postgres}
SANS=${POSTGRES_SSL_SANS:-"DNS:localhost,IP:127.0.0.1"}

# If secrets were provided, don't generate
if [ -f "$CERT" ] && [ -f "$KEY" ]; then
  echo "SSL: existing certificate and key found at $CERT / $KEY"
else
  echo "SSL: generating self-signed cert to $SSL_DIR"
  umask 077
  mkdir -p "$SSL_DIR"

  # Create OpenSSL config for SANs
  TMP_CONF=$(mktemp)
  cat >"$TMP_CONF" <<EOF
[req]
default_bits = 4096
prompt = no
default_md = sha256
x509_extensions = v3_req
distinguished_name = dn

[dn]
CN = ${CN}

[v3_req]
subjectAltName = ${SANS}
EOF

  openssl req -new -x509 -nodes -sha256 -days "$DAYS" \
    -out "$CERT" -keyout "$KEY" -config "$TMP_CONF"

  rm -f "$TMP_CONF"
  chmod 600 "$KEY"
  chmod 644 "$CERT"
  chown postgres:postgres "$KEY" "$CERT"
fi
