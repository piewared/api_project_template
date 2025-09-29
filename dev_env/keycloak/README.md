# Keycloak Development Environment

This directory contains the Docker Compose configuration for running Keycloak in development mode with automatic OIDC configuration.

## Features

- **Keycloak 24.0** running in development mode
- **Automatic Configuration**: The setup script runs automatically after Keycloak starts
- **Test Realm**: Creates `test-realm` with OIDC client configuration
- **Test Users**: Creates `testuser1` and `testuser2` with password `password123`
- **Persistent Data**: Keycloak data is stored in a Docker volume

## Usage

### Start Keycloak with Auto-Configuration

```bash
# From the dev_env/keycloak directory
docker-compose up -d

# Or from the project root
cd dev_env/keycloak && docker-compose up -d
```

### OIDC Configuration

The setup automatically creates:

- **Realm**: `test-realm`
- **Client ID**: `test-client`
- **Client Secret**: `test-client-secret`
- **Redirect URI**: `http://localhost:8000/auth/web/callback`

### Environment Variables

The following environment variables are configured for your application:

```bash
OIDC_DEFAULT_CLIENT_ID=test-client
OIDC_DEFAULT_CLIENT_SECRET=test-client-secret
OIDC_DEFAULT_ISSUER=http://localhost:8080/realms/test-realm
OIDC_DEFAULT_AUTHORIZATION_ENDPOINT=http://localhost:8080/realms/test-realm/protocol/openid-connect/auth
OIDC_DEFAULT_TOKEN_ENDPOINT=http://localhost:8080/realms/test-realm/protocol/openid-connect/token
OIDC_DEFAULT_USERINFO_ENDPOINT=http://localhost:8080/realms/test-realm/protocol/openid-connect/userinfo
OIDC_DEFAULT_JWKS_URI=http://localhost:8080/realms/test-realm/protocol/openid-connect/certs
OIDC_DEFAULT_END_SESSION_ENDPOINT=http://localhost:8080/realms/test-realm/protocol/openid-connect/logout
OIDC_DEFAULT_REDIRECT_URI=http://localhost:8000/auth/web/callback
```

### Test Users

Two test users are created automatically:

1. **testuser1**
   - Email: `testuser1@example.com`
   - Password: `password123`

2. **testuser2**
   - Email: `testuser2@example.com`
   - Password: `password123`

## Manual Setup

If the automatic setup fails, you can run it manually:

```bash
# From the project root
python src/dev/setup_keycloak.py
```

## Troubleshooting

### Setup Container Fails

If the `keycloak-setup` container fails:

1. Check Keycloak logs: `docker-compose logs keycloak`
2. Check setup logs: `docker-compose logs keycloak-setup`
3. Run manual setup: `python src/dev/setup_keycloak.py`

### Keycloak Won't Start

1. Check if port 8080 is already in use: `lsof -i :8080`
2. Remove existing containers: `docker-compose down -v`
3. Start fresh: `docker-compose up -d`

### Reset Configuration

To reset Keycloak and start fresh:

```bash
docker-compose down -v  # This removes the persistent volume
docker-compose up -d
```

## Files

- `docker-compose.yml`: Main Docker Compose configuration
- `setup_script.py`: Container setup script that runs after Keycloak starts
- `README.md`: This documentation file

The setup script uses the main Keycloak setup module from `../../src/dev/setup_keycloak.py`.

## Configuration

The Keycloak service is configured with:
- Admin user: `admin` / `admin`
- Development mode enabled
- HTTP port: 8080
- Named volume for data persistence