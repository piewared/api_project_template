# 🚀 FastAPI Production Template

[![Python](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![Lint](https://img.shields.io/badge/lint-Ruff-informational)
![Types](https://img.shields.io/badge/types-MyPy-informational)
![Tests](https://img.shields.io/badge/tests-pytest-success)
![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen)

Build scalable, production-ready REST APIs with built-in **OIDC authentication**, **server-side session management**, and modern **security** (rate limiting, CSRF protection, client fingerprinting).

Develop and test like production with a full **Docker stack** — **PostgreSQL**, **Redis**, **Temporal**, and a **local Keycloak instance for dev/test OIDC flows**.

> In **production**, use a managed IdP (Azure AD, Okta, Auth0, Google, Cognito, etc.).

A **powerful CLI** streamlines your workflow — start/stop the dev environment, manage databases, run the API with hot reload, and generate boilerplate for new domain entities (Entity class, ORM model, repository, and router with pre-generated CRUD endpoints).

---

## Table of Contents

* [Overview](#overview)
* [Key Features](#key-features)
* [Requirements](#requirements)
* [Quick Start](#quick-start)
* [Building Your Service](#building-your-service)
* [Built-in Development Environment](#built-in-development-environment)
* [Configuration](#configuration)
* [Authentication API](#authentication-api)
* [Testing](#testing)
* [Development Workflow](#development-workflow)
* [Troubleshooting](#troubleshooting)
* [Project Structure](#project-structure)
* [Architecture & Design](#architecture--design)
* [License](#license)
* [Support](#support)

---

## Overview

This template provides a complete foundation for building scalable FastAPI applications with:

* 🔐 **OIDC Authentication (BFF)** – Authorization Code + PKCE + nonce, secure sessions, CSRF protection, cookies
* 🏗️ **Clean Architecture** – Entities → Repositories → Services → API layers
* ⚡ **Complete Dev Environment** – Keycloak (dev/test only), PostgreSQL, Redis, Temporal
* 🛠️ **Developer CLI** – Manage env, DB, hot reload, and scaffold entities/routes
* 🔄 **Cruft Updates** – Keep your fork synced with template updates
* 🗄️ **Flexible Database** – PostgreSQL (prod), SQLite (dev/test)
* 📊 **Type-safe ORM** – SQLModel + Pydantic
* 🧪 **Comprehensive Testing** – pytest (unit, integration, E2E)

---

## Key Features

### Authentication & Security
- **BFF pattern** with secure, HttpOnly session cookies
- **OIDC** with multiple providers (Keycloak for dev/test; bring your own IdP for prod)
- **PKCE + nonce + state**; ID token validation with JWKS caching/rotation
- **CSRF protection** for state-changing routes; **origin allowlist**
- **Client fingerprinting** for session binding
- **Rate limiting** with Redis
- Sensible **CORS** and security headers for production

### Development Experience
- **Docker Compose** stack (Keycloak*, PostgreSQL, Redis, Temporal)
- **Zero-manual setup** with pre-seeded dev realm/users in Keycloak
- **Hot reload** dev server
- **Structured logging** with request tracing
- **CLI** for environment + entity codegen

> \* Keycloak is **dev/test only**. In production, configure a managed IdP and point the app to its discovery/issuer URL.

### Architecture & Code Quality
- Clean Architecture layers
- Dependency Injection for testability
- Ruff (format/lint), MyPy (types), pytest (fixtures & E2E)

---

## Requirements

- **Python 3.13+**
- **Docker & Docker Compose**
- **uv** (recommended) or **pip**

---

## Quick Start

**One-liner:**
```bash
pip install -U cruft && cruft create https://github.com/piewared/api_project_template
````

**Full steps:**

```bash
# 1) Create from the template
pip install -U cruft
cruft create https://github.com/piewared/api_project_template

# 2) Configure & run
cd your-project-name
cp .env.example .env
uv run cli dev start-env      # Keycloak (dev), PostgreSQL, Redis, Temporal
uv run init-db
uv run cli dev start-server   # API w/ hot reload
```

**Local URLs**

| Service     | URL                                                      | Notes                       |
| ----------- | -------------------------------------------------------- | --------------------------- |
| API         | [http://localhost:8000](http://localhost:8000)           | Dev server (hot reload)     |
| Docs        | [http://localhost:8000/docs](http://localhost:8000/docs) | OpenAPI/Swagger             |
| Keycloak*   | [http://localhost:8080](http://localhost:8080)           | Dev/test auth (admin/admin) |
| Temporal UI | [http://localhost:8082](http://localhost:8082)           | Workflows                   |

> * In prod, configure a managed IdP and set `issuer`, `client_id`, `audiences`, cookies `Secure=true`, etc.

---

## Building Your Service

Use the CLI to generate domain entities (model, ORM, repository, router with CRUD) and auto-register routes in the app.

```bash
# Create a new entity with interactive field prompts
uv run cli entity add Product

# Manage entities
uv run cli entity ls
uv run cli entity rm Product [--force]
```

What’s generated:

* **Entity** (domain model + validation)
* **Table** (SQLModel)
* **Repository** (CRUD + queries)
* **Router** (CRUD endpoints)
* **Auto-registration** with FastAPI

---

## Built-in Development Environment

**Start here:** **[docs/dev_env/README.md](docs/dev_env/README.md)**

Dockerized services for local dev/test to quickly spin up a local stack that mimics production:

* 🔐 **Keycloak** – OIDC provider with pre-configured dev realm/users (**dev/test only**) → [docs/dev_env/keycloak.md](docs/dev_env/keycloak.md)
* 🗄️ **PostgreSQL** – production-like DB with persistent volume → [docs/dev_env/postgres.md](docs/dev_env/postgres.md)
* ⚡ **Redis** – cache, sessions, rate limiting → [docs/dev_env/redis.md](docs/dev_env/redis.md)
* ⏱️ **Temporal** – workflow engine + UI → [docs/dev_env/temporal.md](docs/dev_env/temporal.md)

Common commands:

```bash
uv run cli dev start-env
uv run cli dev status
uv run cli dev logs [service]
uv run cli dev stop-env
uv run cli dev start-server
```

---

## Configuration

### 🔧 Overview

Configuration is centralized in a single **`config.yaml`**, with environment variable overrides (`${VAR_NAME:-default}` syntax).
This allows clean defaults under version control, while keeping secrets and environment-specific overrides in `.env`.

### ⚙️ Layers

| Layer           | Source                | Description                               |
| --------------- | --------------------- | ----------------------------------------- |
| `.env`          | Environment variables | Environment-specific values               |
| `config.yaml`   | Application config    | Structured defaults with env substitution |
| FastAPI startup | Pydantic models       | Final validation & type safety            |

### 🧭 Structure

Key sections in `config.yaml`:

* `app` → app metadata, session, CORS, and host configuration
* `database` → DB URL, pool size, timeouts
* `redis` → cache/session store config
* `temporal` → background workflows
* `oidc.providers` → multi-provider authentication
* `jwt` → token validation rules & claim mappings
* `rate_limiter` → per-endpoint throttling
* `logging` → log level, structured format

### 🔐 Authentication & Redirects

* The **OIDC `redirect_uri`** (callback) is defined *server-side* per provider in `config.yaml` — never accepted from clients.
* Clients may optionally pass a `return_to` param (relative path or allowlisted host) for post-login redirection.
* The application:

  * Stores state and PKCE verifier securely (e.g., in Redis).
  * Validates `state` and `nonce` on callback.
  * Issues an HttpOnly, `SameSite=Lax` signed session cookie.
  * Rotates session ID and CSRF token on refresh.

### 🍪 Cookie & Security Notes

* `HttpOnly` cookies always (no JS access).
* In **production**, `Secure=true` and HTTPS are mandatory.
* For cross-site frontends, set `SameSite=None` + `Secure=true`.
* Configure `CLIENT_ORIGINS` as a **list** (comma-separated in `.env`).

### 🗝️ Provider Configuration

Prefer discovery:

```yaml
oidc:
  providers:
    keycloak:
      issuer: http://localhost:8080/realms/test-realm
      client_id: test-client
      client_secret: test-secret
      scopes: ["openid", "email", "profile"]
```

For production IdPs (Google, Microsoft, Okta, etc.), set:

* `issuer` to the IdP base URL
* `client_id` / `client_secret` via env vars
* `end_session_endpoint` if your provider supports RP-initiated logout

---

### ⚡️ Example `.env`

```bash
APP_ENVIRONMENT=development
DATABASE_URL=postgresql://appuser:devpass@localhost:5432/appdb
REDIS_URL=redis://localhost:6379/0
BASE_URL=http://localhost:8000
SESSION_SIGNING_SECRET=change-this-32-char-secret
CLIENT_ORIGINS=http://localhost:3000
OIDC_KEYCLOAK_ISSUER=http://localhost:8080/realms/test-realm
OIDC_KEYCLOAK_CLIENT_ID=test-client
OIDC_KEYCLOAK_CLIENT_SECRET=test-secret
```

---

### 🏁 Prod vs Dev Auth

| Environment    | Provider                                          | Redirect URI                              | Security                                        |
| -------------- | ------------------------------------------------- | ----------------------------------------- | ----------------------------------------------- |
| **Dev/Test**   | Local Keycloak                                    | `http://localhost:8000/auth/web/callback` | Self-contained, no internet access              |
| **Production** | Managed IdP (e.g., Azure AD, Okta, Auth0, Google) | `https://your-api.com/auth/web/callback`  | HTTPS required, Secure cookies, rotated secrets |

> ✅ In production:
>
> * Replace Keycloak URLs with your IdP’s `issuer` and `client_id`.
> * Configure OIDC discovery, JWKS validation, and session rotation.
> * Set `Secure=true`, `SameSite=None`, and a strong `SESSION_SIGNING_SECRET`.

---

## Authentication API

All endpoints are under `/auth/web` for web clients using session cookies.

* **`GET /auth/web/login`** – Initiates OIDC login (uses server-configured `redirect_uri`). Accepts `provider` (optional) and sanitized `return_to` (relative path).
* **`GET /auth/web/callback`** – Handles OIDC callback. Validates `state`, `nonce`, tokens (issuer/audience/exp/alg via JWKS). Single-use auth session; sets `user_session_id` cookie; redirects to `return_to` or `/`.
* **`GET /auth/web/me`** – Returns auth state and a CSRF token for subsequent state-changing requests.
* **`POST /auth/web/refresh`** – Refreshes session (rotates session id + CSRF). Requires `X-CSRF-Token` and Origin allowlist.
* **`POST /auth/web/logout`** – Logs out (requires `X-CSRF-Token`); optionally supports RP-initiated logout when provider supports it.

**Client examples:**

* **[docs/clients/javascript.md](docs/clients/javascript.md)**
* **[docs/clients/python.md](docs/clients/python.md)**

---

## Testing

```bash
uv run pytest
uv run pytest --cov=your_package
uv run pytest tests/unit/
uv run pytest tests/integration/
uv run pytest tests/e2e/
```

* **Unit** – business logic
* **Integration** – DB + external services
* **E2E** – full auth + workflows
* **Fixtures** – `tests/fixtures/`

---

## Development Workflow

1. Start Environment: `uv run cli dev start-env`
2. Verify: `uv run cli dev status`
3. Start Server: `uv run cli dev start-server`
4. Access: API/Docs/Keycloak/Temporal via the URLs above

**Adding Features**

* `uv run cli entity add EntityName`
* Add business logic in services/repositories
* Write unit/integration tests
* Update docs

**Debugging**

* `uv run cli dev logs`
* `uv run cli dev logs postgres | keycloak | redis | temporal`

---

## Troubleshooting

**Ports in use**

```bash
sudo netstat -tlnp | grep -E ':8080|:5432'
```

**DB reset**

```bash
uv run cli dev stop-env
docker volume rm dev_env_postgres_data
uv run cli dev start-env
```

**Keycloak (dev)**

```bash
curl http://localhost:8080/realms/test-realm/.well-known/openid-configuration
uv run cli dev logs keycloak
```

**Clean reset**

```bash
uv run cli dev stop-env
docker compose -f dev_env/docker-compose.yml down -v
uv run cli dev start-env
```

**Cookies & cross-site**

* If your frontend runs on a different origin, set `SameSite=None` and ensure HTTPS (`Secure=true`).

---

## Project Structure

```
your_project/
├─ src/
│  └─ your_package/
│     ├─ app/
│     │  ├─ entities/            # Domain entities (CLI generates packages here)
│     │  ├─ api/                 # FastAPI routers
│     │  ├─ core/                # Auth, DB, config, security
│     │  ├─ runtime/             # App runtime
│     │  └─ service/             # Domain services
│     └─ dev/                    # Dev tooling
├─ tests/                        # Unit/integration/E2E
├─ infra/                        # Infrastructure files
│  ├─ docker/                    # Docker configurations (dev/prod)
│  ├─ scripts/                   # Deployment & utility scripts
│  └─ secrets/                   # Secrets management & generation
├─ docs/                         # Additional docs (clients, guides)
└─ dev_env/                      # Dockerized infra + volumes
```

> Deleting volumes will wipe local data (`dev_env/postgres-data/`, etc.).

---

## Architecture & Design

* **Clean Architecture** and **DDD**-inspired layering
* **Entities** (domain) • **Repositories** (data access) • **Services** (business logic) • **API** (FastAPI)
* **Dependency Injection**, **Repository Pattern**
* **Temporal** for reliable, long-running workflows
* **Type safety** end-to-end (Pydantic, SQLModel, MyPy)

---

## License

MIT — see `LICENSE`.

## Support

* Open an issue for bugs/features
* Discussions for Q&A/ideas

---

**Quick create**

```bash
cruft create https://github.com/piewared/api_project_template
```