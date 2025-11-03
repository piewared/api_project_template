# Temporal Usage Guide

This guide shows how to use the Temporal service from FastAPI endpoints to execute workflows. It covers the complete lifecycle from defining workflows to executing them via API routes.

## Quick Start

### 1. Define a Workflow

Create a workflow class that inherits from `BaseWorkflow[TInput, TReturn]`:

```python
# src/app/worker/workflows/order_workflow.py
from pydantic import BaseModel
from temporalio import workflow

from src.app.worker.workflows.base import BaseWorkflow
from src.app.worker.registry import workflow_defn

# Input/Output models with Pydantic validation
class OrderInput(BaseModel):
    order_id: str
    customer_email: str
    amount: float
    items: list[dict]

class OrderOutput(BaseModel):
    order_id: str
    status: str
    message: str

# Workflow definition
@workflow_defn(queue="orders")  # Register to task queue
@workflow.defn                   # Temporal decorator
class OrderWorkflow(BaseWorkflow[OrderInput, OrderOutput]):
    
    @workflow.run
    async def run(self, input: OrderInput) -> OrderOutput:
        # Your workflow logic here
        workflow.logger.info(f"Processing order {input.order_id}")
        
        # Execute activities
        payment_result = await self.execute_activity(
            charge_payment,
            input.amount
        )
        
        return OrderOutput(
            order_id=input.order_id,
            status="completed",
            message=f"Order processed successfully"
        )
```

### 2. Define Activities

```python
# src/app/worker/activities/payment.py
from temporalio import activity
from src.app.worker.registry import activity_defn

@activity_defn(queue="orders")  # Same queue as workflow
@activity.defn
async def charge_payment(amount: float) -> str:
    # Your activity logic here
    activity.logger.info(f"Charging ${amount}")
    
    # Simulate payment processing
    await asyncio.sleep(1)
    
    return f"txn_{uuid.uuid4().hex[:8]}"
```

### 3. Execute from FastAPI

```python
# src/app/api/http/routers/orders.py
from fastapi import APIRouter, Depends

from src.app.api.http.deps import get_temporal_service
from src.app.core.services.temporal.temporal_client import TemporalClientService
from src.app.worker.workflows.order_workflow import OrderInput, OrderWorkflow

router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("/")
async def create_order(
    order_data: OrderInput,
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    """Start an order processing workflow."""
    
    # Get Temporal client
    client = await temporal_service.get_client()
    
    # Start workflow (non-blocking)
    handle = await OrderWorkflow.start_workflow(
        client,
        input=order_data,
        id=f"order-{order_data.order_id}"
    )
    
    return {
        "workflow_id": handle.id,
        "status": "started"
    }
```

## Accessing the Temporal Service

### Via FastAPI Dependency (Recommended)

The Temporal client is available as a FastAPI dependency:

```python
from fastapi import Depends
from src.app.api.http.deps import get_temporal_service
from src.app.core.services.temporal.temporal_client import TemporalClientService

async def my_endpoint(
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    # Use client...
```

### Direct Access (Not Recommended)

You can also access the service directly from app state, but this bypasses FastAPI's dependency injection:

```python
from fastapi import Request

async def my_endpoint(request: Request):
    app_deps = request.app.state.app_dependencies
    temporal_service = app_deps.temporal_service
    client = await temporal_service.get_client()
    # Use client...
```

## Workflow Execution Patterns

### Pattern 1: Start and Return Immediately (Non-Blocking)

Use when you want to start a workflow and return a response immediately without waiting for completion.

```python
@router.post("/orders")
async def create_order(
    order_data: OrderInput,
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    
    # Start workflow (returns immediately)
    handle = await OrderWorkflow.start_workflow(
        client,
        input=order_data,
        id=f"order-{order_data.order_id}"
    )
    
    return {
        "workflow_id": handle.id,
        "status": "started",
        "message": "Order is being processed"
    }
```

**Use Cases**:
- Long-running workflows (> 5 seconds)
- Background processing
- Async operations where user doesn't need immediate result
- Webhooks or event-driven flows

---

### Pattern 2: Execute and Wait for Result (Blocking)

Use when you need the workflow result before returning a response.

```python
@router.post("/orders/sync")
async def create_order_sync(
    order_data: OrderInput,
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    
    # Execute workflow (waits for completion)
    result = await OrderWorkflow.execute_workflow(
        client,
        input=order_data,
        id=f"order-{order_data.order_id}"
    )
    
    return {
        "order_id": result.order_id,
        "status": result.status,
        "message": result.message
    }
```

