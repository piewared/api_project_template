# Temporal Client Service

This service provides centralized management of the Temporal client connection. **All workflow-specific operations should use the `BaseWorkflow` class** which provides type-safe methods for starting, executing, and scheduling workflows.

## Purpose

The `TemporalClientService` manages:
- **Shared client connection** with lazy loading
- **Connection retry logic** (up to 3 attempts)
- **TLS configuration** (when enabled)
- **Health checking**
- **Reconnection** for recovery scenarios

## Configuration

The Temporal service is configured via `config.yaml`:

```yaml
temporal:
  enabled: true                    # Enable/disable Temporal service
  url: "${TEMPORAL_URL:-temporal:7233}"  # Temporal server address
  namespace: default               # Temporal namespace
  task_queue: default              # Default task queue name
  tls: false                       # Enable TLS (requires cert configuration)
```

Environment variables:
- `TEMPORAL_URL`: Temporal server URL (default: `temporal:7233`)
- `TEMPORAL_NAMESPACE`: Namespace to use (default: `default`)

## Usage

### 1. Get Temporal Client (Recommended)

Use the service to get a client, then use `BaseWorkflow` class methods:

```python
from fastapi import APIRouter, Depends
from src.app.api.http.deps import get_temporal_service
from src.app.core.services import TemporalClientService
from src.app.worker.workflows.my_workflow import MyWorkflow, MyWorkflowInput

router = APIRouter()

@router.post("/workflows/start")
async def start_workflow(
    data: MyWorkflowInput,
    temporal_service: TemporalClientService = Depends(get_temporal_service),
):
    # Get client
    client = await temporal_service.get_client()
    
    # Use type-safe BaseWorkflow methods
    handle = await MyWorkflow.start_workflow(
        client,
        input=data,
        id=f"my-workflow-{data.id}",
    )
    
    return {
        "workflow_id": handle.id,
        "run_id": handle.run_id,
    }
```

### 2. BaseWorkflow Methods (Type-Safe)

Your workflows should extend `BaseWorkflow` which provides:

```python
# Start workflow and get handle
handle = await MyWorkflow.start_workflow(
    client,
    input=MyWorkflowInput(...),
    id="workflow-123",
    execution_timeout=timedelta(hours=1),
)

# Execute workflow and wait for result
result = await MyWorkflow.execute_workflow(
    client,
    input=MyWorkflowInput(...),
    id="workflow-123",
)

# Schedule workflow for later
handle = await MyWorkflow.schedule_workflow(
    client,
    input=MyWorkflowInput(...),
    id="workflow-123",
    start_delay=timedelta(hours=1),
)

# Query workflow state (type-safe)
status = await handle.query(MyWorkflow.state)

# Signal workflow (type-safe)
await handle.signal(MyWorkflow.cancel)
```

## Service Properties

### Read-Only Properties

```python
temporal_service = Depends(get_temporal_service)

# Check if enabled
if temporal_service.is_enabled:
    ...

# Get configuration
namespace = temporal_service.namespace  # str
task_queue = temporal_service.task_queue  # str
url = temporal_service.url  # str
```

## Service Methods

### `get_client() -> Client`

Get or create the shared Temporal client connection. Connection is lazy-loaded on first call.

```python
client = await temporal_service.get_client()
```

**Raises**:
- `RuntimeError`: If Temporal is disabled in configuration
- `Exception`: If connection fails after 3 retry attempts

### `health_check() -> bool`

Perform a health check on the Temporal connection.

```python
if await temporal_service.health_check():
    print("Temporal is healthy")
```

**Returns**: `True` if healthy, `False` otherwise

### `reconnect() -> Client`

Force a reconnection to the Temporal server. Useful for recovery after network issues.

```python
client = await temporal_service.reconnect()
```

### `close() -> None`

Release the Temporal client connection. Called automatically during application shutdown.

```python
await temporal_service.close()
```

## Complete Example

