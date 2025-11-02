# Temporal Deployment Notes

## 1. Database Setup

Temporal requires **two separate databases** to operate:

* **Main database** – stores workflow histories, task queues, and execution metadata.
* **Visibility database** – stores searchable workflow visibility records (used for listing and querying workflows).

These databases must be **created and initialized before Temporal starts**.

### Schema Initialization

Temporal provides a CLI tool to manage schema setup and updates:

👉 [Temporal SQL Tool (`temporal-sql-tool`)](https://github.com/temporalio/temporal/tree/main/tools/sql)

This tool can:

* Create and drop databases.
* Initialize schema versioning tables.
* Apply migrations to bring the schema to a specific version.

Example usage for PostgreSQL:

```bash
temporal-sql-tool \
  --plugin postgres \
  --ep localhost -p 5432 \
  -u temporal_user -pw <password> \
  --db temporal setup-schema \
  --schema-name postgres
```

Repeat for `temporal_visibility` if using a separate visibility database.

> **Tip:**
> In production, initialize schemas using a privileged user (migration role), then run Temporal services with a restricted runtime user.

---

## 2. Configuration Templating

Temporal images use a **configuration templating system** that maps environment variables into configuration files at container startup.

This process is handled by the Docker image’s entrypoint:

📄 [entrypoint.sh](https://github.com/temporalio/docker-builds/blob/main/docker/entrypoint.sh)

It performs the following steps:

1. Expands `{{ env.VAR_NAME }}` placeholders in configuration templates.
2. Writes the rendered configuration to `/etc/temporal/config/`.
3. Calls the main startup script.

---

## 3. Startup Process

After templating, the entrypoint invokes:

📄 [start-temporal.sh](https://github.com/temporalio/docker-builds/blob/main/docker/start-temporal.sh)

This script:

* Starts the Temporal core services (`frontend`, `history`, `matching`, `worker`).
* Optionally starts a `temporal-admin-tools` container for CLI access.
* Loads configuration files and environment overrides.

---

## 4. Configuration Template

The configuration structure for the Temporal server is defined in:

📄 [config_template.yaml](https://github.com/temporalio/temporal/blob/main/docker/config_template.yaml)

This file shows the expected structure for:

* **Persistence:** MySQL/PostgreSQL connection info and database mappings.
* **Services:** Frontend, history, matching, and worker configuration.
* **Cluster metadata:** Cluster name, global namespace settings.
* **Telemetry:** Metrics and Prometheus exporters.

You can override most settings with environment variables (via the templating system).

---

## 5. Dynamic Configuration System

Temporal supports a **dynamic configuration** subsystem for runtime tuning of behavior without restarting services.

* Dynamic config files are typically mounted at `/etc/temporal/dynamicconfig/config.yaml`.
* Changes are polled and applied periodically by Temporal services.
* Used for settings like:

  * Workflow retention overrides
  * Rate limits
  * Task queue partitioning
  * Feature flags for experimental behavior

Documentation:
🔗 [Temporal Dynamic Configuration Reference](https://docs.temporal.io/self-hosted-guide/dynamic-configuration)

---

## 6. Summary Workflow for a Fresh Setup

1. **Create roles and databases** (for Temporal and Temporal Visibility).
2. **Initialize schemas** using `temporal-sql-tool setup-schema`.
3. **Render configs** via entrypoint (environment variables → config template).
4. **Start Temporal services** using `start-temporal.sh`.
5. **Verify cluster health** with `tctl` or `temporal` CLI:

   ```bash
   temporal operator namespace list
   temporal operator cluster health
   ```

