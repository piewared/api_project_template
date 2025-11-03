# Temporal Configuration

This document describes all Temporal configuration options available in `config.yaml` and explains the defaults chosen for this application.

## Configuration File Location

Temporal settings are located in `/config.yaml` under the `config.temporal` section.

## Configuration Structure

```yaml
config:
  temporal:
    enabled: true
    url: "${TEMPORAL_URL:-temporal:7233}"
    namespace: "default"
    task_queue: "default"
    tls: false
    
    workflows:
      execution_timeout_s: 86400    # 24 hours
      run_timeout_s: 7200            # 2 hours
      task_timeout_s: 10             # 10 seconds
      retry:
        maximum_attempts: 3
        initial_interval_seconds: 5
        backoff_coefficient: 2.0
        maximum_interval_seconds: 60
    
    activities:
      start_to_close_timeout_s: 1200        # 20 minutes
      schedule_to_close_timeout_s: 3600     # 1 hour
      heartbeat_timeout_s: 300              # 5 minutes
      retry:
        maximum_attempts: 5
        initial_interval_seconds: 5
        backoff_coefficient: 2.0
        maximum_interval_seconds: 60
    
    worker:
      enabled: true
      activities_per_second: 10
      max_concurrent_activities: 100
      max_concurrent_workflows: 100
      poll_interval_ms: 1000
      workflow_cache_size: 100
      max_workflow_tasks_per_second: 100
      max_concurrent_workflow_tasks: 100
      sticky_queue_schedule_to_start_timeout_ms: 10000
      worker_build_id: "api-worker-1"
```

## Core Settings

### `enabled` (boolean, default: `true`)
Controls whether Temporal integration is active.

- **`true`**: Temporal client and workers are available
- **`false`**: Temporal client will raise exceptions if used, workers won't start

**When to disable**: 
- Local development without Temporal server
- Testing environments that don't need workflow execution
- Staging environments where Temporal isn't deployed yet

**Environment Variable**: None (controlled via config file only)

---

### `url` (string, default: `temporal:7233`)
Temporal server gRPC endpoint.

**Format**: `host:port`

**Common Values**:
- `temporal:7233` - Docker Compose service name (development)
- `localhost:7233` - Local Temporal server
- `temporal.example.com:7233` - Production server

**Environment Variable**: `TEMPORAL_URL`

**Example**:
```bash
export TEMPORAL_URL="temporal-prod.internal:7233"
```

**Note**: In production with TLS, use port `7233` with TLS configuration (see Security section).

---

### `namespace` (string, default: `"default"`)
Temporal namespace for logical isolation of workflows.

**What are namespaces?**
- Logical grouping of workflows within a Temporal cluster
- Separate visibility, retention policies, and rate limits
- Common pattern: one namespace per environment or team

**Common Patterns**:
- `default` - Development/simple deployments
- `production` - Production workflows
- `staging` - Staging environment
- `team-name` - Multi-tenant scenarios

**How to create namespaces**: Use Temporal CLI or admin API
```bash
# Via Temporal CLI (tctl)
tctl --namespace my-namespace namespace register
```

**Environment Variable**: None (controlled via config file only)

---

### `task_queue` (string, default: `"default"`)
**⚠️ Deprecated in favor of queue-specific decorators**

This is a legacy default. Modern workflows use task queue names declared in `@workflow_defn(queue="name")` decorators.

**Current Usage**: Only used as a fallback if a workflow doesn't declare a queue (which should never happen with our wrapper).

---

### `tls` (boolean, default: `false`)
Enable TLS/mTLS for secure communication with Temporal server.

- **`false`**: Insecure plaintext gRPC (development only)
- **`true`**: Requires certificate configuration (see [Security](./security.md))

**Environment Variable**: `TEMPORAL_TLS_ENABLED`

**Example**:
```bash
export TEMPORAL_TLS_ENABLED="true"
```

