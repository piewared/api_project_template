# 🚀 FastAPI Production Template

Build scalable, production-ready REST APIs with built-in **OIDC authentication**, **server-side session management**, and modern **security** (rate limiting, CSRF protection, client fingerprinting).

Develop and test like production with a full **Docker** stack—**PostgreSQL**, **Redis**, **Temporal**, and a **local Keycloak instance for dev/test OIDC flows**.  
> In **production**, use your organization’s managed IdP (e.g., Azure AD, Okta, Auth0, Google, Cognito, or managed Keycloak).

A **powerful CLI** streamlines your workflow: start/stop the dev environment, manage databases, run the API with hot reload, and generate boilerplate for new domain entities (Entity class, ORM model, repository, and router with pre-generated CRUD endpoints).

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Building Your Service](#building-your-service)
- [Built-in Development Environment](#built-in-development-environment)
- [Configuration](#configuration)
- [Authentication API](#authentication-api)
- [Testing](#testing)
- [Development Workflow](#development-workflow)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)
- [Architecture & Design](#architecture--design)
- [License](#license)
- [Support](#support)

---

## Overview

This template provides a complete foundation for building scalable FastAPI applications with:

- 🔐 **OIDC Authentication (BFF)** – Authorization Code + PKCE + nonce, **server-side sessions**, CSRF protection, secure cookies
- 🏗️ **Clean Architecture** – Entities → Repositories → Services → API layers
- ⚡ **Complete Dev Environment** – Keycloak (dev/test only), PostgreSQL, Redis, Temporal via Docker Compose
- 🛠️ **Developer CLI** – Start/stop env, DB tasks, hot-reload server, and **entity/repository/router scaffolding**
- 🔄 **Template Updates** – Keep in sync with **Cruft**
- 🗄️ **Flexible Database** – PostgreSQL (prod), SQLite (dev/test)
- 📊 **Type-safe Modeling** – SQLModel + Pydantic
- 🧪 **Testing Setup** – Unit, integration, and E2E with pytest + fixtures

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
| Temporal UI | [http://localhost:8081](http://localhost:8081)           | Workflows                   |

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

Dockerized services for local dev/test:

* **Keycloak** – OIDC provider with pre-configured dev realm/users (**dev/test only**)
* **PostgreSQL** – production-like DB with persistent volume
* **Redis** – cache, sessions, rate limiting
* **Temporal** – workflow engine + UI

Common commands:

```bash
uv run cli dev start-env
uv run cli dev status
uv run cli dev logs [service]
uv run cli dev stop
uv run cli dev start-server
```

---

## Configuration

Copy `.env.example` → `.env`. Most settings are driven by `config.yaml` with `${ENV_VAR:-default}` substitution.

**Highlights:**

* Use **discovery** (`/.well-known/openid-configuration`) where possible to resolve OIDC endpoints.
* Do **not** accept `redirect_uri` from clients—callback URIs are configured server-side per provider.
* `return_to` (post-login navigation) is sanitized to **relative paths** by default (or allowlisted hosts).
* Cookies: `HttpOnly=true`, `SameSite=Lax` (default), `Secure=true` in production. Cross-site apps require `SameSite=None` + HTTPS.

**Notes:**

* Deduplicate `app:` keys—keep a single `environment`, `host`, `port`, `session_max_age`, `session_signing_secret` (rename from `SESSION_JWT_SECRET` if you prefer clarity).
* Prefer `CLIENT_ORIGINS` as a **list**; parse from a comma-separated env var.

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
uv run cli dev stop
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
uv run cli dev stop
docker-compose -f dev_env/docker-compose.yml down -v
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
├─ dev_env/                      # Dockerized infra + volumes
├─ docs/                         # Additional docs (clients, guides)
└─ scripts/                      # Utilities
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