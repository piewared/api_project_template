# ⏱️ Temporal Workflow Server

This directory defines the **Temporal workflow orchestration environment**, which provides reliable scheduling, background task management, and long-running workflow execution.

The setup includes:
- A **Temporal server** (gRPC + web UI)
- A **dedicated PostgreSQL instance** for persistence
- Integration with other local services via the `dev-network` Docker bridge

---

## 📦 Services Overview

| Service | Purpose | Port(s) | Notes |
|----------|----------|---------|-------|
| **temporal-server** | Main Temporal service (gRPC API) | 7233 | Used by workers and clients |
| **temporal-web** | Web UI for monitoring workflows | 8081 | Accessible at [http://localhost:8081](http://localhost:8081) |
| **temporal-postgresql** | Dedicated Temporal database | — (internal) | Not exposed to host |

---

## ⚙️ Configuration

### Temporal Server
- **Image:** `temporalio/auto-setup:1.28.1`
- **Database:** PostgreSQL 16
- **Network:** `dev-network`
- **Environment Variables:**
  - `DB=postgres12`
  - `POSTGRES_USER=temporal`
  - `POSTGRES_PWD=temporal`
  - `POSTGRES_SEEDS=temporal-postgresql`
  - `TEMPORAL_ADDRESS=temporal-server:7233`
  - `TEMPORAL_CLI_ADDRESS=temporal-server:7233`

### Temporal PostgreSQL
- **Image:** `postgres:16`
- **User:** `temporal`
- **Password:** `temporal`
- **Volume:** `temporal_postgres_data`
- **Network:** `dev-network`
- **Health Check:** `pg_isready`

### Temporal Web UI
- **Image:** `temporalio/ui:2.34.0`
- **Port Mapping:** `8081:8080`
- **CORS Origin:** `http://localhost:3000`
- **Network:** `dev-network`

---

## 🚀 Usage

Start Temporal with the full development stack:
```bash
uv run cli dev start-env
````

Or manually:

```bash
docker compose up -d temporal-postgresql temporal-server temporal-web
```

Stop services:

```bash
docker compose down
```

View logs:

```bash
docker compose logs -f temporal-server
```

---

## 🌐 Access

| Component    | URL / Endpoint                                 | Description                    |
| ------------ | ---------------------------------------------- | ------------------------------ |
| **Web UI**   | [http://localhost:8081](http://localhost:8081) | Visualize and manage workflows |
| **gRPC API** | `localhost:7233`                               | Connect from Temporal workers  |
| **CLI**      | `tctl --address localhost:7233 namespace list` | Temporal command-line access   |

---

## 💾 Data Persistence

| Volume                   | Purpose                                            |
| ------------------------ | -------------------------------------------------- |
| `temporal_postgres_data` | Stores Temporal PostgreSQL data                    |
| `temporal_data`          | Stores Temporal metadata and state (if applicable) |

Data persists between restarts and is managed automatically by Docker.

Reset all Temporal data:

```bash
docker compose down -v
```

---

## 🧩 Integration Notes

* The **FastAPI app** connects to Temporal via `localhost:7233` (or `temporal-server:7233` from within Docker).
* Used for:

  * Background workflows (e.g., email dispatch, batch processing)
  * Long-running transactions
  * Sagas and compensating workflows
* Works seamlessly with your `uv` CLI and test setup.

---

## 🧠 Health Checks

| Service         | Check Command         | Expected Result         |
| --------------- | --------------------- | ----------------------- |
| PostgreSQL      | `pg_isready`          | `accepting connections` |
| Temporal Server | `tctl cluster health` | `SERVING`               |
| Temporal Web    | HTTP 200 OK on `/`    | UI loads normally       |

Example:

```bash
docker exec -it api-template-temporal tctl cluster health
```

---

## ⚠️ Notes

* Designed for **local development and testing** only.
* Default credentials and networking are not secure.
* In production, use:

  * Managed PostgreSQL or high-availability database
  * Temporal Cloud or hardened self-hosted setup
  * TLS, authentication, and monitoring configuration
