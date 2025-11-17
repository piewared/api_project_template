# FastAPI Temporal Workflows

Learn how to implement distributed workflows and async background tasks in your FastAPI application using Temporal. This guide covers workflow design, activities, worker setup, and best practices for building reliable async processing with Temporal and FastAPI.

## Overview

API Forge integrates Temporal for distributed workflow orchestration, providing:

- **Durable execution** - Workflows survive failures and restarts
- **Long-running processes** - Handle tasks that take hours, days, or weeks
- **Async task processing** - Background jobs without blocking API requests
- **Reliable retries** - Automatic retry with exponential backoff
- **Workflow visibility** - Track execution history and debug failures
- **Activity composition** - Break workflows into reusable activities
- **Saga pattern** - Implement compensating transactions

Temporal is ideal for FastAPI applications that need reliable background processing beyond simple task queues.

## When to Use Temporal

### ✅ Good Use Cases

**Long-running processes**:
- Order fulfillment workflows (payment → inventory → shipping)
- Multi-step approval processes
- Data synchronization between systems
- Scheduled report generation

**Reliable async tasks**:
- Sending emails with delivery confirmation
- External API calls with retries
- File processing and uploads
- Data migrations

**Complex orchestration**:
- Multi-service transactions (saga pattern)
- Human-in-the-loop workflows (waiting for approval)
- Conditional workflows with branching logic
- Parallel task execution

### ❌ When Not to Use Temporal

**Simple background tasks**:
- Use FastAPI BackgroundTasks for simple, fast tasks
- Example: Logging analytics events

**Real-time operations**:
- Temporal has ~10-100ms latency
- Use direct API calls for <10ms requirements

**Simple queues**:
- Use Redis pub/sub or Celery for basic job queues
- Temporal is heavier but more reliable

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   FastAPI API Server                    │
│                                                         │
│  POST /orders                                           │
│    ↓                                                    │
│  Start workflow → Temporal Client                       │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ gRPC/mTLS
                     ↓
┌─────────────────────────────────────────────────────────┐
│                  Temporal Server                        │
│                                                         │
│  • Workflow state management                            │
│  • Task queue distribution                              │
│  • Event history storage                                │
│  • Retry/timeout handling                               │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ Poll for tasks
                     ↓
┌─────────────────────────────────────────────────────────┐
│                 Temporal Workers                        │
│                                                         │
│  Worker 1 (task queue: email)                           │
│    • Execute workflows                                  │
│    • Run activities                                     │
│                                                         │
│  Worker 2 (task queue: processing)                      │
│    • Execute workflows                                  │
│    • Run activities                                     │
└─────────────────────────────────────────────────────────┘
```

**Key Components**:
1. **Client** - Starts workflows from FastAPI (in API server process)
2. **Server** - Manages workflow state (separate service/container)
3. **Workers** - Execute workflows and activities (separate process)

## Project Structure

```
src/app/worker/
├── __init__.py
├── main.py              # Worker entry point
├── registry.py          # Register workflows and activities
├── activities/          # Activity implementations
│   ├── __init__.py
│   ├── email.py         # Email sending activities
│   └── notifications.py # Notification activities
├── workflows/           # Workflow definitions
│   ├── __init__.py
│   ├── order.py         # Order fulfillment workflow
│   └── user.py          # User onboarding workflow
└── clients/             # Temporal client factory
    └── __init__.py
```

## Defining Activities

Activities are the building blocks of workflows - they perform actual work.

### Example: Email Activity

```python
# src/app/worker/activities/email.py
from datetime import timedelta
from temporalio import activity
from temporalio.common import RetryPolicy

@activity.defn(name="send_welcome_email")
async def send_welcome_email(user_id: int, email: str) -> str:
    """
    Send welcome email to new user
    
    Activities should be idempotent - safe to retry
    """
    activity.logger.info(f"Sending welcome email to {email}")
    
    try:
        # Actual email sending logic
        from src.app.core.services.email_service import EmailService
        
        email_service = EmailService()
        result = await email_service.send_welcome_email(
            to=email,
            user_id=user_id
        )
        
        activity.logger.info(f"Welcome email sent to {email}: {result}")
        return f"Email sent: {result}"
        
    except Exception as e:
        activity.logger.error(f"Failed to send email to {email}: {e}")
        raise  # Temporal will retry based on retry policy

