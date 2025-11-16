# 🚀 FastAPI Production Template

[![Python](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
![Lint](https://img.shields.io/badge/lint-Ruff-informational)
![Types](https://img.shields.io/badge/types-MyPy-informational)
![Tests](https://img.shields.io/badge/tests-pytest-success)
![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen)

Build scalable, production-ready REST APIs with **FastAPI**, a **BFF-style OIDC session layer**, and a full **Docker dev stack** (PostgreSQL, Redis, Temporal, Keycloak for dev/test).

A **project CLI** lets you start/stop environments, deploy to Docker Compose or Kubernetes, and generate CRUD entities from the domain model.

> In **production**, use a managed IdP (Identity Provider) such as Azure AD, Okta, Auth0, Google, AWS Cognito, etc.

---

## Table of Contents

- [Overview](#overview)
- [Features at a Glance](#features-at-a-glance)
- [Who Is This For?](#who-is-this-for)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Project CLI](#project-cli)
- [Configuration & Auth](#configuration--auth)
- [Development & Testing](#development--testing)
- [Project Structure](#project-structure)
- [More Documentation](#more-documentation)
- [License](#license)
- [Support](#support)

---

## Overview

This template gives you a batteries-included starting point for FastAPI services:

- OIDC-based **backend-for-frontend (BFF)** with secure session cookies
- Clean, layered architecture (entities → repositories → services → API)
- A Dockerized **dev environment** that mirrors production
- A unified **CLI** to run dev/prod/k8s deployments
- First-class **testing**, typing, and linting

---

## Features at a Glance

### Authentication & Security

- **BFF pattern** with HttpOnly session cookies (no tokens in the browser)
- **OIDC** with multiple providers (Keycloak for dev/test; managed IdP for prod)
- **PKCE + nonce + state** with JWKS-based token validation
- **CSRF protection** for state-changing requests (origin allowlist + CSRF token)
- **Client fingerprinting** to bind sessions to user agents
- **Rate limiting** backed by Redis
- Sensible **CORS** and security headers for production

### Development Experience

- **Unified CLI**: `api-forge-cli` for dev, prod (Docker Compose), and k8s
- **Hot reload** dev server with a single command to spin up the full stack
- **Docker Compose stack**: Keycloak (dev/test), PostgreSQL, Redis, Temporal
- Pre-seeded Keycloak realm/users for local auth flows
- Structured logging with request tracing
- Entity code generation: create new CRUD entities with one command

### Architecture & Quality

- Clean Architecture with DDD-inspired layering
- SQLModel + Pydantic for type-safe persistence and validation
- Ruff for lint/format, MyPy for static types, pytest for tests (unit, integration, E2E)

---

## Who Is This For?

This template is a good fit if:

- You’re building a **backend-for-frontend (BFF)** serving web or SPA clients
- You want **OIDC login with server-side sessions** instead of rolling your own
- You care about a **dev environment that looks like production**
- You plan to deploy with **Docker Compose** and/or **Kubernetes**

It may not be ideal if:

- You only need a minimal toy API with no external infra
- You don’t want Docker or external services in your workflow

---

## Requirements

**Core**

- Python **3.13+**
- **Docker** & **Docker Compose**
- **uv** (recommended) or **pip** + virtualenv

**Optional**

- **kubectl** and a cluster (or minikube) for the `k8s` target

---

## Quick Start

### 1. Create a project from the template

```bash
# Using uv (recommended - faster)
uv tool install copier
copier copy gh:piewared/api-forge your-project-name

# Or using pip
pip install -U copier
copier copy https://github.com/piewared/api-forge your-project-name

cd your-project-name
````

### 2. Install dependencies & project

```bash
# Recommended: uv
uv sync

# Or with pip (inside a venv)
# python -m venv .venv
# source .venv/bin/activate  # or .venv\Scripts\activate on Windows
# pip install -e .
```

### 3. Configure environment

```bash
cp .env.example .env
```

### 4. Start the dev stack

```bash
api-forge-cli deploy up dev
# Or, if you prefer not to install the script:
# uv run api-forge-cli deploy up dev
```

Once services are healthy, open:

* API: `http://localhost:8000`
* Docs: `http://localhost:8000/docs`
* Keycloak (dev only): `http://localhost:8080` (admin/admin)
* Temporal UI: `http://localhost:8082`

Keycloak is **dev/test only**. In production, use a managed IdP (see [Configuration & Auth](#configuration--auth)).

### 5. Updating from template (optional)

Copier makes it easy to pull in template updates:

```bash
# Update your project with the latest template changes
copier update

# Or specify a particular version/tag
copier update --vcs-ref=v1.2.3
```

Copier will intelligently merge template changes with your customizations.

---

## Project CLI

When you install the project (via `uv sync` or `pip install -e .`), you get a **project CLI**:

* As a script: `api-forge-cli`
* Or via uv: `uv run api-forge-cli ...`

Common examples:

```bash
# Development environment (Docker Compose + hot reload)
api-forge-cli deploy up dev
api-forge-cli deploy status dev
api-forge-cli deploy down dev

# Production-like stack (Docker Compose)
api-forge-cli deploy up prod
api-forge-cli deploy status prod
api-forge-cli deploy down prod --volumes

# Kubernetes (requires cluster/minikube)
api-forge-cli deploy up k8s
api-forge-cli deploy status k8s
api-forge-cli deploy down k8s
```

### Entity scaffolding

Generate CRUD endpoints and supporting layers for a new domain entity:

```bash
api-forge-cli entity add Product
api-forge-cli entity ls
api-forge-cli entity rm Product --force
```

The generator creates:

* Domain **entity** (validation, invariants)
* SQLModel **table**
* **Repository** (CRUD + queries)
* **Router** (CRUD endpoints) auto-registered with FastAPI

---

## Configuration & Auth

### Config layers

Configuration is centralized in **`config.yaml`** with environment variable substitution (`${VAR_NAME:-default}`):

| Layer         | Description                               |
| ------------- | ----------------------------------------- |
| `.env`        | Environment-specific values               |
| `config.yaml` | Structured defaults with env substitution |
| Startup       | Pydantic models for validation and types  |

Key sections:

* `app` – app metadata, session, CORS, host config
* `database` – DB URL, pool, timeouts
* `redis` – cache and session store
* `temporal` – workflow connection
* `oidc.providers` – OIDC provider definitions
* `jwt` – token validation rules
* `rate_limiter` – per-endpoint throttling
* `logging` – structured logging config

### Auth model (BFF + OIDC)

* Auth uses OIDC **Authorization Code + PKCE** with **server-side sessions**
* The **OIDC `redirect_uri`** is defined **server-side** in `config.yaml`, not taken from clients
* Clients can pass an optional `return_to` parameter (relative path or allowlisted host) for post-login redirect
* The app:

  * stores state and PKCE verifier (e.g. in Redis)
  * validates `state` and `nonce` on callback
  * issues an HttpOnly, signed session cookie
  * rotates session ID and CSRF token on refresh

### Cookies & cross-site usage

* Cookies are always **HttpOnly**
* In **production**, require `Secure=true` and HTTPS
* For cross-site frontends, use `SameSite=None` + `Secure=true`
* Configure `CLIENT_ORIGINS` (comma-separated in `.env`) to control allowed origins

### Authentication endpoints

All web auth endpoints live under `/auth/web`:

* `GET /auth/web/login` – start OIDC login (uses server-configured `redirect_uri`)
* `GET /auth/web/callback` – handle OIDC callback, validate tokens, set session cookie
* `GET /auth/web/me` – return auth state and a CSRF token
* `POST /auth/web/refresh` – rotate session and CSRF token
* `POST /auth/web/logout` – invalidate session; supports RP-initiated logout if the IdP does

Client examples:

* [`docs/clients/javascript.md`](docs/clients/javascript.md)
* [`docs/clients/python.md`](docs/clients/python.md)

### Dev vs prod auth

* **Dev/Test**

  * Local Keycloak, pre-seeded realm/users
  * Redirect URI: `http://localhost:8000/auth/web/callback`

* **Production**

  * Managed IdP (Azure AD, Okta, Auth0, Google, etc.)
  * Redirect URI: `https://your-api.com/auth/web/callback`
  * Configure `issuer`, `client_id`, `client_secret`, and JWKS validation
  * Use strong `SESSION_SIGNING_SECRET`, HTTPS, and secure cookies

---

## Development & Testing

### Typical dev loop

1. Start dev stack: `api-forge-cli deploy up dev`
2. Work on entities, services, and routers
3. Run tests
4. Stop dev stack: `api-forge-cli deploy down dev`

### Testing

```bash
# Full test suite
uv run pytest

# With coverage
uv run pytest --cov=your_package

# Targeted suites
uv run pytest tests/unit/
uv run pytest tests/integration/
uv run pytest tests/e2e/
```

* **Unit** – domain logic and small units
* **Integration** – DB + external services
* **E2E** – full auth + workflows (assumes dev stack is running)

### Troubleshooting (high level)

Common checks:

* **Services up?** – `api-forge-cli deploy status dev`
* **Logs** – `docker compose -f docker-compose.dev.yml logs [service]`
* **Ports in use?** – `netstat`/`ss` on `:8000`, `:8080`, `:5432`, etc.

See [`docs/troubleshooting.md`](docs/troubleshooting.md) for detailed commands and Kubernetes-specific tips.

---

## Project Structure

```text
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
├─ tests/                        # Unit, integration, E2E
├─ infra/                        # Infrastructure files
│  ├─ docker/                    # Docker configurations (dev/prod)
│  ├─ scripts/                   # Deployment & utility scripts
│  └─ secrets/                   # Secrets management & generation
├─ docs/                         # Clients, guides, troubleshooting, etc.
└─ dev_env/                      # Dockerized infra + local volumes
```

Deleting volumes in `dev_env/` will wipe local data (e.g. `dev_env/postgres-data/`).

---

## More Documentation

* **Dev environment**: `dev_env/README.md`
* **Keycloak (dev)**: `dev_env/keycloak.md`
* **PostgreSQL**: `dev_env/postgres.md`
* **Redis**: `dev_env/redis.md`
* **Temporal**: `dev_env/temporal.md`
* **Client examples**: `docs/clients/`
* **Troubleshooting**: `docs/troubleshooting.md`

---

## License

MIT — see [`LICENSE`](LICENSE).

---

## Support

* Open an issue for bugs or feature requests
* Use Discussions for Q&A and ideas

---

**Quick create**

```bash
copier copy gh:piewared/api-forge your-project-name
```