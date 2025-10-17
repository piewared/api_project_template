#!/bin/bash

# Cryptographically Secure Secret Generator
# This script generates secure random secrets for the application

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEYS_DIR="$SCRIPT_DIR/keys"
mkdir -p "$KEYS_DIR"
CERTS_DIR="$SCRIPT_DIR/certs"
mkdir -p "$CERTS_DIR"

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if required tools are available
check_dependencies() {
    local missing_deps=()
    
    if ! command -v openssl >/dev/null 2>&1; then
        missing_deps+=("openssl")
    fi
    
    if ! [ -c /dev/urandom ]; then
        missing_deps+=("/dev/urandom device")
    fi
    
    if [ ${#missing_deps[@]} -ne 0 ]; then
        print_error "Missing required dependencies: ${missing_deps[*]}"
        print_info "Please install missing dependencies and try again"
        exit 1
    fi
}

# Function to generate a secure random string
generate_secure_random() {
    local length="${1:-32}"
    local charset="${2:-base64}"
    
    case "$charset" in
        "base64")
            # Generate base64 encoded string (good for secrets)
            openssl rand -base64 "$length" | tr -d '\n'
            ;;
        "hex")
            # Generate hexadecimal string
            openssl rand -hex "$length" | tr -d '\n'
            ;;
        "alphanumeric")
            # Generate alphanumeric string (A-Z, a-z, 0-9)
            LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$length"
            ;;
        "password")
            # Generate password with special characters
            LC_ALL=C tr -dc 'A-Za-z0-9!@#$%^&*()_+-=[]{}|;:,.<>?' < /dev/urandom | head -c "$length"
            ;;
        *)
            print_error "Unknown charset: $charset"
            exit 1
            ;;
    esac
}

# Function to generate a JWT signing secret (256-bit)
generate_jwt_secret() {
    # Generate 32 bytes (256 bits) for JWT signing
    openssl rand -base64 32 | tr -d '\n'
}

# Function to generate a database password
generate_db_password() {
    # Generate 24-character password with mixed case, numbers, and safe special chars
    LC_ALL=C tr -dc 'A-Za-z0-9!@#$%^&*()_+-=' < /dev/urandom | head -c 24
}

# Function to generate CSRF token secret
generate_csrf_secret() {
    # Generate 32 bytes (256 bits) for CSRF protection
    openssl rand -base64 32 | tr -d '\n'
}

# Function to generate session signing secret
generate_session_secret() {
    # Generate 32 bytes (256 bits) for session signing
    openssl rand -base64 32 | tr -d '\n'
}

# Function to generate backup encryption password
generate_backup_password() {
    # Generate 32-character strong password for backup encryption
    LC_ALL=C tr -dc 'A-Za-z0-9!@#$%^&*()_+-=[]{}' < /dev/urandom | head -c 32
}

# Function to generate OIDC client secret
generate_oidc_secret() {
    # Generate 48-character secret for OIDC providers
    openssl rand -base64 48 | tr -d '\n'
}

# ============================================================================
# PKI Certificate Functions
# ============================================================================

# Function to create certificate directories
create_cert_directories() {
    mkdir -p "$CERTS_DIR"/{postgres,redis,temporal}
    print_info "Created certificate directories"
}

