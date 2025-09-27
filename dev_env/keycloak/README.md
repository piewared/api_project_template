# Keycloak Development Environment

This directory contains the Keycloak service configuration for the development environment.

## Structure

- `docker-compose.yml` - Keycloak service definition
- `README.md` - This documentation

## Usage

Start Keycloak service:
```bash
docker-compose up -d
```

Stop Keycloak service:
```bash
docker-compose down
```

View logs:
```bash
docker-compose logs -f keycloak
```

## Access

- **Admin Console**: http://localhost:8080/admin
- **Default Credentials**: admin/admin

## Data Persistence

Keycloak data is stored in a Docker named volume `keycloak_data`:
- ✅ **Persistent**: Survives container restarts and updates
- ✅ **Git-safe**: No risk of committing database files to repository
- ✅ **Managed**: Docker handles permissions and optimization

**Manage data volume:**
```bash
# View volume
docker volume inspect keycloak_data

# Backup data
docker run --rm -v keycloak_data:/data -v $(pwd):/backup alpine tar czf /backup/keycloak-backup.tar.gz -C /data .

# Remove data volume (destructive!)
docker volume rm keycloak_data
```

## Configuration

The Keycloak service is configured with:
- Admin user: `admin` / `admin`
- Development mode enabled
- HTTP port: 8080
- Named volume for data persistence