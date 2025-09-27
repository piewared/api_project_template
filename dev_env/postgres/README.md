# PostgreSQL Development Environment

This directory contains the PostgreSQL service configuration for the development environment.

## Structure

- `docker-compose.yml` - PostgreSQL service definition
- `init/` - Database initialization scripts
- `init/01-init-db.sh` - Initial database setup script

## Usage

Start PostgreSQL service:
```bash
docker-compose up -d
```

Stop PostgreSQL service:
```bash
docker-compose down
```

View logs:
```bash
docker-compose logs -f postgres
```

## Access

- **Host**: localhost
- **Port**: 5432
- **Database**: devdb
- **Username**: devuser
- **Password**: devpass
- **Test Database**: testdb

## Connection String

```
postgresql://devuser:devpass@localhost:5432/devdb
```

## Configuration

The PostgreSQL service is configured with:
- PostgreSQL 16 (Alpine)
- Default database: `devdb`
- Test database: `testdb` (auto-created)
- User: `devuser` / `devpass`
- Data persistence via Docker volume
- Health check enabled
- SCRAM-SHA-256 authentication

## Connecting with psql

```bash
# Connect to main database
psql -h localhost -U devuser -d devdb

# Connect to test database
psql -h localhost -U devuser -d testdb
```