# Function to generate root CA
generate_root_ca() {
    local root_key="$CERTS_DIR/root-ca.key"
    local root_crt="$CERTS_DIR/root-ca.crt"
    
    print_info "Generating Root Certificate Authority..."
    
    # Generate root CA private key (4096-bit for security)
    openssl genrsa -out "$root_key" 4096
    chmod 600 "$root_key"
    
    # Create root CA certificate (valid for 10 years)
    openssl req -new -x509 -days 3650 -key "$root_key" -out "$root_crt" \
        -subj "/C=US/ST=State/L=City/O=Organization/OU=IT Department/CN=Internal Root CA" \
        -config <(cat <<EOF
[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_ca

[req_distinguished_name]

[v3_ca]
basicConstraints = critical, CA:TRUE
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer:always
EOF
)
    
    chmod 644 "$root_crt"
    print_success "Generated Root CA certificate and key"
}

# Function to generate intermediate CA
generate_intermediate_ca() {
    local root_key="$CERTS_DIR/root-ca.key"
    local root_crt="$CERTS_DIR/root-ca.crt"
    local int_key="$CERTS_DIR/intermediate-ca.key"
    local int_csr="$CERTS_DIR/intermediate-ca.csr"
    local int_crt="$CERTS_DIR/intermediate-ca.crt"
    
    print_info "Generating Intermediate Certificate Authority..."
    
    # Generate intermediate CA private key
    openssl genrsa -out "$int_key" 4096
    chmod 600 "$int_key"
    
    # Create intermediate CA certificate signing request
    openssl req -new -key "$int_key" -out "$int_csr" \
        -subj "/C=US/ST=State/L=City/O=Organization/OU=IT Department/CN=Internal Intermediate CA"
    
    # Sign intermediate CA certificate with root CA (valid for 5 years)
    openssl x509 -req -in "$int_csr" -CA "$root_crt" -CAkey "$root_key" \
        -CAcreateserial -out "$int_crt" -days 1825 \
        -extensions v3_intermediate_ca \
        -extfile <(cat <<EOF
[v3_intermediate_ca]
basicConstraints = critical, CA:TRUE, pathlen:0
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer:always
EOF
)
    
    chmod 644 "$int_crt"
    rm -f "$int_csr"  # Clean up CSR
    print_success "Generated Intermediate CA certificate and key"
}

# Function to generate service certificate
generate_service_certificate() {
    local service_name="$1"
    local service_dir="$CERTS_DIR/$service_name"
    local int_key="$CERTS_DIR/intermediate-ca.key"
    local int_crt="$CERTS_DIR/intermediate-ca.crt"
    local srv_key="$service_dir/server.key"
    local srv_csr="$service_dir/server.csr"
    local srv_crt="$service_dir/server.crt"
    
    print_info "Generating certificate for $service_name service..."
    
    # Generate service private key
    openssl genrsa -out "$srv_key" 2048
    chmod 600 "$srv_key"
    
    # Define Subject Alternative Names based on service
    local sans=""
    case "$service_name" in
        "postgres")
            sans="DNS:postgres,DNS:postgres.backend,DNS:app_data_postgres_db,DNS:database,DNS:db,DNS:localhost,DNS:*.fly.dev,DNS:*.internal,IP:127.0.0.1,IP:::1"
            ;;
        "redis")
            sans="DNS:redis,DNS:redis.backend,DNS:cache,DNS:localhost,DNS:*.fly.dev,DNS:*.internal,IP:127.0.0.1,IP:::1"
            ;;
        "temporal")
            sans="DNS:temporal,DNS:temporal.backend,DNS:temporal-server,DNS:workflow,DNS:localhost,DNS:*.fly.dev,DNS:*.internal,IP:127.0.0.1,IP:::1"
            ;;
        *)
            sans="DNS:$service_name,DNS:localhost,DNS:*.fly.dev,DNS:*.internal,IP:127.0.0.1,IP:::1"
            ;;
    esac
    
    # Create certificate signing request
    openssl req -new -key "$srv_key" -out "$srv_csr" \
        -subj "/C=US/ST=State/L=City/O=Organization/OU=IT Department/CN=$service_name.local"
    
    # Sign service certificate with intermediate CA (valid for 1 year)
    openssl x509 -req -in "$srv_csr" -CA "$int_crt" -CAkey "$int_key" \
        -CAcreateserial -out "$srv_crt" -days 365 \
        -extensions v3_service \
        -extfile <(cat <<EOF
[v3_service]
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always,issuer:always
subjectAltName = $sans
EOF
)
    
    chmod 644 "$srv_crt"
    rm -f "$srv_csr"  # Clean up CSR
    print_success "Generated certificate for $service_name service"
}

