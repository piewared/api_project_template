# Temporal Workflow Engine

## Overview

[Temporal](https://temporal.io) is a durable execution platform that enables developers to build scalable, reliable distributed applications. It provides guarantees that workflows will complete successfully, even in the face of failures, timeouts, or infrastructure issues.

This application integrates Temporal to handle long-running, complex business processes that require reliability, visibility, and resilience.

## What is Temporal?

Temporal is fundamentally a **workflow orchestration engine** that solves the hardest problems in distributed systems:

- **Durable Execution**: Your code is guaranteed to run to completion, even if servers crash or network connections fail
- **Automatic Retries**: Failed operations are automatically retried with configurable backoff strategies
- **State Management**: Workflow state is automatically persisted and recovered
- **Visibility**: Full execution history and current state of all workflows through a web UI
- **Versioning**: Safe deployment of code changes to long-running workflows
- **Timers & Scheduling**: Built-in support for delays, timeouts, and scheduled execution

### Key Concepts

#### Workflows
Workflows are the coordination logic that orchestrates activities. They are:
- **Deterministic**: Must produce the same output given the same input
- **Durable**: State is automatically persisted and can survive process restarts
- **Versioned**: Can be safely updated while old versions are still running
- **Long-running**: Can execute for days, months, or years

In this application, workflows are implemented as classes that:
- Inherit from `BaseWorkflow[TInput, TReturn]` for type safety
- Are decorated with `@workflow_defn(queue="queue-name")`
- Define a `run()` method that implements the workflow logic
- Can define signals (external events) and queries (state inspection)

#### Activities
Activities are the actual work being done - external API calls, database operations, file I/O, etc. They are:
- **Non-deterministic**: Can have side effects and interact with external systems
- **Retryable**: Automatically retried on failure with configurable policies
- **Timeout-protected**: Have built-in timeout management
- **Heartbeat-capable**: Can report progress for long-running operations

In this application, activities are functions decorated with `@activity_defn(queue="queue-name")`.

#### Task Queues
Task queues are the routing mechanism between clients and workers:
- Clients submit workflows to specific task queues
- Workers poll task queues for work
- Multiple workers can share a task queue for load balancing
- Different queues can be used to segregate workload types

#### Workers
Workers are processes that:
- Poll task queues for workflows and activities to execute
- Execute workflow and activity code
- Report results back to the Temporal server
- Handle retries and error recovery

## Use Cases in This Application

Temporal is ideal for workflows that require any of the following characteristics:

### 1. **Multi-Step Business Processes**
Order processing, user onboarding, data pipelines, approval workflows - any process with multiple steps that must be coordinated and tracked.

**Example**: 
```python
# Order processing with payment, inventory, and shipping
@workflow_defn(queue="orders")
@workflow.defn
class OrderWorkflow(BaseWorkflow[OrderInput, OrderOutput]):
    async def run(self, input: OrderInput) -> OrderOutput:
        # Each step is an activity that can fail and retry independently
        payment = await self.execute_activity(charge_payment, input.payment_details)
        inventory = await self.execute_activity(reserve_inventory, input.items)
        shipping = await self.execute_activity(schedule_shipment, input.address)
        return OrderOutput(status="completed", tracking=shipping.tracking_number)
```

### 2. **Long-Running Operations**
Background jobs that take minutes, hours, or days - video processing, report generation, data migrations, batch operations.

**Why Temporal?**: Normal HTTP requests timeout. Background job queues lose state on restart. Temporal persists state and can resume after any failure.

### 3. **Operations Requiring Retries**
External API calls, payment processing, third-party integrations - anything that can temporarily fail and needs retry logic.

**Why Temporal?**: Instead of writing custom retry logic everywhere, Temporal provides configurable retry policies with exponential backoff, maximum attempts, and non-retryable error types.

### 4. **Scheduled Tasks**
Recurring jobs, delayed execution, time-based triggers - monthly reports, subscription renewals, reminder emails.

**Why Temporal?**: Built-in scheduling with `start_delay` and durable timers that survive server restarts.

### 5. **Workflows Requiring Visibility**
Operations where you need to see current status, execution history, or debug failed runs.

**Why Temporal?**: The Temporal Web UI provides full visibility into all workflow executions, their history, inputs/outputs, and failure reasons.

### 6. **Compensating Transactions (Sagas)**
Multi-service operations that need to be rolled back if any step fails - distributed transactions, booking systems, financial operations.

**Why Temporal?**: Workflow code can implement compensation logic cleanly, and Temporal ensures it runs even if the system crashes mid-rollback.

## Architecture

### High-Level Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   FastAPI App   │────────▶│ Temporal Client  │────────▶│ Temporal Server │
│                 │         │    (HTTP Deps)   │         │   (localhost)   │
└─────────────────┘         └──────────────────┘         └────────┬────────┘
                                                                   │
                                                                   │
                            ┌──────────────────────────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │    Workers    │
                    │  (Separate    │
                    │   Process)    │
                    └───────┬───────┘
                            │
                ┌───────────┴───────────┐
                │                       │
                ▼                       ▼
        ┌──────────────┐        ┌─────────────┐
        │  Workflows   │        │ Activities  │
        │  (Logic)     │        │  (Tasks)    │
        └──────────────┘        └─────────────┘
```

### Components in This Application

#### 1. **Temporal Server** (`temporal` container)
- Stores workflow state and execution history in PostgreSQL
- Coordinates workflow execution and activity scheduling
- Provides gRPC API for clients and workers
- Running on port `7233` internally (mapped to `7234` on host in development)

#### 2. **Temporal Client Service** (`src/app/core/services/temporal/temporal_client.py`)
- Singleton service that maintains a connection to Temporal server
- Injected as a FastAPI dependency via `get_temporal_service()`
- Handles connection lifecycle, retries, and health checks
- Provides methods to start/execute workflows

#### 3. **Worker Registry** (`src/app/worker/registry.py`)
- Automatic discovery of workflows and activities via decorators
- Maps task queues to their registered handlers
- Ensures type safety and queue consistency

#### 4. **Worker Manager** (`src/app/worker/manager.py`)
- Manages worker lifecycle (start, stop, graceful shutdown)
- Builds worker pools for each task queue
- Handles signals for graceful drain on shutdown

#### 5. **Base Workflow Class** (`src/app/worker/workflows/base.py`)
- Provides type-safe workflow execution methods
- Handles activity cancellation when workflows are cancelled
- Offers convenience methods for starting/executing workflows
- Loads timeout and retry configuration from `config.yaml`

#### 6. **Workflow & Activity Decorators**
- `@workflow_defn(queue="name")`: Registers workflows to a task queue
- `@activity_defn(queue="name")`: Registers activities to a task queue
- Ensures all handlers are discoverable and routable

## Implementation: Our Wrapper Design

### Motivation for the Wrapper

The Temporal Python SDK is powerful but verbose. Direct SDK usage requires:
- Manually tracking which workflows/activities belong to which queues
- Passing queue names as strings everywhere (not type-safe)
- Writing boilerplate for connection management
- Duplicating retry/timeout configuration across the codebase

Our wrapper provides:

#### 1. **Automatic Service Discovery**
Workflows and activities are automatically discovered via decorators. No manual registration needed.

```python
# Just decorate your classes/functions
@workflow_defn(queue="orders")
@workflow.defn
class OrderWorkflow(BaseWorkflow[OrderInput, OrderOutput]):
    ...

@activity_defn(queue="orders")
@activity.defn
async def charge_payment(payment_details: PaymentInput) -> PaymentOutput:
    ...
```

#### 2. **Type-Safe Workflow Execution**
Workflows inherit from `BaseWorkflow[TInput, TReturn]` with full type checking:

```python
# Type checker knows input and output types
result: OrderOutput = await OrderWorkflow.execute_workflow(
    client,
    input=OrderInput(order_id="123", amount=99.99),
    id="order-123"
)
# result.status is known to exist and be the correct type
```

#### 3. **Centralized Configuration**
All timeouts, retry policies, and connection settings are in `config.yaml`. No magic numbers scattered across code.

```yaml
temporal:
  workflows:
    execution_timeout_s: 86400  # 24 hours
    run_timeout_s: 7200         # 2 hours
    task_timeout_s: 10          # 10 seconds
  activities:
    start_to_close_timeout_s: 1200  # 20 minutes
    retry:
      maximum_attempts: 5
      backoff_coefficient: 2.0
```

#### 4. **FastAPI Integration**
The Temporal client is available as a FastAPI dependency:

```python
from src.app.api.http.deps import get_temporal_service

@router.post("/orders")
async def create_order(
    order_data: OrderInput,
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    handle = await OrderWorkflow.start_workflow(
        client,
        input=order_data,
        id=f"order-{order_data.order_id}"
    )
    return {"workflow_id": handle.id}
```

#### 5. **Graceful Shutdown**
Workers handle SIGINT/SIGTERM gracefully:
- Stop accepting new tasks
- Complete in-flight tasks (up to `drain_timeout`)
- Report completion before exiting

#### 6. **Activity Cancellation Support**
The `BaseWorkflow` class tracks all running activities and automatically cancels them when a workflow receives a cancellation signal:

```python
# In your workflow class
@workflow.signal
def custom_cancel_order(self, reason: str):
    # Call base class cancel() - it handles activity cleanup
    self.cancel()
    self._state["cancel_reason"] = reason
```

### Design Decisions

#### Why a Registry Pattern?
- **Single Source of Truth**: Task queue assignments are declared once at the decorator level
- **Compile-Time Checks**: TypeScript-style task queue validation (wrong queue = runtime error on startup, not during workflow execution)
- **Auto-Discovery**: Workers automatically know what workflows/activities they can handle

#### Why BaseWorkflow?
- **DRY Principle**: Common patterns (signals, queries, state management) in one place
- **Type Safety**: Generic type parameters ensure input/output types are consistent
- **Convenience**: Class methods for starting/executing workflows without repeating boilerplate

#### Why Separate Client Service?
- **Connection Pooling**: Single client connection shared across all requests
- **Health Checks**: Endpoint can query Temporal connectivity via `temporal_service.health_check()`
- **Lazy Loading**: Connection established on first use, not during app startup

## Development Workflow

### 1. Define a Workflow
```python
# src/app/worker/workflows/my_workflow.py
from src.app.worker.workflows.base import BaseWorkflow
from src.app.worker.registry import workflow_defn
from temporalio import workflow

@workflow_defn(queue="my-queue")
@workflow.defn
class MyWorkflow(BaseWorkflow[MyInput, MyOutput]):
    @workflow.run
    async def run(self, input: MyInput) -> MyOutput:
        # Your workflow logic here
        result = await self.execute_activity(some_activity, input.data)
        return MyOutput(result=result)
```

### 2. Define Activities
```python
# src/app/worker/activities/my_activities.py
from src.app.worker.registry import activity_defn
from temporalio import activity

@activity_defn(queue="my-queue")
@activity.defn
async def some_activity(data: str) -> str:
    # Your activity logic here
    return f"Processed: {data}"
```

### 3. Start the Worker
```bash
# In development (auto-reload enabled)
uv run python -m src.app.worker.main serve --queue my-queue

# Or all discovered queues
uv run python -m src.app.worker.main serve
```

### 4. Execute from FastAPI
```python
# In your route handler
from src.app.api.http.deps import get_temporal_service

@router.post("/trigger")
async def trigger_workflow(
    temporal_service: TemporalClientService = Depends(get_temporal_service)
):
    client = await temporal_service.get_client()
    
    # Option 1: Start and return immediately (non-blocking)
    handle = await MyWorkflow.start_workflow(
        client,
        input=MyInput(data="hello"),
        id="unique-workflow-id"
    )
    return {"workflow_id": handle.id}
    
    # Option 2: Wait for result (blocking)
    result = await MyWorkflow.execute_workflow(
        client,
        input=MyInput(data="hello"),
        id="unique-workflow-id"
    )
    return {"result": result.result}
```

## Key Benefits

✅ **Type Safety**: Full static type checking for inputs, outputs, and workflow methods  
✅ **Automatic Discovery**: No manual registration of workflows/activities  
✅ **Centralized Config**: All timeouts and retries configured in one place  
✅ **FastAPI Integration**: Temporal client available as a simple dependency  
✅ **Graceful Shutdown**: Workers drain cleanly on SIGTERM/SIGINT  
✅ **Activity Cancellation**: Automatic cleanup when workflows are cancelled  
✅ **Queue Validation**: Runtime checks ensure workflows execute on correct queues  
✅ **Developer Experience**: Clean API with minimal boilerplate  

## Next Steps

- [Configuration](./configuration.md) - Configure timeouts, retries, and connection settings
- [Usage Guide](./usage.md) - Learn how to execute workflows from FastAPI endpoints
- [Security](./security.md) - Understand security considerations and mTLS setup
- [Temporal Web UI](./temporal-web-ui.md) - Access the management interface