**Use Cases**:
- Fast workflows (< 5 seconds)
- Synchronous operations
- When client needs immediate result
- Testing/debugging

**⚠️ Warning**: HTTP requests have timeouts (typically 30-60 seconds). Don't use this pattern for long-running workflows.

---

### Pattern 3: Schedule Delayed Execution

Use when you want a workflow to start at a future time.

```python
from datetime import timedelta

@router.post("/orders/scheduled")
async def schedule_order(
    order_data: OrderInput,
    delay_minutes: int,
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    
    # Schedule workflow to start later
    handle = await OrderWorkflow.schedule_workflow(
        client,
        input=order_data,
        id=f"order-{order_data.order_id}",
        start_delay=timedelta(minutes=delay_minutes)
    )
    
    return {
        "workflow_id": handle.id,
        "scheduled_in_minutes": delay_minutes,
        "status": "scheduled"
    }
```

**Use Cases**:
- Delayed jobs (send email in 1 hour)
- Scheduled tasks (run report at midnight)
- Reminder systems
- Recurring workflows (monthly billing)

---

### Pattern 4: Get Status of Running Workflow

Use when you want to check the status of an already-running workflow.

```python
from temporalio.client import WorkflowHandle

@router.get("/orders/{workflow_id}/status")
async def get_order_status(
    workflow_id: str,
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    
    # Get handle to existing workflow
    handle: WorkflowHandle = client.get_workflow_handle(workflow_id)
    
    # Query workflow state
    try:
        state = await handle.query(OrderWorkflow.state)
        return {
            "workflow_id": workflow_id,
            "state": state,
            "status": "running"
        }
    except Exception as e:
        return {
            "workflow_id": workflow_id,
            "error": str(e),
            "status": "not_found"
        }
```

**Use Cases**:
- Status polling endpoints
- Progress tracking
- Admin dashboards
- Long-running workflow monitoring

---

### Pattern 5: Send Signal to Running Workflow

Use when you need to send an event or data to a running workflow.

```python
@router.post("/orders/{workflow_id}/cancel")
async def cancel_order(
    workflow_id: str,
    reason: str,
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    
    # Get handle to existing workflow
    handle = client.get_workflow_handle(workflow_id)
    
    # Send cancel signal
    await handle.signal(OrderWorkflow.cancel)
    
    return {
        "workflow_id": workflow_id,
        "status": "cancel_signal_sent",
        "reason": reason
    }
```

**Use Cases**:
- Cancellation requests
- User actions (approve/reject)
- External events (payment confirmed)
- Dynamic workflow updates

---

### Pattern 6: Wait for Result of Started Workflow

Use when you've started a workflow earlier and now want to wait for its result.

```python
@router.get("/orders/{workflow_id}/result")
async def get_order_result(
    workflow_id: str,
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    
    # Get handle to existing workflow
    handle = client.get_workflow_handle(workflow_id)
    
    # Wait for result (blocks until workflow completes)
    try:
        result = await handle.result()
        return {
            "workflow_id": workflow_id,
            "result": result,
            "status": "completed"
        }
    except Exception as e:
        return {
            "workflow_id": workflow_id,
            "error": str(e),
            "status": "failed"
        }
```

**Use Cases**:
- Polling for completion
- Webhook callbacks after workflow finishes
- Fetching results after async processing

---

## Advanced Usage

### Custom Timeouts and Retry Policies

Override default configuration per workflow execution:

```python
from datetime import timedelta
from temporalio.common import RetryPolicy

@router.post("/orders/urgent")
async def create_urgent_order(
    order_data: OrderInput,
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    
    # Custom timeouts and retry policy
    handle = await OrderWorkflow.start_workflow(
        client,
        input=order_data,
        id=f"order-{order_data.order_id}",
        execution_timeout=timedelta(minutes=30),  # Override default
        run_timeout=timedelta(minutes=15),
        retry_policy=RetryPolicy(
            maximum_attempts=2,  # Only retry once
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=10),
            backoff_coefficient=2.0
        )
    )
    
    return {"workflow_id": handle.id}
```

---

### Workflow with Memo and Search Attributes

Add metadata to workflows for searching and filtering in Temporal UI:

```python
@router.post("/orders/tracked")
async def create_tracked_order(
    order_data: OrderInput,
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    
    handle = await OrderWorkflow.start_workflow(
        client,
        input=order_data,
        id=f"order-{order_data.order_id}",
        memo={
            "customer_email": order_data.customer_email,
            "order_amount": order_data.amount
        },
        search_attributes={
            "CustomKeywordField": [order_data.customer_email],
            "CustomIntField": [int(order_data.amount)]
        }
    )
    
    return {"workflow_id": handle.id}
```

**Note**: Search attributes must be registered in Temporal server first. See [Temporal docs on search attributes](https://docs.temporal.io/visibility#search-attribute).

---

### Batch Workflow Execution

Start multiple workflows concurrently:

```python
import asyncio

@router.post("/orders/batch")
async def create_batch_orders(
    orders: list[OrderInput],
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    
    # Start all workflows concurrently
    handles = await asyncio.gather(*[
        OrderWorkflow.start_workflow(
            client,
            input=order,
            id=f"order-{order.order_id}"
        )
        for order in orders
    ])
    
    return {
        "total": len(handles),
        "workflow_ids": [h.id for h in handles]
    }
```

---

### Error Handling

Handle workflow failures gracefully:

```python
from temporalio.exceptions import WorkflowAlreadyStartedError, WorkflowFailureError

@router.post("/orders/safe")
async def create_order_safe(
    order_data: OrderInput,
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    
    try:
        handle = await OrderWorkflow.start_workflow(
            client,
            input=order_data,
            id=f"order-{order_data.order_id}"
        )
        return {
            "workflow_id": handle.id,
            "status": "started"
        }
    
    except WorkflowAlreadyStartedError:
        # Workflow with this ID is already running
        return {
            "workflow_id": f"order-{order_data.order_id}",
            "status": "already_running",
            "message": "Workflow is already in progress"
        }
    
    except WorkflowFailureError as e:
        # Workflow failed during execution
        return {
            "workflow_id": f"order-{order_data.order_id}",
            "status": "failed",
            "error": str(e)
        }
    
    except Exception as e:
        # Other errors (connection issues, etc.)
        return {
            "workflow_id": f"order-{order_data.order_id}",
            "status": "error",
            "error": f"Failed to start workflow: {str(e)}"
        }
```

---

## Type Safety

Our wrapper provides full type safety through generics:

```python
# Type checker knows the exact input/output types
handle: WorkflowHandle[OrderWorkflow, OrderOutput] = await OrderWorkflow.start_workflow(
    client,
    input=OrderInput(order_id="123", customer_email="test@example.com", amount=99.99, items=[]),
    id="order-123"
)

# Type checker knows result is OrderOutput
result: OrderOutput = await handle.result()

# Auto-completion works
print(result.order_id)   # ✓ Type checker knows this exists
print(result.status)     # ✓ Type checker knows this exists
print(result.invalid)    # ✗ Type checker error!
```

---

## Health Checks

Check Temporal connectivity in health check endpoints:

```python
@router.get("/health")
async def health_check(
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    temporal_healthy = await temporal_service.health_check()
    
    return {
        "status": "healthy" if temporal_healthy else "degraded",
        "temporal": {
            "enabled": temporal_service.is_enabled,
            "healthy": temporal_healthy,
            "url": temporal_service.url,
            "namespace": temporal_service.namespace
        }
    }
```

---

## Running Workers

Workers must be running to execute workflows. Start a worker process:

```bash
# Start worker for specific queue
uv run python -m src.app.worker.main serve --queue orders

# Start workers for all discovered queues
uv run python -m src.app.worker.main serve

# Start worker with custom logging
uv run python -m src.app.worker.main serve --log-level DEBUG

# Start worker with custom drain timeout
uv run python -m src.app.worker.main serve --drain-timeout 300
```

**Production Setup**:
- Run workers as separate services/containers
- Use process managers (systemd, supervisord, Kubernetes)
- Scale workers horizontally for throughput
- Monitor worker health and restart on failure

---

## Common Patterns

### Pattern: Idempotent Workflow Execution

Ensure workflows can be safely retried:

```python
# Use deterministic IDs based on business logic
workflow_id = f"order-{order_data.order_id}-{datetime.utcnow().date()}"

handle = await OrderWorkflow.start_workflow(
    client,
    input=order_data,
    id=workflow_id  # Same ID = same workflow (won't duplicate)
)
```

### Pattern: Long-Running Background Jobs

For operations that take minutes/hours:

```python
@router.post("/reports/generate")
async def generate_report(
    report_config: ReportConfig,
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    
    # Start long-running workflow
    handle = await ReportGenerationWorkflow.start_workflow(
        client,
        input=report_config,
        id=f"report-{uuid.uuid4()}",
        execution_timeout=timedelta(hours=2)
    )
    
    # Return immediately
    return {
        "report_id": handle.id,
        "status": "generating",
        "status_url": f"/reports/{handle.id}/status"
    }

@router.get("/reports/{report_id}/status")
async def get_report_status(
    report_id: str,
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    handle = client.get_workflow_handle(report_id)
    
    # Check if completed
    try:
        result = await asyncio.wait_for(handle.result(), timeout=0.1)
        return {"status": "completed", "result": result}
    except asyncio.TimeoutError:
        state = await handle.query(ReportGenerationWorkflow.state)
        return {"status": "processing", "progress": state.get("progress", 0)}
```

### Pattern: Human-in-the-Loop Workflows

For workflows requiring approval:

```python
@workflow_defn(queue="approvals")
@workflow.defn
class ApprovalWorkflow(BaseWorkflow[ApprovalInput, ApprovalOutput]):
    def __init__(self):
        super().__init__()
        self._approved = False
        self._rejected = False
    
    @workflow.run
    async def run(self, input: ApprovalInput) -> ApprovalOutput:
        # Send notification
        await self.execute_activity(send_approval_request, input.approver_email)
        
        # Wait for approval (up to 24 hours)
        await workflow.wait_condition(
            lambda: self._approved or self._rejected,
            timeout=timedelta(hours=24)
        )
        
        if self._approved:
            return ApprovalOutput(status="approved")
        else:
            return ApprovalOutput(status="rejected")
    
    @workflow.signal
    def approve(self):
        self._approved = True
    
    @workflow.signal
    def reject(self):
        self._rejected = True

# API endpoints
@router.post("/approvals/{workflow_id}/approve")
async def approve_workflow(
    workflow_id: str,
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(ApprovalWorkflow.approve)
    return {"status": "approved"}
```

---

## Testing Workflows

### Unit Testing Workflows

Use Temporal's testing framework:

```python
import pytest
from temporalio.testing import WorkflowEnvironment

@pytest.mark.asyncio
async def test_order_workflow():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        # Execute workflow in test environment
        result = await env.client.execute_workflow(
            OrderWorkflow.run,
            OrderInput(
                order_id="TEST-123",
                customer_email="test@example.com",
                amount=99.99,
                items=[]
            ),
            id="test-workflow",
            task_queue="orders"
        )
        
        assert result.status == "completed"
        assert result.order_id == "TEST-123"
```

### Integration Testing with Real Temporal

```python
@pytest.mark.asyncio
async def test_order_workflow_integration():
    from temporalio.client import Client
    
    # Connect to real Temporal server
    client = await Client.connect("localhost:7233")
    
    # Execute workflow
    result = await OrderWorkflow.execute_workflow(
        client,
        input=OrderInput(
            order_id="INT-TEST-123",
            customer_email="test@example.com",
            amount=99.99,
            items=[]
        ),
        id=f"test-{uuid.uuid4()}"
    )
    
    assert result.status == "completed"
```

---

## Debugging

### Enable Workflow Logging

Workflows can log using `workflow.logger`:

```python
@workflow.run
async def run(self, input: OrderInput) -> OrderOutput:
    workflow.logger.info(f"Starting order workflow for {input.order_id}")
    workflow.logger.debug(f"Input: {input}")
    
    result = await self.execute_activity(process_payment, input.amount)
    
    workflow.logger.info(f"Payment processed: {result}")
    return OrderOutput(...)
```

### View Logs in Terminal

```bash
# Start worker with DEBUG logging
uv run python -m src.app.worker.main serve --log-level DEBUG --queue orders
```

### View Execution History in Temporal UI

See [Temporal Web UI](./temporal-web-ui.md) for details on viewing workflow execution history, inputs, outputs, and errors.

---

## Related Documentation

- [Main Overview](./main.md) - Temporal concepts and architecture
- [Configuration](./configuration.md) - Configure timeouts and retry policies
- [Security](./security.md) - Secure Temporal communication
- [Temporal Web UI](./temporal-web-ui.md) - Monitor workflows visually