# Function to create certificate chain file
create_certificate_chain() {
    local service_name="$1"
    local service_dir="$CERTS_DIR/$service_name"
    local chain_file="$service_dir/server-chain.crt"
    local chain_no_root_file="$service_dir/server-chain-no-root.crt"
    local int_crt="$CERTS_DIR/intermediate-ca.crt"
    local root_crt="$CERTS_DIR/root-ca.crt"
    
    # Create full certificate chain (service cert + intermediate CA + root CA)
    # Recommended for internal PKI - self-contained and simpler deployment
    cat "$service_dir/server.crt" "$int_crt" "$root_crt" > "$chain_file"
    chmod 644 "$chain_file"
    print_success "Created full certificate chain for $service_name"
    
    # Create certificate chain without root CA (service cert + intermediate CA only)
    # Industry standard for public CAs - requires root CA in client trust store
    cat "$service_dir/server.crt" "$int_crt" > "$chain_no_root_file"
    chmod 644 "$chain_no_root_file"
    print_success "Created certificate chain without root CA for $service_name"
}

# Function to create CA bundle for client certificate validation
create_ca_bundle() {
    local ca_bundle="$CERTS_DIR/ca-bundle.crt"
    local int_crt="$CERTS_DIR/intermediate-ca.crt"
    local root_crt="$CERTS_DIR/root-ca.crt"
    
    print_info "Creating CA bundle for client certificate validation..."
    
    # Create CA bundle (intermediate CA + root CA) for ssl_ca_file
    cat "$int_crt" "$root_crt" > "$ca_bundle"
    chmod 644 "$ca_bundle"
    print_success "Created CA bundle: certs/ca-bundle.crt"
    print_info "Use this file for PostgreSQL ssl_ca_file parameter"
}

# Function to check if CA certificates exist
ca_certificates_exist() {
    [ -f "$CERTS_DIR/root-ca.crt" ] && [ -f "$CERTS_DIR/root-ca.key" ] && \
    [ -f "$CERTS_DIR/intermediate-ca.crt" ] && [ -f "$CERTS_DIR/intermediate-ca.key" ]
}

# Function to generate all PKI certificates
generate_pki_certificates() {
    local force_ca="$1"
    
    print_info "Starting PKI certificate generation..."
    echo ""
    
    # Create certificate directories
    create_cert_directories
    
    # Check if CA certificates already exist
    if ca_certificates_exist && [ "$force_ca" != "true" ]; then
        print_warning "CA certificates already exist. Use --force-ca to regenerate them."
        print_info "Using existing CA certificates to generate service certificates..."
    else
        if [ "$force_ca" = "true" ] && ca_certificates_exist; then
            print_warning "Force regenerating CA certificates (existing ones will be backed up)"
        fi
        
        # Generate root and intermediate CAs
        generate_root_ca
        generate_intermediate_ca
    fi
    
    # Generate service certificates
    local services=("postgres" "redis" "temporal")
    
    for service in "${services[@]}"; do
        generate_service_certificate "$service"
        create_certificate_chain "$service"
    done
    
    # Create CA bundle for client certificate validation
    create_ca_bundle
    
    echo ""
    print_success "PKI certificate generation complete!"
    print_info "Certificate hierarchy:"
    print_info "  Root CA -> Intermediate CA -> Service Certificates"
    print_info "  Service certificates include comprehensive SANs for Docker and Fly.io"
    print_warning "Keep CA private keys secure and never commit them to version control!"
}

# Function to write secret to file safely
write_secret() {
    local filename="$1"
    local secret="$2"
    local filepath="$SCRIPT_DIR/$filename"
    
    # Create file with restrictive permissions
    touch "$filepath"
    chmod 600 "$filepath"
    
    # Write secret to file
    echo -n "$secret" > "$filepath"
    
    # Verify file was written correctly
    if [ -f "$filepath" ] && [ -s "$filepath" ]; then
        print_success "Generated $filename ($(wc -c < "$filepath") bytes)"
    else
        print_error "Failed to write $filename"
        return 1
    fi
}