**See**: [Security Documentation](./security.md) for mTLS setup instructions.

---

## Workflow Timeouts

These settings control the maximum execution times for workflows. All values are in **seconds**.

### `workflows.execution_timeout_s` (default: `86400` = 24 hours)
**Maximum total time** a workflow can execute, including retries and continues-as-new.

**What it controls**: The absolute deadline for workflow completion from first start to final termination.

**When it triggers**: 
- Workflow has been running for 24 hours total
- Includes time spent retrying after failures
- Includes time across multiple "continue as new" executions

**Recommended Values**:
- **Short tasks** (API orchestration): `3600` (1 hour)
- **Medium tasks** (report generation): `7200` (2 hours)
- **Long tasks** (data migrations): `86400` (24 hours)
- **Very long tasks** (monthly jobs): `604800` (7 days)

**Override per workflow**:
```python
handle = await MyWorkflow.start_workflow(
    client,
    input=my_input,
    id="wf-123",
    execution_timeout=timedelta(hours=2)  # Override to 2 hours
)
```

---

### `workflows.run_timeout_s` (default: `7200` = 2 hours)
**Maximum time for a single run** of a workflow (before retries or continues-as-new).

**What it controls**: How long a single attempt at executing the workflow can take.

**When it triggers**: 
- A single workflow run has been executing for 2 hours
- After timeout, workflow is retried (if retry policy allows)
- Reset to 0 when workflow uses "continue as new"

**Recommended Values**:
- **Fast workflows**: `600` (10 minutes)
- **Standard workflows**: `3600` (1 hour)
- **Slow workflows**: `7200` (2 hours)

**Use Case**: Prevents a single run from getting stuck forever, but allows retries to make progress.

---

### `workflows.task_timeout_s` (default: `10` seconds)
**Maximum time** for a single workflow task (decision task) to complete.

**What it controls**: How long the workflow code has to process a single event (timer fired, activity completed, signal received).

