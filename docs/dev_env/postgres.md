# 🗄️ PostgreSQL Development Environment

This directory defines the **PostgreSQL service** used by the local development environment.  
It provides both a **main application database** and a **test database**, with automatic initialization on first run.

---

## 📂 Structure

| File / Directory | Purpose |
|------------------|----------|
| [`docker-compose.yml`](../../dev_env/postgres/docker-compose.yml) | PostgreSQL service definition |
| [`init/`](../../dev_env/postgres/init) | Initialization scripts executed at container startup |
| [`init/01-init-db.sh`](../../dev_env/postgres/init/01-init-db.sh) | Creates `devdb` and `testdb` databases with user permissions |

---

## 🧩 Configuration

* **Image:** `postgres:16-alpine`
* **Authentication:** SCRAM-SHA-256
* **Health check:** Enabled
* **Databases created:**

  * `devdb` (main)
  * `testdb` (testing)
* **User:** `devuser`
* **Password:** `devpass`
* **Persistent Data Volume:** `postgres_data`

> Data persists across container restarts via a named Docker volume.

---


## ⚙️ Usage

Start PostgreSQL:
```bash
docker compose up -d
````

Stop PostgreSQL:

```bash
docker compose down
```

View logs:

```bash
docker compose logs -f postgres
```

---

## 🔌 Access

| Property     | Host        | In-Network Hostname |
| ------------ | ----------- | ------------------- |
| **Host**     | `localhost` | `postgres`          |
| **Port**     | `5432`      | `5432`              |
| **Username** | `devuser`   | `devuser`           |
| **Password** | `devpass`   | `devpass`           |
| **Main DB**  | `devdb`     | `devdb`             |
| **Test DB**  | `testdb`    | `testdb`            |

---

## 🔗 Connection String

```bash
postgresql://devuser:devpass@localhost:5432/devdb
```

If connecting from another container on the same Docker network:

```bash
postgresql://devuser:devpass@postgres:5432/devdb
```

---

## 💾 Data Management

View volume:

```bash
docker volume ls | grep postgres
```

Remove volume (reset database):

```bash
docker compose down -v
```

Backup example:

```bash
docker exec -t postgres pg_dump -U devuser devdb > devdb_backup.sql
```

Restore example:

```bash
cat devdb_backup.sql | docker exec -i postgres psql -U devuser -d devdb
```

---

## 🧠 Connecting via psql

```bash
# Connect to main database
psql -h localhost -U devuser -d devdb

# Connect to test database
psql -h localhost -U devuser -d testdb
```

Or, from within another container:

```bash
psql -h postgres -U devuser -d devdb
```

---

## ⚠️ Notes

* This database is **for local development only**.
* Default credentials (`devuser/devpass`) should **not** be used in production.
* In production, configure:

  * Managed PostgreSQL (e.g., RDS, Cloud SQL)
  * SSL connections
  * Strong passwords and limited privileges

