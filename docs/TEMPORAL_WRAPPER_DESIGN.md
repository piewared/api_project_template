# Temporal Wrapper Design & Implementation Guide (Revised)

## Table of Contents

* [Overview](#overview)
* [Design Goals](#design-goals)
* [Architecture](#architecture)
* [Implementation Details](#implementation-details)
* [Usage Guide](#usage-guide)
* [Advanced Features](#advanced-features)
* [Best Practices](#best-practices)
* [Testing](#testing)
* [Troubleshooting](#troubleshooting)
* [Migration from Traditional Temporal](#migration-from-traditional-temporal)
* [Conclusion](#conclusion)

---

## Overview

This document describes the design, implementation, and usage of our custom Temporal wrapper located in `src/infra/temporal_runtime.py`. The wrapper provides a clean, type-safe abstraction over Temporal’s workflow engine, eliminating boilerplate and preventing Temporal-specific code from leaking into your business logic.

### Key Principle: Zero Temporal Leakage

Your workflows and activities look like regular Python classes and functions—no `@workflow.defn` decorators, no direct `workflow.execute_activity` calls, and no Temporal imports in your business logic. The wrapper hides those details.

---

## Design Goals

### 1) Clean Business Logic

Focus on business logic; the wrapper handles infrastructure:

```python
class MyWorkflow(Workflow):
    async def process(self, data: ProcessInput) -> ProcessResult:
        result = await self.exec(process_activity, data, timeout=30)
        return result
```

### 2) Strong Type Safety

* Python **3.12+** (PEP 695) type parameter syntax for generics/overloads.
* Pydantic models validate all activity I/O.
* IDEs and static checkers (pyright/mypy) see real method signatures.

### 3) Simplified API

Three execution styles cover most cases:

* **Immediate (await result):** `await wf.my_method(args)`
* **Async / fire-and-forget:** `await wf.async_.my_method(args)` → returns handle
* **Delayed start:** `await wf.after(3600).my_method(args)`

### 4) Automatic Registration

* Workflows auto-register via a metaclass.
* Activities register via a single decorator.

### 5) Signal/Query Support

Use `@wf_signal("name")` and `@wf_query("name")` on workflow methods—no Temporal imports.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Your Application Code                      │
│  (Pure Python - no Temporal imports)                        │
│                                                             │
│  class MyWorkflow(Workflow):                                │
│      async def process(self, data: Input) -> Output:        │
│          result = await self.exec(activity, data, timeout=30)│
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Temporal Wrapper                          │
│  (src/infra/temporal_runtime.py)                             │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Workflow     │  │ Activity     │  │ Temporal     │      │
│  │ Metaclass    │  │ Registry     │  │ Engine       │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                             │
│  ┌──────────────────────────────────────────────────┐       │
│  │   Client Proxy (Dynamic Method Routing)          │       │
│  └──────────────────────────────────────────────────┘       │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   Temporal.io SDK                            │
│  (Distributed execution, durability, retries)               │
└─────────────────────────────────────────────────────────────┘
```

**Key Components**

1. **`Workflow` Base Class** — what your workflows inherit from.
2. **`_WorkflowMeta` Metaclass** — auto-registers workflows and creates hidden Temporal adapters.
3. **`activity_def` Decorator** — registers activities with type-safe DTO handling.
4. **`TemporalEngine`** — manages client connection and worker lifecycle.
5. **Client Proxy** — dynamic method routing with signature preservation.
6. **`MethodHandle`** — wrapper around `WorkflowHandle` with convenience helpers.

---

## Implementation Details

### 1) Activities (DTO-first, strongly typed)

Activities use Pydantic DTOs for input and (optionally) output. The decorator returns a typed **handle** used by workflows.

```python
from pydantic import BaseModel

class SendEmailArgs(BaseModel):
    to: str
    subject: str
    body: str

class SendEmailResult(BaseModel):
    message_id: str
    sent_at: str

send_email = activity_def(
    "send_email",
    Args=SendEmailArgs,
    Result=SendEmailResult,  # omit if returning primitive/None
)(send_email_impl)
```

**How it works**

* The decorator registers a Temporal activity entrypoint that validates input (`Args`) and, when provided, validates/normalizes output (`Result`).
* A per-process `_ACTIVITY_REGISTRY` stores metadata used to start the Worker.
* Overloads ensure `Workflow.exec(...)` returns the correct static type:

  * If `Result` is declared, the return type is that model.
  * Otherwise, it returns the activity’s primitive/None result.

### 2) Workflow Metaclass

Declaring a workflow class triggers auto-registration and adapter generation:

```python
class MyWorkflow(Workflow):
    async def process(self, data: Input) -> Output:
        ...
```

**Behind the scenes**

1. Registers the class (guards against duplicate names).
2. Builds an internal `@_twf.defn(name=wf_name)` **adapter** with a single `_run(payload)` method. The payload shape is `{"method": "<name>", "kwargs": {...}}`; the adapter dispatches to your method.
3. Scans for `@wf_signal` and `@wf_query` methods and dynamically attaches Temporal signal/query handlers to the adapter.

> **Note:** In the current adapter, queries are implemented as `async def`. You can support sync queries by detecting non-coroutines and calling without `await`.

### 3) Client Proxy Pattern

`Workflow.client(engine)` returns a proxy that exposes the **same methods** as your workflow. Calling one:

1. Captures the method name.
2. Binds `*args/**kwargs` to names (fills defaults).
3. Invokes `engine.execute_method(...)` with the payload.
4. Preserves the original method signature for IDEs/type checkers.

### 4) Execution Patterns

* **Immediate:** `await wf.method(...)` → `engine.execute_method(...)` (start + wait).
* **Async:** `await wf.async_.method(...)` → `engine.start_method(...)` (returns `MethodHandle`).
* **Delayed:** `await wf.after(SECONDS).method(...)` → start with `start_delay`.

### 5) Signals & Queries

Decorate workflow methods:

```python
class ApprovalWorkflow(Workflow):
    def __init__(self) -> None:
        self._approved = False

    @wf_signal("approve")
    async def approve(self) -> None:
        self._approved = True

    @wf_query("is_approved")
    async def is_approved(self) -> bool:
        return self._approved

    async def process(self, request: Request) -> Result:
        await self.wait_until(lambda: self._approved)
        return Result(status="approved")
```

**Usage**

```python
handle = await ApprovalWorkflow.client(engine).async_.process(request)
await handle.signal("approve")
approved = await handle.query("is_approved")
```

### 6) Optional Zero-Leak Helpers

To avoid importing Temporal in workflows, the base class can expose:

```python
class Workflow(...):
    async def sleep(self, seconds: float) -> None:
        await _twf.sleep(seconds)

    async def wait_until(self, predicate: Callable[[], bool]) -> None:
        await _twf.wait_condition(predicate)
```

---

## Usage Guide

### 1) Initialize the Engine

```python
from src.infra.temporal_runtime import TemporalEngine
from fastapi import FastAPI

engine = TemporalEngine(
    url="localhost:7233",
    namespace="default",
    task_queue="my-task-queue",
    start_worker=True,  # start Worker in this process
)

# IMPORTANT: import modules that define activities/workflows BEFORE engine.start()
import src.features.email.workflow_email_campaign  # noqa: F401

app = FastAPI()

@app.on_event("startup")
async def startup():
    await engine.start()

@app.on_event("shutdown")
async def shutdown():
    await engine.stop()
```

### 2) Define Activities

```python
from pydantic import BaseModel
from src.infra.temporal_runtime import activity_def

class ProcessDataInput(BaseModel):
    data_id: str
    parameters: dict[str, Any]

class ProcessDataOutput(BaseModel):
    result: str
    processed_at: str

async def process_data_impl(args: ProcessDataInput) -> ProcessDataOutput:
    # business logic...
    return ProcessDataOutput(result="ok", processed_at=datetime.now().isoformat())

process_data = activity_def(
    "process_data",
    Args=ProcessDataInput,
    Result=ProcessDataOutput,
)(process_data_impl)
```

### 3) Define Workflows

```python
from temporalio.common import RetryPolicy
from src.infra.temporal_runtime import Workflow

class DataPipelineWorkflow(Workflow):
    async def run_pipeline(self, input_data: ProcessDataInput) -> ProcessDataOutput:
        result = await self.exec(
            process_data,
            input_data,
            timeout=300,  # 5 minutes
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        # more business logic...
        return result
```

### 4) Execute Workflows

```python
pipeline = DataPipelineWorkflow.client(engine)

# Immediate
result = await pipeline.run_pipeline(ProcessDataInput(data_id="123", parameters={"mode": "fast"}))

# Async
handle = await pipeline.async_.run_pipeline(ProcessDataInput(data_id="456", parameters={"mode": "batch"}))
result = await handle.result(timeout=60.0)

# Delayed
handle = await pipeline.after(3600).run_pipeline(ProcessDataInput(data_id="789", parameters={"mode": "scheduled"}))
```

### 5) Signals & Queries

```python
class OrderProcessingWorkflow(Workflow):
    def __init__(self) -> None:
        self._status = "pending"
        self._items_processed = 0
        self._paused = False
        self._cancelled = False

    @wf_signal("cancel")
    async def cancel(self, reason: str) -> None:
        self._cancelled = True
        self._status = f"cancelled: {reason}"

    @wf_signal("pause")
    async def pause(self) -> None:
        self._paused = True

    @wf_signal("resume")
    async def resume(self) -> None:
        self._paused = False

    @wf_query("status")
    async def status(self) -> str:
        return self._status

    @wf_query("progress")
    async def progress(self) -> dict[str, int | str]:
        return {"status": self._status, "items_processed": self._items_processed}

    async def process_order(self, order: Order) -> OrderResult:
        self._status = "processing"
        for item in order.items:
            await self.wait_until(lambda: not self._paused)
            if self._cancelled:
                return OrderResult(status=self._status)
            await self.exec(process_item, item, timeout=60)
            self._items_processed += 1
        self._status = "completed"
        return OrderResult(status=self._status, items=self._items_processed)

# Use
client = OrderProcessingWorkflow.client(engine)
handle = await client.async_.process_order(order_data)
await handle.signal("pause")
prog = await handle.query("progress")
await handle.signal("resume")
await engine.signal(handle.id, "cancel", "Customer request")
final = await engine.query(handle.id, "status")
```

---

## Advanced Features

### 1) Retry Policies

```python
from temporalio.common import RetryPolicy

retry_policy = RetryPolicy(
    maximum_attempts=5,
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(seconds=60),
    backoff_coefficient=2.0,
)

result = await self.exec(
    risky_activity,
    args,
    timeout=300,
    retry_policy=retry_policy,
)
```

### 2) Workflow ID Conflict Handling

```python
from temporalio.common import WorkflowIDConflictPolicy

# Fail if ID exists
handle = await engine.start_method(
    MyWorkflow, "process", workflow_id="unique-123",
    id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
)

# Use existing workflow if ID matches
handle = await engine.start_method(
    MyWorkflow, "process", workflow_id="idempotent-id",
    id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
)
```

### 3) Multiple Methods per Workflow

```python
class MultiMethodWorkflow(Workflow):
    async def method_a(self, a: InputA) -> OutputA: ...
    async def method_b(self, b: InputB) -> OutputB: ...
    async def method_c(self, c: InputC) -> OutputC: ...
```

Call independently:

```python
wf = MultiMethodWorkflow.client(engine)
result_a = await wf.method_a(data_a)
handle_c = await wf.async_.method_c(data_c)
```

### 4) Lifecycle Management

```python
status = await engine.get_status(workflow_id)
await engine.cancel(workflow_id)              # graceful
await engine.terminate(workflow_id, "reason") # immediate
try:
    res = await engine.get_result(workflow_id, timeout_seconds=30)
except TimeoutError:
    ...
```

---

## Best Practices

### 1) Use Pydantic Models for Activity I/O

```python
class SendEmailInput(BaseModel):
    to: EmailStr
    subject: str
    body: str
    cc: list[EmailStr] = []
```

### 2) Keep Workflows Deterministic

* No randomness/real time/system I/O in control flow.
* Use workflow input/state or signals to branch deterministically.

### 3) Always Set Timeouts

* Activities: `timeout` on every `exec(...)`.
* Workflows: consider `execution_timeout` when starting.

### 4) Meaningful Workflow IDs

* Compose IDs with domain identifiers (e.g., `order-{order_id}-{user_id}`).

### 5) Handle Failures Gracefully

* Catch and compensate inside workflows; surface meaningful errors.

### 6) Prefer Signals for External Events

* Pause/resume/cancel/approve: model them as signals.

### 7) Document Workflow Behavior

* Docstrings listing major steps, signals, queries, and idempotency guidance.

---

## Testing

### Unit Tests (no Temporal)

* Instantiate workflow classes directly.
* Mock `exec`, `sleep`, `wait_until` as needed.

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_workflow_logic():
    wf = MyWorkflow()
    with patch.object(wf, "exec", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = ExpectedOutput(result="success")
        out = await wf.process(input_data)
        assert out.result == "success"
        mock_exec.assert_called_once()
```

### Integration Tests (Temporal)

* Import workflow/activity modules **before** `engine.start()` so registries are populated.
* Use a test namespace/task queue.

```python
@pytest.mark.asyncio
async def test_workflow_execution():
    engine = TemporalEngine(url="localhost:7233", namespace="test", task_queue="test-queue")
    import myproj.features.sample.workflows  # ensure registration
    await engine.start()
    try:
        wf = MyWorkflow.client(engine)
        result = await wf.process(test_input)
        assert result.status == "completed"
    finally:
        await engine.stop()
```

---

## Troubleshooting

**“Activity not registered”**

* The module that calls `activity_def(...)` must be imported before `engine.start()`.

**“Workflow not found”**

* Class must inherit `Workflow`.
* Import the module before starting the engine.
* Ensure workflow names are unique (duplicate names are rejected at class creation).

**“Signal/query not working”**

* Names must match exactly.
* With the current adapter, implement both as `async def`.
  *(If you prefer sync queries, extend the adapter to detect and call sync functions.)*

**“Type errors with `exec()`”**

* Pass a DTO **instance** for `Args`.
* If you declared `Result=Model`, `exec(...)` returns that model; otherwise it returns the primitive/None result of the activity.

---

## Migration from Traditional Temporal

### Before

```python
from temporalio import workflow, activity

@activity.defn
async def my_activity(data: dict) -> dict: ...

@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, data: dict) -> dict:
        return await workflow.execute_activity(my_activity, args=[data], start_to_close_timeout=timedelta(seconds=30))
```

### After

```python
from pydantic import BaseModel
from src.infra.temporal_runtime import Workflow, activity_def

class MyActivityInput(BaseModel): ...
class MyActivityOutput(BaseModel): ...

@activity_def("my_activity", Args=SendEmailArgs, Result=SendEmailResult)
async def my_activity(args: MyActivityInput) -> MyActivityOutput: ...

class MyWorkflow(Workflow):
    async def run(self, data: MyActivityInput) -> MyActivityOutput:
        return await self.exec(my_activity, data, timeout=30)
```

---

## Conclusion

This wrapper provides a **Pythonic, type-safe** way to build Temporal workflows:

* Plain classes with custom async methods.
* DTO-typed activities with runtime validation.
* Zero Temporal leakage in business logic.
* Clean client ergonomics (immediate/async/delayed).
* Full support for signals/queries, status, cancellation, termination, and results.

**Operational note:** always import modules that define activities/workflows **before** `engine.start()` so the per-process registries are populated for the Worker.