**When it triggers**: 
- Workflow event handler takes longer than 10 seconds to return
- Usually indicates blocking code in workflow (which violates Temporal's determinism requirements)

**Recommended Values**:
- **Default**: `10` seconds (suitable for most workflows)
- **Complex workflows**: `30` seconds (if lots of in-memory calculations)

**⚠️ Warning**: If this triggers, it usually means:
1. You have blocking I/O in workflow code (move it to an activity!)
2. You have a very long loop in workflow code (use activities or split the workflow)
3. You have non-deterministic code (timestamps, random, external calls)

---

### `workflows.retry` Configuration

Retry policy for workflow execution failures.

#### `maximum_attempts` (default: `3`)
Maximum number of workflow execution attempts before giving up.

- **`1`**: No retries
- **`3`**: Two retries after initial failure
- **`0`**: Unlimited retries (dangerous!)

#### `initial_interval_seconds` (default: `5`)
Time to wait before the first retry attempt.

#### `backoff_coefficient` (default: `2.0`)
Multiplier for retry delay on each subsequent attempt.

**Example**: With `initial_interval=5` and `backoff_coefficient=2.0`:
- 1st retry after 5 seconds
- 2nd retry after 10 seconds
- 3rd retry after 20 seconds

#### `maximum_interval_seconds` (default: `60`)
Maximum wait time between retry attempts (caps exponential backoff).

---

## Activity Timeouts

These settings control timeouts for individual activities. All values are in **seconds**.

### `activities.start_to_close_timeout_s` (default: `1200` = 20 minutes)
**Maximum time** for a single activity execution from start to completion.

**What it controls**: How long an activity can run for a single attempt.

**When it triggers**: 
- Activity has been executing for 20 minutes
- Activity is cancelled and retried (if retry policy allows)

**Recommended Values**:
- **Fast activities** (database queries): `30` (30 seconds)
- **Medium activities** (API calls): `300` (5 minutes)
- **Slow activities** (file processing): `1200` (20 minutes)
- **Very slow activities** (video transcoding): `3600` (1 hour)

**Override per activity**:
```python
result = await self.execute_activity(
    my_activity,
    input_data,
    start_to_close_timeout=timedelta(minutes=5)  # Override to 5 minutes
)
```

---

### `activities.schedule_to_close_timeout_s` (default: `3600` = 1 hour)
**Maximum total time** from scheduling to completion, including retries.

**What it controls**: The absolute deadline for activity completion across all retry attempts.

**When it triggers**: 
- Activity has been retrying for 1 hour total
- Includes all retry delays and execution times
- Activity is permanently failed (no more retries)

**Relationship**: Must be greater than `start_to_close_timeout_s × maximum_attempts`

**Recommended Values**:
- **Critical activities** (payment): `300` (5 minutes)
- **Standard activities**: `3600` (1 hour)
- **Background activities**: `7200` (2 hours)

---

### `activities.heartbeat_timeout_s` (default: `300` = 5 minutes)
**Maximum time** between heartbeat reports from long-running activities.

**What it controls**: How often activities must report they're still alive.

**When it triggers**: 
- Activity hasn't called `activity.heartbeat()` for 5 minutes
- Activity is considered failed and retried

**When to use heartbeats**:
- Long-running activities (> 1 minute)
- Activities that can be partially completed
- Activities where you want progress reporting

**Example activity with heartbeat**:
```python
@activity_defn(queue="data-processing")
@activity.defn
async def process_large_file(file_path: str) -> int:
    total_lines = count_lines(file_path)
    processed = 0
    
    for line in read_file(file_path):
        process_line(line)
        processed += 1
        
        # Report progress every 100 lines
        if processed % 100 == 0:
            activity.heartbeat(processed)  # Report progress
    
    return processed
```

**Recommended Values**:
- **No heartbeats needed**: Don't set (or set to 0)
- **With heartbeats**: `300` (5 minutes)

---

### `activities.retry` Configuration

Retry policy for activity failures.

#### `maximum_attempts` (default: `5`)
Maximum number of activity execution attempts.

- **`1`**: No retries (fail immediately)
- **`5`**: Four retries after initial failure
- **`0`**: Unlimited retries (use with caution)

**Recommended Values**:
- **Idempotent operations** (GET requests): `5` or more
- **Non-idempotent operations** (charge payment): `1` or `2`

#### `initial_interval_seconds` (default: `5`)
Time to wait before the first retry.

#### `backoff_coefficient` (default: `2.0`)
Multiplier for retry delay (exponential backoff).

#### `maximum_interval_seconds` (default: `60`)
Maximum retry delay (caps exponential backoff).

---

## Worker Settings

Configuration for Temporal worker processes. These settings affect worker performance and resource usage.

### `worker.enabled` (default: `true`)
Whether worker functionality is enabled.

- **`true`**: Workers can be started via `python -m src.app.worker.main serve`
- **`false`**: Worker commands will fail

---

### `worker.activities_per_second` (default: `10`)
**⚠️ Note**: This setting is present in config but not currently used by the worker implementation.

In future implementations, this would control the rate limit for activity executions per second.

---

### `worker.max_concurrent_activities` (default: `100`)
Maximum number of activities executing concurrently in a single worker process.

**What it controls**: Worker-level concurrency limit for activities.

**When to adjust**:
- **Increase** if activities are I/O-bound and you want more throughput
- **Decrease** if activities are CPU-bound or memory-intensive

**Environment Variable Override**:
```bash
export ACT_CONCURRENCY=200
```

---

### `worker.max_concurrent_workflows` (default: `100`)
Maximum number of workflows executing concurrently in a single worker process.

**What it controls**: Worker-level concurrency limit for workflow tasks.

**Note**: Workflow tasks are usually very fast (milliseconds), so this rarely needs adjustment.

---

### `worker.poll_interval_ms` (default: `1000`)
**⚠️ Note**: This setting is present in config but not currently used by the worker implementation.

In future implementations, this would control how often workers poll task queues for new work.

---

### `worker.workflow_cache_size` (default: `100`)
**⚠️ Note**: This setting is present in config but not currently used by the worker implementation.

In future implementations, this would control the in-memory cache size for workflow instances (sticky execution optimization).

---

### `worker.max_workflow_tasks_per_second` (default: `100`)
**⚠️ Note**: This setting is present in config but not currently used by the worker implementation.

In future implementations, this would rate-limit workflow task processing.

---

### `worker.max_concurrent_workflow_tasks` (default: `100`)
Maximum number of workflow tasks processing concurrently in a single worker.

**Environment Variable Override**:
```bash
export WF_TASKS=64
```

---

### `worker.sticky_queue_schedule_to_start_timeout_ms` (default: `10000`)
**⚠️ Note**: This setting is present in config but not currently used by the worker implementation.

Sticky execution is an optimization where workflows prefer to run on the same worker to reuse cached state.

---

### `worker.worker_build_id` (default: `"api-worker-1"`)
Identifier for this worker build, used for versioning and deployment strategies.

**Use Cases**:
- Blue/green deployments
- Gradual rollouts
- Identifying which code version processed a workflow

---

## Environment-Specific Configurations

### Development
```yaml
temporal:
  enabled: true
  url: "temporal:7233"  # Docker Compose service
  tls: false
  namespace: "default"
```

### Staging
```yaml
temporal:
  enabled: true
  url: "temporal-staging.internal:7233"
  tls: true
  namespace: "staging"
```

### Production
```yaml
temporal:
  enabled: true
  url: "temporal-prod.internal:7233"
  tls: true
  namespace: "production"
  workflows:
    execution_timeout_s: 43200  # 12 hours (shorter for prod)
  activities:
    retry:
      maximum_attempts: 3  # Fewer retries, fail faster
```

---

## Best Practices

### Timeout Hierarchy
Ensure timeouts follow this relationship:
```
workflow.execution_timeout 
  > workflow.run_timeout 
    > (activity.schedule_to_close_timeout × workflow.activity_count)
      > activity.start_to_close_timeout × activity.retry.maximum_attempts
```

### Retry Strategy
- **Idempotent operations**: Higher `maximum_attempts` (5-10)
- **Non-idempotent operations**: Lower `maximum_attempts` (1-2)
- **Fast-failing APIs**: Lower `initial_interval_seconds` (1-2)
- **Rate-limited APIs**: Higher `maximum_interval_seconds` (300+)

### Resource Tuning
- Start with defaults
- Monitor worker CPU/memory usage via `docker stats` or metrics
- Adjust `max_concurrent_activities` based on activity type:
  - **I/O-bound**: Increase (200+)
  - **CPU-bound**: Decrease to match CPU cores
  - **Memory-intensive**: Calculate based on available RAM

### Worker Scaling
- Run multiple worker processes for high throughput
- Each worker should have its own `worker_build_id` for versioning
- Use task queues to segregate workload types (fast vs. slow activities)

---

## Loading Configuration

The configuration is loaded automatically by the application via `src/app/runtime/context.py`:

```python
from src.app.runtime.context import get_config

config = get_config()
temporal_config = config.temporal

print(f"Temporal URL: {temporal_config.url}")
print(f"Namespace: {temporal_config.namespace}")
```

All workflow and activity wrappers automatically load these settings via `default_workflow_opts()` and `default_activity_opts()` functions in `src/app/worker/workflows/base.py`.

---

## Related Documentation

- [Main Overview](./main.md) - Temporal concepts and architecture
- [Usage Guide](./usage.md) - How to execute workflows
- [Security](./security.md) - TLS/mTLS configuration
- [Temporal Web UI](./temporal-web-ui.md) - Access the management interface
