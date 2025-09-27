# Redis Development Service

This directory contains Docker configuration for Redis, used for caching and session storage in development.

## Configuration

- **Port**: 6379
- **Persistence**: Enabled with AOF (Append Only File)
- **Data Volume**: `api-template-redis-data` (persists across container restarts)

## Usage

Redis is automatically started with the development environment:
```bash
uv run cli dev start-dev-env
```

## Access

You can connect to Redis using:
- **Redis CLI**: `docker exec -it dev_env_redis_1 redis-cli`
- **Application**: `redis://localhost:6379`

## Health Check

Redis health is monitored using `redis-cli ping` command.