@activity.defn(name="send_order_confirmation")
async def send_order_confirmation(order_id: int, email: str) -> str:
    """Send order confirmation email"""
    activity.logger.info(f"Sending order confirmation for {order_id} to {email}")
    
    from src.app.core.services.email_service import EmailService
    
    email_service = EmailService()
    result = await email_service.send_order_confirmation(
        to=email,
        order_id=order_id
    )
    
    return f"Confirmation sent: {result}"

@activity.defn(name="send_shipping_notification")
async def send_shipping_notification(order_id: int, email: str, tracking_number: str) -> str:
    """Send shipping notification email"""
    activity.logger.info(f"Sending shipping notification for {order_id}")
    
    from src.app.core.services.email_service import EmailService
    
    email_service = EmailService()
    result = await email_service.send_shipping_notification(
        to=email,
        order_id=order_id,
        tracking_number=tracking_number
    )
    
    return f"Shipping notification sent: {result}"
```

**Activity Best Practices**:
- **Idempotent** - Safe to run multiple times with same input
- **Short-lived** - Complete in seconds/minutes, not hours
- **Minimal state** - Pass simple parameters, not large objects
- **Retryable** - Raise exceptions for transient failures
- **Logged** - Use `activity.logger` for debugging

### Activity Retry Configuration

```python
from temporalio.common import RetryPolicy
from datetime import timedelta

# Default retry policy (configured per workflow)
retry_policy = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(seconds=100),
    backoff_coefficient=2.0,
    maximum_attempts=5,
)

# Activities inherit retry policy from workflow
# Can override per activity in workflow code
```

## Defining Workflows

Workflows orchestrate activities and define business logic.

### Example: Order Fulfillment Workflow

```python
# src/app/worker/workflows/order.py
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activity types
with workflow.unsafe.imports_passed_through():
    from src.app.worker.activities.email import (
        send_order_confirmation,
        send_shipping_notification
    )