```python
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from src.app.api.http.deps import get_temporal_service
from src.app.core.services import TemporalClientService
from src.app.worker.workflows.order import OrderWorkflow, OrderInput, OrderStatus

router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("/{order_id}/process")
async def start_order_processing(
    order_id: str,
    order_data: OrderInput,
    temporal_service: TemporalClientService = Depends(get_temporal_service),
):
    """Start order processing workflow."""
    client = await temporal_service.get_client()
    
    # Start workflow with type safety
    handle = await OrderWorkflow.start_workflow(
        client,
        input=order_data,
        id=f"order-{order_id}",
        execution_timeout=timedelta(hours=24),
    )
    
    return {
        "order_id": order_id,
        "workflow_id": handle.id,
        "run_id": handle.run_id,
    }

@router.get("/{order_id}/status")
async def get_order_status(
    order_id: str,
    temporal_service: TemporalClientService = Depends(get_temporal_service),
):
    """Get current order status from workflow."""
    client = await temporal_service.get_client()
    
    try:
        # Get workflow handle
        handle = client.get_workflow_handle(f"order-{order_id}")
        
        # Query state (type-safe through BaseWorkflow)
        state = await handle.query(OrderWorkflow.state)
        
        return {
            "order_id": order_id,
            "status": state.get("status"),
            "progress": state.get("progress"),
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Order not found: {e}")

@router.post("/{order_id}/approve")
async def approve_order(
    order_id: str,
    approval_notes: str,
    temporal_service: TemporalClientService = Depends(get_temporal_service),
):
    """Approve a pending order."""
    client = await temporal_service.get_client()
    
    handle = client.get_workflow_handle(f"order-{order_id}")
    
    # Signal workflow (assumes OrderWorkflow has an 'approve' signal)
    await handle.signal("approve", approval_notes)
    
    return {"order_id": order_id, "status": "approved"}

@router.delete("/{order_id}")
async def cancel_order(
    order_id: str,
    temporal_service: TemporalClientService = Depends(get_temporal_service),
):
    """Cancel an order."""
    client = await temporal_service.get_client()
    
    handle = client.get_workflow_handle(f"order-{order_id}")
    
    # Use cancel signal from BaseWorkflow
    await handle.signal(OrderWorkflow.cancel)
    
    return {"order_id": order_id, "status": "cancelled"}
```

## Health Check Integration

Add Temporal health check to your readiness endpoint:

```python
@app.get("/ready")
async def readiness(
    temporal_service: TemporalClientService = Depends(get_temporal_service),
) -> dict[str, str]:
    """Readiness check including Temporal."""
    checks = {}
    
    # Temporal health check
    if temporal_service.is_enabled:
        checks["temporal"] = await temporal_service.health_check()
    
    if not all(checks.values()):
        raise HTTPException(status_code=503, detail="Service not ready")
    
    return {"status": "ready", "checks": checks}
```

## Application Lifecycle

The service is initialized during application startup and cleaned up during shutdown:

```python
# src/app/api/http/app.py

async def startup() -> None:
    # ... other initialization ...
    
    temporal_service = TemporalClientService()
    
    deps = ApplicationDependencies(
        # ... other dependencies ...
        temporal_service=temporal_service,
    )
    app.state.app_dependencies = deps

async def shutdown() -> None:
    app_dependencies = app.state.app_dependencies
    # ... other cleanup ...
    await app_dependencies.temporal_service.close()
```

## Why This Design?

1. **Type Safety**: `BaseWorkflow` class methods provide full type checking for inputs/outputs
2. **Separation of Concerns**: Service manages connection state, workflows manage business logic
3. **Single Responsibility**: Each class has one clear purpose
4. **No Duplication**: Workflow logic lives in one place (BaseWorkflow)
5. **Better DX**: IDE autocomplete works properly with typed workflow classes

## See Also

- [BaseWorkflow Class](../../../worker/workflows/base.py)
- [Temporal Python SDK Documentation](https://docs.temporal.io/dev-guide/python)
- [Example Workflows](../../../worker/workflows/)
- [Temporal Configuration](../../../../config.yaml)