# Function to backup existing secrets
backup_existing_secrets() {
    local backup_dir="$SCRIPT_DIR/backup_$(date +%Y%m%d_%H%M%S)"
    local has_existing=false
    
    # Function to backup files from a directory
    backup_directory() {
        local source_dir="$1"
        local dir_name="$(basename "$source_dir")"
        
        if [ -d "$source_dir" ] && [ "$(ls -A "$source_dir" 2>/dev/null)" ]; then
            if [ "$has_existing" = false ]; then
                mkdir -p "$backup_dir"
                print_info "Backing up existing secrets to: $backup_dir"
                has_existing=true
            fi
            
            # Create subdirectory in backup
            mkdir -p "$backup_dir/$dir_name"
            
            # Copy all files from source directory
            for file in "$source_dir"/*; do
                if [ -f "$file" ]; then
                    cp "$file" "$backup_dir/$dir_name/"
                    print_info "Backed up: $dir_name/$(basename "$file")"
                fi
            done
        fi
    }
    
    # Backup keys directory
    backup_directory "$KEYS_DIR"
    
    # Backup certs directory
    backup_directory "$CERTS_DIR"
    
    # Also backup any loose .txt files in the main directory (for backward compatibility)
    for file in "$SCRIPT_DIR"/*.txt; do
        if [ -f "$file" ]; then
            if [ "$has_existing" = false ]; then
                mkdir -p "$backup_dir"
                print_info "Backing up existing secrets to: $backup_dir"
                has_existing=true
            fi
            cp "$file" "$backup_dir/"
            print_info "Backed up: $(basename "$file")"
        fi
    done
    
    if [ "$has_existing" = true ]; then
        print_warning "Existing secrets have been backed up to: $backup_dir"
    fi
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Generate cryptographically secure secrets and PKI certificates for the application"
    echo ""
    echo "Options:"
    echo "  -h, --help           Show this help message"
    echo "  -f, --force          Overwrite existing secrets without backup"
    echo "  -b, --backup-only    Only backup existing secrets, don't generate new ones"
    echo "  -v, --verify         Verify existing secrets meet security requirements"
    echo "  -l, --list           List all secret files and their sizes"
    echo "  -p, --generate-pki   Generate PKI certificates (root CA, intermediate CA, service certs)"
    echo "  --force-ca           Force regeneration of CA certificates (use with caution)"
    echo ""
    echo "Secret files generated:"
    echo "  keys/postgres_password.txt           - PostgreSQL superuser password (if enabled)"
    echo "  keys/postgres_temporal_pw.txt  - PostgreSQL temporal user password"
    echo "  keys/postgres_app_user_pw.txt        - PostgreSQL app user password"
    echo "  keys/postgres_app_ro_pw.txt          - PostgreSQL read-only user password"
    echo "  keys/postgres_app_owner_pw.txt       - PostgreSQL owner user password"
    echo "  keys/redis_password.txt              - Redis cache password"
    echo "  keys/session_signing_secret.txt      - Session token signing key"
    echo "  keys/csrf_signing_secret.txt         - CSRF protection secret"
    echo "  keys/oidc_google_client_secret.txt   - Google OIDC client secret"
    echo "  keys/oidc_microsoft_client_secret.txt - Microsoft OIDC client secret"
    echo "  keys/oidc_keycloak_client_secret.txt - Keycloak OIDC client secret"
    echo ""
    echo "PKI certificates generated (with --generate-pki):"
    echo "  certs/root-ca.crt                    - Root Certificate Authority"
    echo "  certs/root-ca.key                    - Root CA private key"
    echo "  certs/root-ca.srl                    - Root CA serial number tracker"
    echo "  certs/intermediate-ca.crt            - Intermediate Certificate Authority"
    echo "  certs/intermediate-ca.key            - Intermediate CA private key"
    echo "  certs/intermediate-ca.srl            - Intermediate CA serial number tracker"
    echo "  certs/ca-bundle.crt                  - CA bundle for client cert validation (ssl_ca_file)"
    echo "  certs/postgres/server.crt            - PostgreSQL server certificate"
    echo "  certs/postgres/server.key            - PostgreSQL server private key"
    echo "  certs/postgres/server-chain.crt      - PostgreSQL full certificate chain (includes root CA)"
    echo "  certs/postgres/server-chain-no-root.crt - PostgreSQL chain without root CA"
    echo "  certs/redis/server.crt               - Redis server certificate"
    echo "  certs/redis/server.key               - Redis server private key"
    echo "  certs/redis/server-chain.crt         - Redis full certificate chain (includes root CA)"
    echo "  certs/redis/server-chain-no-root.crt - Redis chain without root CA"
    echo "  certs/temporal/server.crt            - Temporal server certificate"
    echo "  certs/temporal/server.key            - Temporal server private key"
    echo "  certs/temporal/server-chain.crt      - Temporal full certificate chain (includes root CA)"
    echo "  certs/temporal/server-chain-no-root.crt - Temporal chain without root CA"
}

# Function to verify existing secrets
verify_secrets() {
    print_info "Verifying existing secrets and certificates..."
    local all_good=true
    
    # Define minimum lengths for each secret type
    declare -A min_lengths=(
        ["keys/postgres_password.txt"]=24
        ["keys/postgres_app_user_pw.txt"]=24
        ["keys/postgres_app_ro_pw.txt"]=24
        ["keys/postgres_app_owner_pw.txt"]=24
        ["keys/redis_password.txt"]=16
        ["keys/postgres_temporal_pw.txt"]=24
        ["keys/session_signing_secret.txt"]=32
        ["keys/csrf_signing_secret.txt"]=32
        ["keys/oidc_google_client_secret.txt"]=32
        ["keys/oidc_microsoft_client_secret.txt"]=32
        ["keys/oidc_keycloak_client_secret.txt"]=32
    )
    
    # Verify secret files
    print_info "Checking secret files..."
    for filename in "${!min_lengths[@]}"; do
        local filepath="$SCRIPT_DIR/$filename"
        local min_len="${min_lengths[$filename]}"
        
        if [ -f "$filepath" ]; then
            local actual_len=$(wc -c < "$filepath")
            local perms=$(stat -c "%a" "$filepath" 2>/dev/null || echo "unknown")
            
            if [ "$actual_len" -ge "$min_len" ]; then
                if [ "$perms" = "600" ]; then
                    print_success "$filename: OK (${actual_len} bytes, permissions: $perms)"
                else
                    print_warning "$filename: Length OK but permissions should be 600 (current: $perms)"
                    chmod 600 "$filepath"
                    print_success "Fixed permissions for $filename"
                fi
            else
                print_error "$filename: Too short (${actual_len} bytes, minimum: ${min_len})"
                all_good=false
            fi
        else
            print_warning "$filename: Missing"
            all_good=false
        fi
    done
    
    # Verify PKI certificates if they exist
    print_info "Checking PKI certificates..."
    if ca_certificates_exist; then
        # Check CA certificates and serial number files
        local ca_files=("certs/root-ca.crt" "certs/root-ca.key" "certs/root-ca.srl" "certs/intermediate-ca.crt" "certs/intermediate-ca.key" "certs/intermediate-ca.srl" "certs/ca-bundle.crt")
        for ca_file in "${ca_files[@]}"; do
            local filepath="$SCRIPT_DIR/$ca_file"
            if [ -f "$filepath" ]; then
                local perms=$(stat -c "%a" "$filepath" 2>/dev/null || echo "unknown")
                if [[ "$ca_file" == *.key ]]; then
                    # Private keys should be 600
                    if [ "$perms" = "600" ]; then
                        print_success "$ca_file: OK (permissions: $perms)"
                    else
                        print_warning "$ca_file: Private key permissions should be 600 (current: $perms)"
                        chmod 600 "$filepath"
                        print_success "Fixed permissions for $ca_file"
                    fi
                elif [[ "$ca_file" == *.srl ]]; then
                    # Serial number files should be 644 (readable for verification)
                    if [ "$perms" = "644" ] || [ "$perms" = "600" ]; then
                        print_success "$ca_file: OK (permissions: $perms, serial: $(cat "$filepath"))"
                    else
                        print_warning "$ca_file: Serial file permissions should be 644 or 600 (current: $perms)"
                        chmod 644 "$filepath"
                        print_success "Fixed permissions for $ca_file"
                    fi
                else
                    # Certificates can be 644
                    if [ "$perms" = "644" ] || [ "$perms" = "600" ]; then
                        print_success "$ca_file: OK (permissions: $perms)"
                    else
                        print_warning "$ca_file: Certificate permissions should be 644 or 600 (current: $perms)"
                        chmod 644 "$filepath"
                        print_success "Fixed permissions for $ca_file"
                    fi
                fi
                
                # Verify certificate validity (not expired)
                if [[ "$ca_file" == *.crt ]]; then
                    if openssl x509 -in "$filepath" -noout -checkend 86400 >/dev/null 2>&1; then
                        print_success "$ca_file: Certificate is valid and not expiring within 24 hours"
                    else
                        print_warning "$ca_file: Certificate is expired or expiring within 24 hours"
                        all_good=false
                    fi
                fi
            else
                print_warning "$ca_file: Missing"
                all_good=false
            fi
        done
        
        # Check service certificates
        local services=("postgres" "redis" "temporal")
        for service in "${services[@]}"; do
            local service_files=("certs/$service/server.crt" "certs/$service/server.key" "certs/$service/server-chain.crt" "certs/$service/server-chain-no-root.crt")
            for service_file in "${service_files[@]}"; do
                local filepath="$SCRIPT_DIR/$service_file"
                if [ -f "$filepath" ]; then
                    local perms=$(stat -c "%a" "$filepath" 2>/dev/null || echo "unknown")
                    if [[ "$service_file" == *.key ]]; then
                        # Private keys should be 600
                        if [ "$perms" = "600" ]; then
                            print_success "$service_file: OK (permissions: $perms)"
                        else
                            print_warning "$service_file: Private key permissions should be 600 (current: $perms)"
                            chmod 600 "$filepath"
                            print_success "Fixed permissions for $service_file"
                        fi
                    else
                        # Certificates can be 644
                        if [ "$perms" = "644" ] || [ "$perms" = "600" ]; then
                            print_success "$service_file: OK (permissions: $perms)"
                        else
                            print_warning "$service_file: Certificate permissions should be 644 or 600 (current: $perms)"
                            chmod 644 "$filepath"
                            print_success "Fixed permissions for $service_file"
                        fi
                    fi
                    
                    # Verify certificate validity for .crt files
                    if [[ "$service_file" == *.crt ]] && [[ "$service_file" != *chain.crt ]]; then
                        if openssl x509 -in "$filepath" -noout -checkend 86400 >/dev/null 2>&1; then
                            print_success "$service_file: Certificate is valid and not expiring within 24 hours"
                        else
                            print_warning "$service_file: Certificate is expired or expiring within 24 hours"
                            all_good=false
                        fi
                    fi
                else
                    print_warning "$service_file: Missing"
                    all_good=false
                fi
            done
        done
    else
        print_info "No PKI certificates found (use --generate-pki to create them)"
    fi
    
    if [ "$all_good" = true ]; then
        print_success "All secrets and certificates verified successfully!"
    else
        print_warning "Some secrets or certificates need attention. Run without --verify to regenerate."
    fi
}

# Function to list secret files
list_secrets() {
    print_info "Secret files in $SCRIPT_DIR:"
    echo ""
    printf "%-45s %10s %10s\n" "File" "Size" "Permissions"
    printf "%-45s %10s %10s\n" "----" "----" "-----------"

    local files_found=false
    
    # List files in keys directory
    if [ -d "$KEYS_DIR" ]; then
        for file in "$KEYS_DIR"/*.txt; do
            if [ -f "$file" ]; then
                local size=$(wc -c < "$file")
                local perms=$(stat -c "%a" "$file" 2>/dev/null || echo "unknown")
                local relative_path="keys/$(basename "$file")"
                printf "%-45s %10s %10s\n" "$relative_path" "${size} bytes" "$perms"
                files_found=true
            fi
        done
    fi
    
    # List files in certs directory (certificates and keys)
    if [ -d "$CERTS_DIR" ]; then
        # List root CA files (including serial number files)
        for file in "$CERTS_DIR"/root-ca.* "$CERTS_DIR"/intermediate-ca.* "$CERTS_DIR"/ca-bundle.crt; do
            if [ -f "$file" ]; then
                local size=$(wc -c < "$file")
                local perms=$(stat -c "%a" "$file" 2>/dev/null || echo "unknown")
                local relative_path="certs/$(basename "$file")"
                printf "%-45s %10s %10s\n" "$relative_path" "${size} bytes" "$perms"
                files_found=true
            fi
        done
        
        # List service certificate files
        for service_dir in "$CERTS_DIR"/*; do
            if [ -d "$service_dir" ]; then
                local service_name=$(basename "$service_dir")
                for file in "$service_dir"/*; do
                    if [ -f "$file" ]; then
                        local size=$(wc -c < "$file")
                        local perms=$(stat -c "%a" "$file" 2>/dev/null || echo "unknown")
                        local relative_path="certs/$service_name/$(basename "$file")"
                        printf "%-45s %10s %10s\n" "$relative_path" "${size} bytes" "$perms"
                        files_found=true
                    fi
                done
            fi
        done
    fi
    
    # Also check for any legacy .txt files in main directory (backward compatibility)
    for file in "$SCRIPT_DIR"/*.txt; do
        if [ -f "$file" ]; then
            local size=$(wc -c < "$file")
            local perms=$(stat -c "%a" "$file" 2>/dev/null || echo "unknown")
            printf "%-45s %10s %10s\n" "$(basename "$file")" "${size} bytes" "$perms"
            files_found=true
        fi
    done
    
    if [ "$files_found" = false ]; then
        print_warning "No secret files found in keys/, certs/, or main directory"
    fi
}

# Function to generate all secrets
generate_all_secrets() {
    print_info "Generating cryptographically secure secrets..."
    echo ""
    
    # Generate all secret files
    write_secret "keys/postgres_password.txt" "$(generate_db_password)"
    write_secret "keys/postgres_app_user_pw.txt" "$(generate_db_password)"
    write_secret "keys/postgres_app_ro_pw.txt" "$(generate_db_password)"
    write_secret "keys/postgres_app_owner_pw.txt" "$(generate_db_password)"
    write_secret "keys/postgres_temporal_pw.txt" "$(generate_db_password)"
    write_secret "keys/redis_password.txt" "$(generate_db_password)"
    write_secret "keys/session_signing_secret.txt" "$(generate_session_secret)"
    write_secret "keys/csrf_signing_secret.txt" "$(generate_csrf_secret)"
    write_secret "keys/oidc_google_client_secret.txt" "$(generate_oidc_secret)"
    write_secret "keys/oidc_microsoft_client_secret.txt" "$(generate_oidc_secret)"
    write_secret "keys/oidc_keycloak_client_secret.txt" "$(generate_oidc_secret)"

    echo ""
    print_success "All secrets generated successfully!"
    print_info "Files are created with 600 permissions (owner read/write only)"
    print_warning "Keep these files secure and never commit them to version control!"
}

# Main function
main() {
    local force=false
    local backup_only=false
    local verify_only=false
    local list_only=false
    local generate_pki=false
    local force_ca=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -f|--force)
                force=true
                shift
                ;;
            -b|--backup-only)
                backup_only=true
                shift
                ;;
            -v|--verify)
                verify_only=true
                shift
                ;;
            -l|--list)
                list_only=true
                shift
                ;;
            -p|--generate-pki)
                generate_pki=true
                shift
                ;;
            --force-ca)
                force_ca=true
                shift
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Change to script directory
    cd "$SCRIPT_DIR"
    
    # Check dependencies
    check_dependencies
    
    # Handle different modes
    if [ "$list_only" = true ]; then
        list_secrets
        exit 0
    fi
    
    if [ "$verify_only" = true ]; then
        verify_secrets
        exit 0
    fi
    
    if [ "$backup_only" = true ]; then
        backup_existing_secrets
        exit 0
    fi
    
    # Handle PKI-only generation
    if [ "$generate_pki" = true ] && [ "$force" = false ]; then
        # Only generate PKI certificates
        if [ "$force_ca" = false ]; then
            backup_existing_secrets
        fi
        generate_pki_certificates "$force_ca"
        echo ""
        print_info "PKI generation complete!"
        print_info "Run '$0 --list' to see all generated files"
        exit 0
    fi
    
    # Backup existing secrets unless force is specified
    if [ "$force" = false ]; then
        backup_existing_secrets
    fi
    
    # Generate new secrets
    generate_all_secrets
    
    # Generate PKI certificates if requested
    if [ "$generate_pki" = true ]; then
        echo ""
        generate_pki_certificates "$force_ca"
    fi
    
    echo ""
    print_info "Secret generation complete!"
    print_info "Run '$0 --verify' to verify the generated secrets"
    print_info "Run '$0 --list' to see all secret files"
    
    if [ "$generate_pki" = true ]; then
        print_info "PKI certificates have been generated with comprehensive SANs"
    fi
}

# Run main function with all arguments
main "$@"