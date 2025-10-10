#!/bin/bash
# Generate TLS certificates for Temporal mTLS authentication

set -e

CERTS_DIR="/etc/temporal/certs"
mkdir -p "$CERTS_DIR"

echo "Generating Temporal TLS certificates..."

# Generate CA private key
openssl genrsa -out "$CERTS_DIR/ca.key" 4096

# Generate CA certificate
openssl req -new -x509 -days 3650 -key "$CERTS_DIR/ca.key" -out "$CERTS_DIR/ca.crt" -subj "/C=US/ST=CA/L=SanFrancisco/O=Temporal/CN=TemporalCA"

# Generate server private key
openssl genrsa -out "$CERTS_DIR/temporal-server.key" 4096

# Generate server certificate signing request
openssl req -new -key "$CERTS_DIR/temporal-server.key" -out "$CERTS_DIR/temporal-server.csr" -subj "/C=US/ST=CA/L=SanFrancisco/O=Temporal/CN=temporal-server"

# Create server certificate extensions
cat > "$CERTS_DIR/server.ext" << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = temporal
DNS.2 = temporal-server
DNS.3 = localhost
IP.1 = 127.0.0.1
EOF

# Generate server certificate
openssl x509 -req -in "$CERTS_DIR/temporal-server.csr" -CA "$CERTS_DIR/ca.crt" -CAkey "$CERTS_DIR/ca.key" -CAcreateserial -out "$CERTS_DIR/temporal-server.crt" -days 365 -extensions v3_req -extfile "$CERTS_DIR/server.ext"

# Generate client private key
openssl genrsa -out "$CERTS_DIR/temporal-client.key" 4096

# Generate client certificate signing request
openssl req -new -key "$CERTS_DIR/temporal-client.key" -out "$CERTS_DIR/temporal-client.csr" -subj "/C=US/ST=CA/L=SanFrancisco/O=Temporal/CN=temporal-client"

# Generate client certificate
openssl x509 -req -in "$CERTS_DIR/temporal-client.csr" -CA "$CERTS_DIR/ca.crt" -CAkey "$CERTS_DIR/ca.key" -CAcreateserial -out "$CERTS_DIR/temporal-client.crt" -days 365

# Generate JWT signing key for authorization
openssl genrsa -out "$CERTS_DIR/temporal-jwt-private.key" 4096
openssl rsa -in "$CERTS_DIR/temporal-jwt-private.key" -pubout -out "$CERTS_DIR/temporal-jwt-public.key"

# Set proper permissions
chmod 600 "$CERTS_DIR"/*.key
chmod 644 "$CERTS_DIR"/*.crt
chmod 644 "$CERTS_DIR"/*.key.pub 2>/dev/null || true

# Clean up CSR files
rm -f "$CERTS_DIR"/*.csr "$CERTS_DIR"/*.ext "$CERTS_DIR"/*.srl

echo "✅ Temporal TLS certificates generated successfully:"
echo "   - CA Certificate: $CERTS_DIR/ca.crt"
echo "   - Server Certificate: $CERTS_DIR/temporal-server.crt"
echo "   - Client Certificate: $CERTS_DIR/temporal-client.crt"
echo "   - JWT Public Key: $CERTS_DIR/temporal-jwt-public.key"

# Display certificate info
echo ""
echo "📋 Certificate Details:"
openssl x509 -in "$CERTS_DIR/temporal-server.crt" -text -noout | grep -A 1 "Subject:"
openssl x509 -in "$CERTS_DIR/temporal-server.crt" -text -noout | grep -A 3 "Subject Alternative Name"