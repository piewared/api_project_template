# Development Environment

This directory contains the development environment setup with separate services for authentication and database.

## Structure

```
dev_env/
├── docker-compose.yml       # Main orchestration file
├── setup_dev.sh            # Environment setup script
├── cleanup_dev.sh          # Environment cleanup script
├── keycloak/               # Keycloak OIDC service
│   ├── docker-compose.yml
│   ├── keycloak-data/      # Persistent data
│   └── README.md
└── postgres/               # PostgreSQL database service
    ├── docker-compose.yml
    ├── init/               # DB initialization scripts
    └── README.md
```

## Quick Start

1. **Start the development environment:**
   ```bash
   ./setup_dev.sh
   ```

2. **Access services:**
   - **Keycloak Admin**: http://localhost:8080 (admin/admin)
   - **PostgreSQL**: localhost:5432 (devuser/devpass)

3. **Stop the development environment:**
   ```bash
   ./cleanup_dev.sh
   ```

4. **Stop and remove all data:**
   ```bash
   ./cleanup_dev.sh --remove-data
   ```

## Services

### Keycloak (Authentication)
- **Port**: 8080
- **Admin Console**: http://localhost:8080
- **Credentials**: admin/admin
- **Data**: Stored in Docker named volume `keycloak_data`

### PostgreSQL (Database)  
- **Port**: 5432
- **Host**: localhost
- **Databases**: `devdb` (main), `testdb` (testing)
- **Credentials**: devuser/devpass
- **Connection**: `postgresql://devuser:devpass@localhost:5432/devdb`
- **Data**: Stored in Docker named volume `postgres_data`

## Data Persistence Strategy

This development environment uses **Docker named volumes** for data persistence:

### Why Named Volumes?
- ✅ **Platform agnostic**: Works consistently across Linux, macOS, Windows
- ✅ **Git-safe**: No risk of accidentally committing database files
- ✅ **Docker-managed**: Automatic permission handling and optimization
- ✅ **Isolated**: Data survives container recreation and updates

### Managing Data

**View volumes:**
```bash
docker volume ls | grep dev-env
```

**Backup data:**
```bash
# Backup PostgreSQL
docker run --rm -v dev-env_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres-backup.tar.gz -C /data .

# Backup Keycloak  
docker run --rm -v dev-env_keycloak_data:/data -v $(pwd):/backup alpine tar czf /backup/keycloak-backup.tar.gz -C /data .
```

**Restore data:**
```bash
# Restore PostgreSQL (stop services first)
docker-compose down
docker run --rm -v dev-env_postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres-backup.tar.gz -C /data
docker-compose up -d
```

**Complete reset:**
```bash
./cleanup_dev.sh --remove-data  # Removes all data volumes
```

## What Gets Configured

The setup script automatically creates:

### Keycloak Realm: `test-realm`
- **Issuer URL:** `http://localhost:8080/realms/test-realm`
- **Authorization Endpoint:** `http://localhost:8080/realms/test-realm/protocol/openid-connect/auth`
- **Token Endpoint:** `http://localhost:8080/realms/test-realm/protocol/openid-connect/token`
- **Userinfo Endpoint:** `http://localhost:8080/realms/test-realm/protocol/openid-connect/userinfo`
- **JWKS URI:** `http://localhost:8080/realms/test-realm/protocol/openid-connect/certs`

### OIDC Client: `test-client`
- **Client ID:** `test-client`
- **Client Secret:** `test-client-secret`
- **Redirect URI:** `http://localhost:8000/auth/web/callback`
- **Supported Flows:** Authorization Code with PKCE
- **Allowed Origins:** localhost:8000, localhost:3000, localhost:3001

### Test Users
- **testuser1@example.com** / password: `password123`
- **testuser2@example.com** / password: `password123`

### PostgreSQL Databases
- **devdb** - Main development database
- **testdb** - Testing database  
- **Initialized with**: Basic schema and permissions

## Environment Configuration

Add these variables to your `.env` file:

```bash
# Database Configuration
DATABASE_URL=postgresql://devuser:devpass@localhost:5432/devdb
TEST_DATABASE_URL=postgresql://devuser:devpass@localhost:5432/testdb

# Keycloak OIDC Configuration
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

## Files

- **`docker-compose.yml`** - Docker Compose configuration for Keycloak
- **`setup_dev.sh`** - Main setup script that starts Keycloak and configures it
- **`setup_keycloak.py`** - Python script that configures Keycloak realm, client, and users
- **`cleanup_dev.sh`** - Script to stop and clean up the development environment

## Manual Keycloak Configuration

If you need to manually configure Keycloak:

1. Go to http://localhost:8080
2. Log in with admin/admin
3. Create a new realm called `test-realm`
4. Create a client with:
   - Client ID: `test-client`
   - Client Protocol: `openid-connect`
   - Access Type: `confidential`
   - Standard Flow Enabled: `ON`
   - Valid Redirect URIs: `http://localhost:8000/auth/web/callback`
   - Web Origins: `http://localhost:8000`

## Integration Testing

This environment is designed to work with the integration tests in `tests/integration/`. The tests will automatically use the local Keycloak instance when it's running.

## Troubleshooting

### Keycloak Won't Start
- Make sure Docker is running
- Check if port 8080 is already in use: `lsof -i :8080`
- Try restarting Docker

### Permission Errors
- Make sure the scripts are executable: `chmod +x dev/*.sh`
- On Linux/macOS, you might need to adjust file permissions for the data volume

### Network Issues
- The Docker Compose creates a bridge network for services to communicate
- If you have firewall issues, try temporarily disabling it during development

## Production Notes

⚠️ **This setup is for development only!**

- Uses development mode (`start-dev`) with relaxed security
- Default admin credentials (admin/admin)
- No SSL/TLS encryption
- Data is stored in local volumes that can be easily deleted

For production, use proper Keycloak configuration with:
- Production database (PostgreSQL/MySQL)
- SSL certificates
- Strong admin passwords
- Proper network security
- Regular backups