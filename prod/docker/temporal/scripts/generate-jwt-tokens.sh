#!/bin/bash
# Generate JWT tokens for Temporal client authentication

set -e

CERTS_DIR="/etc/temporal/certs"
JWT_PRIVATE_KEY="$CERTS_DIR/temporal-jwt-private.key"

if [ ! -f "$JWT_PRIVATE_KEY" ]; then
    echo "Error: JWT private key not found at $JWT_PRIVATE_KEY"
    echo "Run generate-certs.sh first to create the certificates"
    exit 1
fi

# Function to generate JWT token
generate_jwt_token() {
    local scope="$1"
    local expiry="${2:-3600}"  # Default 1 hour expiry
    
    if [ -z "$scope" ]; then
        echo "Usage: generate_jwt_token <scope> [expiry_seconds]"
        echo "Available scopes: temporal-system, temporal-worker, temporal-client"
        exit 1
    fi
    
    # Create header
    header='{"alg":"RS256","typ":"JWT"}'
    header_b64=$(echo -n "$header" | base64 | tr -d '=' | tr '/+' '_-' | tr -d '\n')
    
    # Create payload
    now=$(date +%s)
    exp=$((now + expiry))
    payload="{\"sub\":\"temporal-user\",\"scope\":\"$scope\",\"iat\":$now,\"exp\":$exp}"
    payload_b64=$(echo -n "$payload" | base64 | tr -d '=' | tr '/+' '_-' | tr -d '\n')
    
    # Create signature
    signature_input="$header_b64.$payload_b64"
    signature=$(echo -n "$signature_input" | openssl dgst -sha256 -sign "$JWT_PRIVATE_KEY" | base64 | tr -d '=' | tr '/+' '_-' | tr -d '\n')
    
    # Create final JWT
    jwt="$header_b64.$payload_b64.$signature"
    echo "$jwt"
}

# Generate tokens for different scopes
echo "Generating JWT tokens for Temporal authentication..."

echo ""
echo "🔑 System Admin Token (temporal-system scope):"
SYSTEM_TOKEN=$(generate_jwt_token "temporal-system" 86400)  # 24 hours
echo "$SYSTEM_TOKEN"

echo ""
echo "👷 Worker Token (temporal-worker scope):"
WORKER_TOKEN=$(generate_jwt_token "temporal-worker" 86400)  # 24 hours
echo "$WORKER_TOKEN"

echo ""
echo "📱 Client Token (temporal-client scope):"
CLIENT_TOKEN=$(generate_jwt_token "temporal-client" 3600)   # 1 hour
echo "$CLIENT_TOKEN"

# Save tokens to files for easy access
echo "$SYSTEM_TOKEN" > "$CERTS_DIR/system-token.jwt"
echo "$WORKER_TOKEN" > "$CERTS_DIR/worker-token.jwt"
echo "$CLIENT_TOKEN" > "$CERTS_DIR/client-token.jwt"

echo ""
echo "✅ JWT tokens generated and saved to:"
echo "   - System token: $CERTS_DIR/system-token.jwt"
echo "   - Worker token: $CERTS_DIR/worker-token.jwt"
echo "   - Client token: $CERTS_DIR/client-token.jwt"

echo ""
echo "💡 Usage examples:"
echo "   # Connect as system admin:"
echo "   temporal workflow list --address temporal:7233 --tls-cert-path $CERTS_DIR/temporal-client.crt --tls-key-path $CERTS_DIR/temporal-client.key --tls-ca-path $CERTS_DIR/ca.crt --auth-plugin jwt --auth-token-file $CERTS_DIR/system-token.jwt"
echo ""
echo "   # In your application:"
echo "   export TEMPORAL_TLS_CERT=$CERTS_DIR/temporal-client.crt"
echo "   export TEMPORAL_TLS_KEY=$CERTS_DIR/temporal-client.key"
echo "   export TEMPORAL_TLS_CA=$CERTS_DIR/ca.crt"
echo "   export TEMPORAL_JWT_TOKEN=\$(cat $CERTS_DIR/client-token.jwt)"