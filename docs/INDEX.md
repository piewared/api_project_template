# 📚 Documentation Index

Complete guide to the FastAPI Production Template documentation.

## 🚀 Getting Started

| Document | Description |
|----------|-------------|
| **[README.md](../README.md)** | Main project overview, features, and quick start |
| **[CHANGELOG.md](../CHANGELOG.md)** | Version history and notable changes |

---

## 🔧 Development

### Development Environment
- **[Development Environment Overview](dev_env/README.md)** - Complete development setup
- **[Keycloak (OIDC)](dev_env/keycloak.md)** - OAuth/OIDC authentication provider setup
- **[PostgreSQL](dev_env/postgres.md)** - Database configuration and management
- **[Redis](dev_env/redis.md)** - Cache and session store configuration
- **[Temporal](dev_env/temporal.md)** - Workflow orchestration (complete guide)
  - [Development Setup](dev_env/temporal.md#development-setup)
  - [Integration Guide](dev_env/temporal.md#integration-guide)
  - [Usage Patterns](dev_env/temporal.md#usage-patterns)
  - [Production Deployment](dev_env/temporal.md#production-deployment)
  - [Wrapper Design](dev_env/temporal_wrapper_design.md) (Advanced)

### Production Deployment

> **Note**: `temporal_integration_guide.md` and `temporal_usage_guide.md` are deprecated and redirect to the consolidated `temporal.md`.

### Configuration & Security
| Document | Description |
|----------|-------------|
| **[configuration.md](./configuration.md)** | Complete configuration reference |
| **[security.md](./security.md)** | Security model, authentication, CSRF, sessions |

---

## 🏭 Production

### Deployment
| Document | Description |
|----------|-------------|
| **[PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md)** | Complete production deployment guide |
| **[PRODUCTION_STATUS.md](./PRODUCTION_STATUS.md)** | Production infrastructure status summary |

### Production Services
| Document | Description |
|----------|-------------|
| **[prod/postgres.md](./prod/postgres.md)** | Production PostgreSQL with SSL, backups, tuning |
| **[prod/postgres-data-volumes.md](./prod/postgres-data-volumes.md)** | PostgreSQL volume management |
| **[prod/database_production_optimizations.md](./prod/database_production_optimizations.md)** | Database performance tuning |

### Security & Secrets
| Document | Description |
|----------|-------------|
| **[../infra/secrets/README.md](../infra/secrets/README.md)** | 🔐 Secrets generation and management |
| **[security.md](./security.md)** | Security model, authentication, CSRF, sessions |

> **Note**: Temporal authentication is covered in [dev_env/temporal.md#production-deployment](./dev_env/temporal.md#production-deployment)

---

## 🔌 Client Integration

| Document | Description |
|----------|-------------|
| **[clients/javascript.md](./clients/javascript.md)** | JavaScript/TypeScript client examples |
| **[clients/python.md](./clients/python.md)** | Python client examples |

---

## 📋 Quick Reference

### Common Tasks

| Task | Documentation |
|------|---------------|
| **Start development environment** | `uv run cli dev start-env` - See [dev_env/README.md](./dev_env/README.md) |
| **Configure OIDC** | See [security.md](./security.md) and [configuration.md](./configuration.md) |
| **Add Temporal workflows** | See [dev_env/temporal.md#integration-guide](./dev_env/temporal.md#integration-guide) |
| **Deploy to production** | See [PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md) |
| **Manage secrets** | See [infra/secrets/README.md](../infra/secrets/README.md) |
| **Database setup** | Dev: [dev_env/postgres.md](./dev_env/postgres.md), Prod: [prod/postgres.md](./prod/postgres.md) |

### Port Reference (Development)

| Service | Port | URL |
|---------|------|-----|
| FastAPI API | 8000 | http://localhost:8000 |
| Keycloak | 8080 | http://localhost:8080 |
| Temporal UI | 8082 | http://localhost:8082 |
| PostgreSQL | 5433 | localhost:5433 |
| Redis | 6380 | localhost:6380 |

> Production services use standard ports (5432, 6379, 7233)

---

## 🔄 Documentation Updates

### Recent Changes

**November 2024**: Temporal documentation consolidated
- ✅ **`temporal.md`** - Single comprehensive guide
- ⚠️  **`temporal_integration_guide.md`** - Deprecated, redirects to temporal.md
- ⚠️  **`temporal_usage_guide.md`** - Deprecated, redirects to temporal.md

**November 2024**: Production documentation simplified
- ✅ **`PRODUCTION_DEPLOYMENT.md`** - Complete deployment guide
- ✅ **`PRODUCTION_STATUS.md`** - Status summary with links to detailed docs (moved from root)

---

## 📝 Documentation Standards

### File Organization
- **Root level**: Project overview and high-level status
- **`docs/`**: Detailed documentation and guides
- **`docs/dev_env/`**: Development environment specific
- **`docs/prod/`**: Production environment specific
- **`docs/clients/`**: Client integration examples

### Linking Convention
- Use relative links within documentation
- Always provide context for external links
- Cross-reference related documentation
- Mark deprecated files clearly

---

## 🆘 Getting Help

- **Issues**: Check [dev_env/README.md#troubleshooting](./dev_env/README.md)
- **Configuration**: See [configuration.md](./configuration.md)
- **Security**: See [security.md](./security.md)
- **Production**: See [PRODUCTION_DEPLOYMENT.md#troubleshooting](./PRODUCTION_DEPLOYMENT.md)

---

Last updated: November 2024
