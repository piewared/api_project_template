# ⚡ Redis Development Service

This directory defines the **Redis service** used by the local development environment.  
Redis provides fast in-memory storage for **caching**, **session management**, and **rate limiting**.

---

## 📦 Configuration

| Setting | Value |
|----------|--------|
| **Image** | `redis:alpine` |
| **Port** | `6379` |
| **Persistence** | Enabled (AOF – Append Only File) |
| **Data Volume** | `redis_data` |
| **Network** | `dev-network` |

Data persists across container restarts via a named Docker volume.

---

## ⚙️ Usage

Redis is automatically started when you launch the development environment:

```bash
uv run cli dev start-env
````

Or manually from this directory:

```bash
docker compose up -d
```

To stop the service:

```bash
docker compose down
```

---

## 🔌 Access

| Type                               | Connection                                  |
| ---------------------------------- | ------------------------------------------- |
| **From Host**                      | `redis://localhost:6380`                    |
| **From Containers (same network)** | `redis://redis:6379`                        |
| **CLI (inside container)**         | `docker exec -it app_dev_redis_cache redis-cli` |

Example check:

```bash
redis-cli -h localhost -p 6380 ping
# PONG
```

---

## 💾 Data Persistence

Redis uses an **Append-Only File (AOF)** strategy to persist data to disk.

| Volume       | Description                       |
| ------------ | --------------------------------- |
| `redis_data` | Stores AOF logs and snapshot data |

View volume:

```bash
docker volume ls | grep redis
```

Remove volume (to reset all cache/session data):

```bash
docker compose down -v
```

---

## 🧠 Common Uses

* Session token storage
* CSRF token management
* Rate limiting
* Caching of OIDC metadata or user info
* Temporal workflow metadata (in transient contexts)

---

## 🧩 Health Check

The Redis container’s health is monitored automatically using:

```bash
redis-cli ping
```

Expected output:

```bash
PONG
```

---

## 🧭 Troubleshooting

| Issue                                | Solution                                                                |
| ------------------------------------ | ----------------------------------------------------------------------- |
| **Port 6379 already in use**         | Run `lsof -i :6379` to identify and stop conflicting services.          |
| **Permission denied / volume error** | Ensure Docker is running and volumes are not locked by another process. |
| **CLI container not found**          | Verify service name: `docker compose ps` should list `app_dev_redis_cache`. |
| **Redis not persisting data**        | Check AOF config (`appendonly yes` is set in the image).                |

---

## ⚠️ Notes

* Default Redis configuration is tuned for **local development**, not production.
* No authentication or TLS is enabled.
* In production, enable:

  * Password authentication (`requirepass`)
  * Data persistence (AOF or RDB)
  * Redis cluster or managed instance (e.g., AWS ElastiCache)
