# 🧱 Development Environment

A complete **Docker-based development stack** that mirrors production to ensure reliable local testing and CI consistency.  
Includes **Keycloak** (for local OIDC), **PostgreSQL**, **Redis**, and **Temporal** with a dedicated Temporal Postgres instance.  
Automated setup scripts and a built-in CLI streamline developer onboarding and environment management.

> **🔌 Port Configuration**: Development services use non-conflicting ports (PostgreSQL: 5433, Redis: 6380) to allow simultaneous operation with production containers.

---

## 📚 Related Documentation

| Service | Description | Documentation                                            |
|----------|--------------|----------------------------------------------------------|
| 🔐 **Keycloak** | Local OIDC identity provider | [docs/dev_env/keycloak.md](./keycloak.md)                |
| 🗄️ **PostgreSQL** | Primary development and test databases | [docs/dev_env/postgres.md](./postgres.md)     |
| ⚡ **Redis** | Session store, cache, and rate limiter backend | [docs/dev_env/redis.md](./redis.md)           |
| ⏱️ **Temporal** | Workflow orchestration engine | [docs/dev_env/temporal.md](./temporal.md)     |
| ⚙️ **Configuration** | Environment variables, ports, and integration notes | [docs/configuration.md](../configuration.md) |
| 🔒 **Security** | Development vs production security configuration | [docs/security.md](../security.md)   |

---

## 📂 Structure

```text
dev_env/
├── docker-compose.yml           # Main orchestration file
├── setup_dev.sh                 # Start environment script
├── cleanup_dev.sh               # Stop/cleanup script
│
├── keycloak/                    # Local OIDC provider
│   ├── docker-compose.yml
│   ├── setup_script.py          # Auto-configures realm, client, users
│   └── keycloak-data/           # Persistent volume
│
├── postgres/                    # PostgreSQL database
│   ├── docker-compose.yml
│   ├── init/                    # SQL init scripts
│   └── README.md
│
├── redis/                       # Redis cache / session store
│   ├── docker-compose.yml
│   └── README.md
│
└── temporal/                    # Temporal workflow engine
    ├── docker-compose.yml
    └── README.md
````

---

## ⚙️ Quick Start

### Start the environment

```bash
uv run cli dev start-env
```

This command launches all dependent services (PostgreSQL, Redis, Keycloak, and Temporal)
and automatically runs **Keycloak setup** after the service becomes healthy.

To stop everything:

```bash
uv run cli dev stop-env
```

To stop and **remove all volumes** (clean slate):

```bash
uv run cli dev reset-env
```

---

## 🌐 Access Services

| Service             | Purpose             | Host Access                                    | In-Network Hostname      |
| ------------------- | ------------------- | ---------------------------------------------- | ------------------------ |
| **API**             | FastAPI app         | [http://localhost:8000](http://localhost:8000) | `api` (if containerized) |
| **Keycloak**        | Local OIDC provider | [http://localhost:8080](http://localhost:8080) | `keycloak:8080`          |
| **PostgreSQL**      | Primary DB          | localhost:5433                                 | `postgres:5432`          |
| **Redis**           | Caching / sessions  | localhost:6380                                 | `redis:6379`             |
| **Temporal Server** | Workflow RPC        | localhost:7233                                 | `temporal-server:7233`   |
| **Temporal UI**     | Workflow dashboard  | [http://localhost:8081](http://localhost:8081) | `temporal-web:8080`      |

---

## 🧩 Service Summaries

### 🔐 [Keycloak (Local OIDC Provider)](../docs/dev_env/keycloak.md)

A **local Keycloak** instance provides OIDC authentication for development and integration tests.
Automatically configures:

* Realm: `test-realm`
* Client: `test-client`
* Users: `testuser1` / `testuser2` with password `password123`

⚠️ *Intended for development only.*
Production should use an external IdP (Auth0, Okta, Azure AD, or managed Keycloak).

---

### 🗄️ [PostgreSQL (Database)](../docs/dev_env/postgres.md)

Primary relational database for development and tests.

* Databases: `appdb`
* Credentials: `appuser / devpass`
* Connection:
  `postgresql://appuser:devpass@localhost:5433/appdb`

---

### ⚡ [Redis (Cache & Rate Limiting)](../docs/dev_env/redis.md)

In-memory data store used for:

* Session management
* Caching
* Rate limiting
* Temporary OIDC/session tokens

Runs in persistent mode (AOF enabled) using `redis_data` volume.

---

### ⏱️ [Temporal (Workflows & Background Jobs)](../docs/dev_env/temporal.md)

Temporal handles distributed workflows, background processing, and task orchestration.
Includes:

* Temporal server (port 7233)
* Temporal Web UI (port 8081)
* Dedicated PostgreSQL backend

CORS origins default to:
`TEMPORAL_CORS_ORIGINS=http://localhost:3000`

---

## 💾 Data Persistence

All service data is stored in **Docker named volumes** for isolation and persistence.

| Service      | Volume                   | Description             |
| ------------ | ------------------------ | ----------------------- |
| Keycloak     | `keycloak_data`          | Realm & user data       |
| PostgreSQL   | `postgres_data`          | Application database    |
| Redis        | `redis_data`             | Cache/session store     |
| Temporal     | `temporal_postgres_data` | Workflow metadata       |
| *(optional)* | `temporal_data`          | Reserved for future use |

View all volumes:

```bash
docker volume ls | grep dev_env
```

Reset all volumes:

```bash
./cleanup_dev.sh --remove-data
```

---


## 🧠 How It Works

1. The CLI (`uv run cli dev start-env`) runs `docker compose up` for all services.
2. Once **Keycloak** reports healthy, a **one-shot container (`keycloak-setup`)** executes:

   ```bash
   pip install requests && python setup_script.py
   ```
3. This creates the `test-realm`, registers `test-client`, and seeds test users.

The CLI also provides subcommands for:

* Managing databases
* Restarting services
* Generating boilerplate entities and routers

See the [CLI documentation](../docs/cli.md) for details.

---

## 🧪 Integration Testing

Integration tests automatically detect when the dev environment is active.
If OIDC or Temporal are unavailable, related tests are **skipped**.

```bash
uv run pytest -m "integration"
```

---

## 🧭 Troubleshooting

| Symptom                    | Fix                                                              |
| -------------------------- | ---------------------------------------------------------------- |
| **Ports in use**           | `lsof -i :8080` or `:5432` to find and stop conflicting services |
| **Permission denied**      | `chmod +x dev_env/*.sh`                                          |
| **Network errors**         | Reset Docker network: `docker network prune`                     |
| **Keycloak setup fails**   | Check health: `docker compose ps` → rerun `setup_dev.sh`         |
| **Temporal UI CORS error** | Ensure `TEMPORAL_CORS_ORIGINS` matches frontend origin           |

View service logs:

```bash
uv run cli dev logs keycloak
uv run cli dev logs temporal-server
uv run cli dev logs postgres
uv run cli dev logs redis
```

---

## ⚠️ Production Notes

This stack is **for local development only**.

* Uses default credentials (`admin/admin`)
* No SSL/TLS
* Runs Keycloak in `dev` mode
* Stores data in local Docker volumes
* Simplified security defaults for convenience

### For production:

Use external or managed equivalents:

* **OIDC:** Hosted Keycloak, Auth0, Okta, or Azure AD
* **Database:** Managed PostgreSQL (RDS, Cloud SQL)
* **Redis:** Authenticated & persistent (e.g., ElastiCache)
* **Temporal:** Temporal Cloud or hardened self-hosted instance
* **Networking:** HTTPS with valid certificates
* **Security:** Strong secrets, credential rotation, and backups