@workflow.defn(name="OrderFulfillmentWorkflow")
class OrderFulfillmentWorkflow:
    """
    Multi-step order fulfillment workflow:
    1. Process payment
    2. Reserve inventory
    3. Send confirmation email
    4. Ship order
    5. Send shipping notification
    """
    
    @workflow.run
    async def run(
        self,
        order_id: int,
        user_email: str,
        product_ids: list[int],
        payment_method: str
    ) -> dict:
        """
        Execute order fulfillment workflow
        
        Returns:
            dict with status, order_id, tracking_number
        """
        workflow.logger.info(f"Starting order fulfillment for order {order_id}")
        
        # Step 1: Process payment
        payment_result = await workflow.execute_activity(
            "process_payment",
            args=[order_id, payment_method],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not payment_result["success"]:
            workflow.logger.error(f"Payment failed for order {order_id}")
            return {"status": "failed", "reason": "payment_failed"}
        
        # Step 2: Reserve inventory
        try:
            inventory_result = await workflow.execute_activity(
                "reserve_inventory",
                args=[product_ids],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
        except Exception as e:
            # Compensating transaction: refund payment
            workflow.logger.error(f"Inventory reservation failed, refunding payment")
            await workflow.execute_activity(
                "refund_payment",
                args=[payment_result["transaction_id"]],
                start_to_close_timeout=timedelta(seconds=30)
            )
            return {"status": "failed", "reason": "inventory_unavailable"}
        
        # Step 3: Send order confirmation email
        await workflow.execute_activity(
            send_order_confirmation,
            args=[order_id, user_email],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                maximum_attempts=10,
                initial_interval=timedelta(seconds=5)
            )
        )
        
        # Step 4: Ship order (may take hours/days)
        shipping_result = await workflow.execute_activity(
            "ship_order",
            args=[order_id, inventory_result["warehouse_id"]],
            start_to_close_timeout=timedelta(hours=24),  # Long timeout
            heartbeat_timeout=timedelta(minutes=5)
        )
        
        # Step 5: Send shipping notification
        await workflow.execute_activity(
            send_shipping_notification,
            args=[order_id, user_email, shipping_result["tracking_number"]],
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        workflow.logger.info(f"Order {order_id} fulfilled successfully")
        
        return {
            "status": "completed",
            "order_id": order_id,
            "tracking_number": shipping_result["tracking_number"]
        }
```

**Workflow Key Concepts**:

1. **Deterministic** - Must produce same result for same inputs
2. **Long-running** - Can execute for days/weeks/months
3. **Durable** - State persisted, survives worker restarts
4. **Versioning** - Can be updated while running workflows exist

### Workflow with Human Input (Signals)

```python
@workflow.defn(name="ApprovalWorkflow")
class ApprovalWorkflow:
    """
    Workflow that waits for human approval
    """
    
    def __init__(self):
        self.approved = False
        self.rejected = False
        self.approval_comment = ""
    
    @workflow.run
    async def run(self, request_id: int, request_data: dict) -> dict:
        """Wait for approval signal"""
        workflow.logger.info(f"Waiting for approval of request {request_id}")
        
        # Send notification to approvers
        await workflow.execute_activity(
            "send_approval_request_email",
            args=[request_id, request_data],
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Wait for approval signal (up to 7 days)
        await workflow.wait_condition(
            lambda: self.approved or self.rejected,
            timeout=timedelta(days=7)
        )
        
        if self.approved:
            workflow.logger.info(f"Request {request_id} approved: {self.approval_comment}")
            
            # Process approved request
            result = await workflow.execute_activity(
                "process_approved_request",
                args=[request_id],
                start_to_close_timeout=timedelta(minutes=5)
            )
            
            return {"status": "approved", "result": result}
        
        else:
            workflow.logger.info(f"Request {request_id} rejected: {self.approval_comment}")
            return {"status": "rejected", "comment": self.approval_comment}
    
    @workflow.signal
    def approve(self, comment: str = ""):
        """Signal to approve request"""
        self.approved = True
        self.approval_comment = comment
    
    @workflow.signal
    def reject(self, comment: str = ""):
        """Signal to reject request"""
        self.rejected = True
        self.approval_comment = comment
```

### Parallel Execution

```python
@workflow.defn(name="DataProcessingWorkflow")
class DataProcessingWorkflow:
    """Process multiple files in parallel"""
    
    @workflow.run
    async def run(self, file_paths: list[str]) -> dict:
        """Process files in parallel"""
        
        # Execute activities in parallel
        tasks = [
            workflow.execute_activity(
                "process_file",
                args=[file_path],
                start_to_close_timeout=timedelta(minutes=10)
            )
            for file_path in file_paths
        ]
        
        # Wait for all to complete
        results = await workflow.gather(*tasks)
        
        # Aggregate results
        total_records = sum(r["record_count"] for r in results)
        
        return {
            "status": "completed",
            "files_processed": len(results),
            "total_records": total_records
        }
```

## Worker Setup

Workers poll Temporal server and execute workflows/activities.

### Worker Configuration

```python
# src/app/worker/main.py
import asyncio
from temporalio.client import Client, TLSConfig
from temporalio.worker import Worker

from src.app.runtime.config import get_config
from src.app.worker.registry import get_workflows, get_activities

async def run_worker():
    """Start Temporal worker"""
    config = get_config()
    
    # Configure TLS (production)
    tls_config = None
    if config.temporal.tls_enabled:
        tls_config = TLSConfig(
            server_root_ca_cert=open(config.temporal.server_ca_cert, "rb").read(),
            client_cert=open(config.temporal.client_cert, "rb").read(),
            client_private_key=open(config.temporal.client_key, "rb").read(),
        )
    
    # Connect to Temporal
    client = await Client.connect(
        config.temporal.url,
        namespace=config.temporal.namespace,
        tls=tls_config,
    )
    
    # Get workflows and activities from registry
    workflows = get_workflows()
    activities = get_activities()
    
    # Create worker for task queue
    worker = Worker(
        client,
        task_queue="default",  # Can have multiple workers for different queues
        workflows=workflows,
        activities=activities,
        max_concurrent_workflow_tasks=100,
        max_concurrent_activities=50,
    )
    
    print(f"Starting Temporal worker for task queue: default")
    print(f"Registered {len(workflows)} workflows")
    print(f"Registered {len(activities)} activities")
    
    # Run worker (blocks)
    await worker.run()

def main():
    """Main entry point for worker"""
    asyncio.run(run_worker())

if __name__ == "__main__":
    main()
```

### Registry for Auto-discovery

```python
# src/app/worker/registry.py
import importlib
import pkgutil
from pathlib import Path

def get_workflows() -> list:
    """Auto-discover all workflow classes"""
    workflows = []
    
    workflows_path = Path(__file__).parent / "workflows"
    
    # Import all modules in workflows/ directory
    for _, module_name, _ in pkgutil.iter_modules([str(workflows_path)]):
        module = importlib.import_module(f"src.app.worker.workflows.{module_name}")
        
        # Find all workflow classes
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and hasattr(attr, "__temporal_workflow_definition")
            ):
                workflows.append(attr)
                print(f"Registered workflow: {attr.__name__}")
    
    return workflows

def get_activities() -> list:
    """Auto-discover all activity functions"""
    activities = []
    
    activities_path = Path(__file__).parent / "activities"
    
    # Import all modules in activities/ directory
    for _, module_name, _ in pkgutil.iter_modules([str(activities_path)]):
        module = importlib.import_module(f"src.app.worker.activities.{module_name}")
        
        # Find all activity functions
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if callable(attr) and hasattr(attr, "__temporal_activity_definition"):
                activities.append(attr)
                print(f"Registered activity: {attr.__name__}")
    
    return activities
```

### Multiple Task Queues

Run separate workers for different task types:

```python
# Worker 1: Email queue (high priority, many workers)
worker_email = Worker(
    client,
    task_queue="email",
    workflows=[],
    activities=[send_welcome_email, send_order_confirmation],
    max_concurrent_activities=100,
)

# Worker 2: Processing queue (low priority, resource-intensive)
worker_processing = Worker(
    client,
    task_queue="processing",
    workflows=[DataProcessingWorkflow],
    activities=[process_file, analyze_data],
    max_concurrent_activities=10,
)

# Run both workers
await asyncio.gather(
    worker_email.run(),
    worker_processing.run()
)
```

## Starting Workflows from FastAPI

### Temporal Client Setup

```python
# src/app/worker/clients/__init__.py
from temporalio.client import Client, TLSConfig
from src.app.runtime.config import get_config

_client = None

async def get_temporal_client() -> Client:
    """Get or create Temporal client (singleton)"""
    global _client
    
    if _client is None:
        config = get_config()
        
        tls_config = None
        if config.temporal.tls_enabled:
            tls_config = TLSConfig(
                server_root_ca_cert=open(config.temporal.server_ca_cert, "rb").read(),
                client_cert=open(config.temporal.client_cert, "rb").read(),
                client_private_key=open(config.temporal.client_key, "rb").read(),
            )
        
        _client = await Client.connect(
            config.temporal.url,
            namespace=config.temporal.namespace,
            tls=tls_config,
        )
    
    return _client
```

### Starting Workflow from API Endpoint

```python
# src/app/entities/order/router.py
from fastapi import APIRouter, Depends
from temporalio.client import Client

from src.app.worker.clients import get_temporal_client
from src.app.worker.workflows.order import OrderFulfillmentWorkflow
from .model import OrderCreate, OrderRead
from .service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("/", response_model=OrderRead)
async def create_order(
    order_data: OrderCreate,
    service: OrderService = Depends(get_order_service),
    temporal_client: Client = Depends(get_temporal_client)
) -> OrderRead:
    """
    Create order and start fulfillment workflow
    """
    # Create order in database
    order = service.create_order(order_data)
    
    # Start Temporal workflow (async, non-blocking)
    workflow_id = f"order-fulfillment-{order.id}"
    
    handle = await temporal_client.start_workflow(
        OrderFulfillmentWorkflow.run,
        args=[
            order.id,
            order.user_email,
            order.product_ids,
            order.payment_method
        ],
        id=workflow_id,
        task_queue="default",
    )
    
    # Store workflow ID for tracking
    service.update_order(order.id, {"workflow_id": workflow_id})
    
    return OrderRead.model_validate(order)
```

### Querying Workflow Status

```python
@router.get("/{order_id}/status")
async def get_order_status(
    order_id: int,
    service: OrderService = Depends(get_order_service),
    temporal_client: Client = Depends(get_temporal_client)
):
    """Get order fulfillment status from workflow"""
    order = service.get_order(order_id)
    
    if not order.workflow_id:
        return {"status": "no_workflow"}
    
    # Get workflow handle
    handle = temporal_client.get_workflow_handle(order.workflow_id)
    
    # Check if workflow is running
    try:
        description = await handle.describe()
        
        return {
            "order_id": order_id,
            "workflow_status": description.status.name,
            "start_time": description.start_time,
            "execution_time": description.execution_time,
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}
```

### Sending Signals to Workflows

```python
@router.post("/{order_id}/approve")
async def approve_order(
    order_id: int,
    comment: str,
    service: OrderService = Depends(get_order_service),
    temporal_client: Client = Depends(get_temporal_client)
):
    """Approve order (send signal to workflow)"""
    order = service.get_order(order_id)
    
    if not order.workflow_id:
        raise HTTPException(404, "No workflow found")
    
    # Get workflow handle
    handle = temporal_client.get_workflow_handle(order.workflow_id)
    
    # Send approval signal
    await handle.signal("approve", comment)
    
    return {"status": "signal_sent", "order_id": order_id}
```

## Configuration

### Development (docker-compose.dev.yml)

```yaml
temporal:
  image: temporalio/auto-setup:1.29.0
  container_name: api-forge-temporal-dev
  ports:
    - "7233:7233"
  environment:
    - DB=postgresql
    - DB_PORT=5432
    - POSTGRES_USER=devuser
    - POSTGRES_PWD=devpass
    - POSTGRES_SEEDS=postgres
  networks:
    - dev-network
```

### Production (docker-compose.prod.yml)

```yaml
temporal:
  image: temporalio/auto-setup:1.29.0
  environment:
    - TEMPORAL_TLS_REQUIRE_CLIENT_AUTH=true
    - TEMPORAL_TLS_SERVER_CA_CERT=/run/secrets/temporal_ca.crt
    - TEMPORAL_TLS_SERVER_CERT=/run/secrets/temporal_server.crt
    - TEMPORAL_TLS_SERVER_KEY=/run/secrets/temporal_server.key
  secrets:
    - temporal_server_cert
    - temporal_server_key
    - temporal_ca
  networks:
    - prod-network
```

### Application Configuration

```yaml
# config.yaml
temporal:
  url: ${TEMPORAL_URL:-localhost:7233}
  namespace: ${TEMPORAL_NAMESPACE:-default}
  tls_enabled: ${TEMPORAL_TLS_ENABLED:-false}
  client_cert: ${TEMPORAL_CLIENT_CERT:-/run/secrets/temporal_client.crt}
  client_key: ${TEMPORAL_CLIENT_KEY:-/run/secrets/temporal_client.key}
  server_ca_cert: ${TEMPORAL_SERVER_CA_CERT:-/run/secrets/temporal_ca.crt}
```

## Monitoring and Debugging

### Temporal Web UI

Access at http://localhost:8082 (development):

**Features**:
- View all workflows
- Search by workflow ID or status
- Inspect workflow execution history
- View activity inputs/outputs
- Retry failed workflows
- Cancel running workflows

### Workflow Logging

```python
# In workflows
workflow.logger.info("Processing step 1")
workflow.logger.error(f"Failed to process order {order_id}")

# In activities
activity.logger.info(f"Sending email to {email}")
activity.logger.warning("Rate limit approaching")
```

Logs appear in worker output and Temporal Web UI.

### Viewing Workflow History

```bash
# Using temporal CLI
temporal workflow show \
  --workflow-id order-fulfillment-123 \
  --namespace default

# Get execution history
temporal workflow showid \
  order-fulfillment-123 \
  --namespace default \
  --output json
```

## Testing Workflows

### Unit Testing Activities

```python
# tests/unit/worker/activities/test_email.py
import pytest
from src.app.worker.activities.email import send_welcome_email

@pytest.mark.asyncio
async def test_send_welcome_email(mocker):
    """Test email activity"""
    # Mock email service
    mock_email_service = mocker.patch(
        "src.app.core.services.email_service.EmailService.send_welcome_email"
    )
    mock_email_service.return_value = "email-id-123"
    
    result = await send_welcome_email(1, "test@example.com")
    
    assert "Email sent" in result
    mock_email_service.assert_called_once()
```

### Integration Testing Workflows

```python
# tests/integration/worker/workflows/test_order.py
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from src.app.worker.workflows.order import OrderFulfillmentWorkflow
from src.app.worker.activities.email import send_order_confirmation

@pytest.mark.asyncio
async def test_order_fulfillment_workflow():
    """Test order fulfillment workflow end-to-end"""
    
    async with await WorkflowEnvironment.start_time_skipping() as env:
        # Create worker for testing
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[OrderFulfillmentWorkflow],
            activities=[send_order_confirmation],  # Add all activities
        ):
            # Execute workflow
            result = await env.client.execute_workflow(
                OrderFulfillmentWorkflow.run,
                args=[1, "test@example.com", [101, 102], "credit_card"],
                id="test-workflow-1",
                task_queue="test",
            )
            
            assert result["status"] == "completed"
            assert "tracking_number" in result
```

## Best Practices

### 1. Keep Activities Idempotent

```python
# GOOD: Idempotent - safe to retry
@activity.defn
async def send_email(email_id: str, recipient: str):
    # Check if already sent
    if await email_service.is_sent(email_id):
        return "already_sent"
    
    await email_service.send(email_id, recipient)
    return "sent"

# BAD: Not idempotent - retry causes duplicate
@activity.defn
async def send_email(recipient: str):
    await email_service.send(recipient)  # No deduplication!
```

### 2. Use Heartbeats for Long Activities

```python
@activity.defn
async def process_large_file(file_path: str):
    """Process file with progress heartbeats"""
    records = await load_file(file_path)
    
    for i, record in enumerate(records):
        await process_record(record)
        
        # Send heartbeat every 100 records
        if i % 100 == 0:
            activity.heartbeat(f"Processed {i}/{len(records)}")
```

### 3. Handle Failures Gracefully

```python
@workflow.defn
class PaymentWorkflow:
    @workflow.run
    async def run(self, order_id: int):
        try:
            # Try primary payment processor
            result = await workflow.execute_activity(
                "process_payment_stripe",
                args=[order_id],
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
        except Exception:
            # Fallback to secondary processor
            result = await workflow.execute_activity(
                "process_payment_paypal",
                args=[order_id],
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
        
        return result
```

### 4. Version Workflows Carefully

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, data: dict):
        # Version check for compatibility
        version = workflow.get_version("add_new_step", 1, 2)
        
        if version == 1:
            # Old behavior
            await workflow.execute_activity("old_activity", args=[data])
        else:
            # New behavior
            await workflow.execute_activity("new_activity", args=[data])
```

## Related Documentation

- [FastAPI Docker Development Environment](./fastapi-docker-dev-environment.md) - Setting up Temporal locally
- [FastAPI Clean Architecture](./fastapi-clean-architecture-overview.md) - Integrating workflows with services
- [FastAPI Kubernetes Deployment](./fastapi-kubernetes-deployment.md) - Deploying Temporal workers to K8s

## Additional Resources

- [Temporal Documentation](https://docs.temporal.io/)
- [Temporal Python SDK](https://docs.temporal.io/dev-guide/python)
- [Temporal Samples](https://github.com/temporalio/samples-python)
- [Workflow Patterns](https://docs.temporal.io/workflows)
