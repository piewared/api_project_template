# Temporal Workflow Server

This directory contains Docker configuration for Temporal workflow server, used for orchestrating distributed workflows and activities.

## Services

### Temporal Server
- **Port**: 7233 (gRPC API)
- **Database**: PostgreSQL (dedicated instance)
- **Version**: 1.24.2

### Temporal Web UI
- **Port**: 8088
- **Access**: http://localhost:8088
- **Features**: Workflow monitoring, debugging, and management

### Temporal PostgreSQL
- **Internal service** (not exposed)
- **Database**: `temporal`
- **User**: `temporal`
- **Password**: `temporal`

## Usage

Temporal is automatically started with the development environment:
```bash
uv run cli dev start-dev-env
```

## Access

- **Web UI**: http://localhost:8088
- **gRPC API**: `localhost:7233`
- **CLI**: `tctl --address localhost:7233 namespace list`

## Data Persistence

- **Database**: `api-template-temporal-postgres-data`
- **Config**: `api-template-temporal-data`

## Health Checks

- **PostgreSQL**: `pg_isready` command
- **Temporal Server**: `tctl cluster health` command