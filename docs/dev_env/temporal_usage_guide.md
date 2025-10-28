# Temporal Workflow Engine - Usage Guide

## Overview

The Temporal Engine provides a user-friendly abstraction over Temporal.io for managing background tasks, workflows, and distributed processing in your FastAPI application.

## Quick Start

### 1. Initialize the Engine

In your FastAPI app startup:

```python
from src.app.core.services.tasks.temporal_engine import TemporalEngine

# Create a singleton instance
temporal = TemporalEngine()

@app.on_event("startup")
async def startup():
    await temporal.start()

@app.on_event("shutdown")
async def shutdown():
    await temporal.stop()
```

### 2. Define Activities

Activities are individual units of work that can be retried and monitored:

```python
@temporal.activities.register
async def send_email(to: str, subject: str, body: str) -> bool:
    """Send an email using your email service."""
    logger.info(f"Sending email to {to}")
    
    # Your email sending logic here
    # This can call external APIs, databases, etc.
    
    return True

@temporal.activities.register
async def charge_payment(user_id: str, amount: float) -> dict:
    """Charge a payment."""
    logger.info(f"Charging ${amount} to user {user_id}")
    
    # Payment processing logic
    
    return {
        "transaction_id": "txn_123",
        "status": "success"
    }
```

### 3. Define Workflows

Workflows orchestrate multiple activities with retry logic, timeouts, and state management:

```python
from temporalio import workflow
from datetime import timedelta

@temporal.workers.register_workflow
@workflow.defn
class OrderProcessingWorkflow:
    """Workflow to process an order from payment to fulfillment."""
    
    @workflow.run
    async def run(self, order_data: dict) -> dict:
        """
        Process an order with multiple steps.
        
        Args:
            order_data: Dict with user_id, items, total
            
        Returns:
            Dict with order status and details
        """
        order_id = order_data["order_id"]
        workflow.logger.info(f"Processing order: {order_id}")
        
        # Step 1: Charge payment
        payment_result = await workflow.execute_activity(
            charge_payment,
            args=[order_data["user_id"], order_data["total"]],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=workflow.RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
            )
        )
        
        # Step 2: Reserve inventory
        inventory_result = await workflow.execute_activity(
            reserve_inventory,
            args=[order_data["items"]],
            start_to_close_timeout=timedelta(seconds=20)
        )
        
        # Step 3: Send confirmation email
        await workflow.execute_activity(
            send_email,
            args=[
                order_data["email"],
                "Order Confirmed",
                f"Your order {order_id} is confirmed!"
            ],
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        return {
            "order_id": order_id,
            "status": "completed",
            "transaction_id": payment_result["transaction_id"]
        }
```

### 4. Execute Workflows from API Endpoints

#### Synchronous Execution (wait for result)

```python
@app.post("/orders")
async def create_order(order: OrderRequest) -> OrderResponse:
    """Create and process an order."""
    
    # Execute workflow and wait for completion
    result = await temporal.workflows.execute(
        "OrderProcessingWorkflow",
        args={
            "order_id": str(uuid.uuid4()),
            "user_id": order.user_id,
            "items": order.items,
            "total": order.total,
            "email": order.email
        },
        workflow_id=f"order-{order.user_id}-{int(time.time())}",
        timeout_seconds=300  # 5 minute timeout
    )
    
    return OrderResponse(
        order_id=result["order_id"],
        status=result["status"],
        transaction_id=result["transaction_id"]
    )
```

#### Asynchronous Execution (fire and forget)

```python
@app.post("/orders/async")
async def create_order_async(order: OrderRequest) -> dict:
    """Create an order for background processing."""
    
    order_id = str(uuid.uuid4())
    
    # Start workflow without waiting
    handle = await temporal.workflows.start(
        "OrderProcessingWorkflow",
        args={
            "order_id": order_id,
            "user_id": order.user_id,
            "items": order.items,
            "total": order.total,
            "email": order.email
        },
        workflow_id=f"order-{order_id}"
    )
    
    return {
        "order_id": order_id,
        "workflow_id": handle.id,
        "message": "Order is being processed"
    }
```

#### Check Workflow Status

```python
@app.get("/orders/{order_id}/status")
async def get_order_status(order_id: str) -> dict:
    """Get the status of an order workflow."""
    
    workflow_id = f"order-{order_id}"
    
    try:
        status = await temporal.workflows.get_status(workflow_id)
        
        return {
            "order_id": order_id,
            "workflow_status": status.status.value,
            "workflow_type": status.workflow_type,
            "start_time": status.start_time,
            "close_time": status.close_time
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Order not found: {str(e)}")
```

#### Get Workflow Result

```python
@app.get("/orders/{order_id}/result")
async def get_order_result(order_id: str) -> dict:
    """Get the result of a completed order workflow."""
    
    workflow_id = f"order-{order_id}"
    
    try:
        result = await temporal.workflows.get_result(
            workflow_id,
            timeout_seconds=30
        )
        
        return result
    except TimeoutError:
        return {"status": "still_processing"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 5. Scheduled/Delayed Tasks

Schedule a task to run in the future:

```python
@app.post("/reminders")
async def schedule_reminder(reminder: ReminderRequest) -> dict:
    """Schedule a reminder to be sent later."""
    
    # Send reminder in 24 hours
    handle = await temporal.workflows.schedule(
        "SendReminderWorkflow",
        args={
            "user_id": reminder.user_id,
            "message": reminder.message
        },
        delay_seconds=86400,  # 24 hours
        workflow_id=f"reminder-{reminder.user_id}-{int(time.time())}"
    )
    
    return {
        "reminder_id": handle.id,
        "scheduled_for": datetime.now() + timedelta(days=1)
    }
```

### 6. Cancel a Running Workflow

```python
@app.delete("/orders/{order_id}")
async def cancel_order(order_id: str) -> dict:
    """Cancel an order that's being processed."""
    
    workflow_id = f"order-{order_id}"
    
    try:
        await temporal.workflows.cancel(workflow_id)
        
        return {
            "order_id": order_id,
            "status": "cancelled"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel: {str(e)}")
```

## Advanced Patterns

### Pattern 1: Long-Running Data Processing

```python
@temporal.activities.register
async def process_batch(batch_id: str, records: list) -> dict:
    """Process a batch of records."""
    processed = 0
    failed = 0
    
    for record in records:
        try:
            # Process each record
            await process_single_record(record)
            processed += 1
        except Exception as e:
            logger.error(f"Failed to process record: {e}")
            failed += 1
    
    return {"processed": processed, "failed": failed}

@temporal.workers.register_workflow
@workflow.defn
class DataProcessingWorkflow:
    """Process large datasets in parallel batches."""
    
    @workflow.run
    async def run(self, dataset_id: str, batch_size: int = 100) -> dict:
        """Process dataset in parallel batches."""
        
        # Get total records (this would query your DB)
        total_records = await workflow.execute_activity(
            get_record_count,
            args=[dataset_id],
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # Process in parallel batches
        batch_count = (total_records + batch_size - 1) // batch_size
        results = []
        
        for batch_num in range(batch_count):
            result = await workflow.execute_activity(
                process_batch,
                args=[f"{dataset_id}-batch-{batch_num}"],
                start_to_close_timeout=timedelta(minutes=10)
            )
            results.append(result)
        
        total_processed = sum(r["processed"] for r in results)
        total_failed = sum(r["failed"] for r in results)
        
        return {
            "dataset_id": dataset_id,
            "total_records": total_records,
            "processed": total_processed,
            "failed": total_failed
        }
```

### Pattern 2: Human-in-the-Loop Approval

```python
from temporalio import workflow

@temporal.workers.register_workflow
@workflow.defn
class ApprovalWorkflow:
    """Workflow that waits for human approval."""
    
    def __init__(self):
        self._approved = False
        self._rejection_reason = None
    
    @workflow.run
    async def run(self, request_data: dict) -> dict:
        """Wait for approval with timeout."""
        
        # Send approval request
        await workflow.execute_activity(
            send_approval_request,
            args=[request_data],
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Wait for approval (up to 24 hours)
        try:
            approved = await workflow.wait_condition(
                lambda: self._approved or self._rejection_reason is not None,
                timeout=timedelta(hours=24)
            )
        except asyncio.TimeoutError:
            # Auto-reject after timeout
            return {"status": "timeout", "approved": False}
        
        if self._approved:
            # Execute approved action
            result = await workflow.execute_activity(
                execute_approved_action,
                args=[request_data],
                start_to_close_timeout=timedelta(minutes=5)
            )
            return {"status": "approved", "result": result}
        else:
            return {
                "status": "rejected",
                "reason": self._rejection_reason
            }
    
    @workflow.signal
    async def approve(self):
        """Signal to approve the request."""
        self._approved = True

    @workflow.signal
    async def reject(self, reason: str):
        """Signal to reject the request."""
        self._rejection_reason = reason

    @workflow.query
    def is_approved(self) -> bool:
        """Query to check if request has been approved."""
        return self._approved

    @workflow.query
    def get_rejection_reason(self) -> str | None:
        """Query to get rejection reason if rejected."""
        return self._rejection_reason# API endpoint to approve/reject
@app.post("/approvals/{workflow_id}/approve")
async def approve_request(workflow_id: str):
    """Approve a pending request."""
    # Use the convenience API for sending signals
    await temporal.workflows.signal(workflow_id, "approve")
    return {"status": "approved"}

@app.post("/approvals/{workflow_id}/reject")
async def reject_request(workflow_id: str, reason: str):
    """Reject a pending request."""
    # Use the convenience API for sending signals
    await temporal.workflows.signal(workflow_id, "reject", reason)
    return {"status": "rejected"}

# Query workflow state
@app.get("/approvals/{workflow_id}/is_approved")
async def check_approval_status(workflow_id: str):
    """Check if a request has been approved (using query)."""
    # Queries allow reading workflow state without modifying it
    is_approved = await temporal.workflows.query(workflow_id, "is_approved")
    return {"approved": is_approved}
```

### Pattern 3: Saga Pattern (Distributed Transactions)

```python
@temporal.workers.register_workflow
@workflow.defn
class BookingS agaWorkflow:
    """Saga pattern for booking with compensating transactions."""
    
    @workflow.run
    async def run(self, booking_data: dict) -> dict:
        """Execute booking with automatic rollback on failure."""
        
        compensations = []
        
        try:
            # Step 1: Reserve hotel
            hotel_result = await workflow.execute_activity(
                reserve_hotel,
                args=[booking_data["hotel_id"]],
                start_to_close_timeout=timedelta(seconds=30)
            )
            compensations.append(("cancel_hotel", [hotel_result["reservation_id"]]))
            
            # Step 2: Reserve flight
            flight_result = await workflow.execute_activity(
                reserve_flight,
                args=[booking_data["flight_id"]],
                start_to_close_timeout=timedelta(seconds=30)
            )
            compensations.append(("cancel_flight", [flight_result["reservation_id"]]))
            
            # Step 3: Charge payment
            payment_result = await workflow.execute_activity(
                charge_payment,
                args=[booking_data["user_id"], booking_data["total"]],
                start_to_close_timeout=timedelta(seconds=30)
            )
            
            return {
                "status": "success",
                "hotel_reservation": hotel_result,
                "flight_reservation": flight_result,
                "payment": payment_result
            }
            
        except Exception as e:
            # Run compensating transactions in reverse order
            workflow.logger.error(f"Booking failed, running compensations: {e}")
            
            for activity_name, args in reversed(compensations):
                try:
                    await workflow.execute_activity(
                        activity_name,
                        args=args,
                        start_to_close_timeout=timedelta(seconds=30)
                    )
                except Exception as comp_error:
                    workflow.logger.error(f"Compensation failed: {comp_error}")
            
            return {
                "status": "failed",
                "error": str(e),
                "compensations_executed": len(compensations)
            }
```

## Health Monitoring

Add a health check endpoint:

```python
@app.get("/health")
async def health_check():
    """Check application and Temporal health."""
    
    temporal_health = temporal.health_check()
    
    return {
        "status": "healthy" if temporal.is_ready else "degraded",
        "temporal": temporal_health,
        "timestamp": datetime.now().isoformat()
    }
```

## Configuration

Temporal is configured via `config.yaml`:

```yaml
temporal:
  enabled: true
  url: "temporal:7233"  # Temporal server URL
  namespace: "default"  # Temporal namespace
  task_queue: "default"  # Default task queue name
  worker:
    enabled: true  # Start worker automatically
    activities_per_second: 10
    max_concurrent_activities: 100
    max_concurrent_workflows: 100
```

## Best Practices

1. **Activity Idempotency**: Make activities idempotent so they can be safely retried
2. **Workflow IDs**: Use meaningful, unique workflow IDs for tracking
3. **Timeouts**: Always set appropriate timeouts for activities
4. **Error Handling**: Use try/catch in workflows and handle failures gracefully
5. **Logging**: Use workflow.logger in workflows for Temporal-aware logging
6. **Testing**: Test activities and workflows independently before integration

## Debugging

### View Workflow History

Use the Temporal Web UI at http://localhost:8081 (in development) to:
- View workflow execution history
- See activity results
- Debug failures
- Replay workflows

### Enable Debug Logging

```python
import logging
logging.getLogger("temporalio").setLevel(logging.DEBUG)
```

## Common Issues

### Issue: "Workflow not found"
**Solution**: Ensure the workflow is registered before starting the engine

### Issue: Activities timeout
**Solution**: Increase `start_to_close_timeout` or optimize activity code

### Issue: Worker not processing tasks
**Solution**: Check worker is enabled in config and task queue names match

## Next Steps

- Read [Temporal Documentation](https://docs.temporal.io/)
- Explore example workflows in `examples/workflows/`
- Set up monitoring and alerting for production
- Configure mTLS for production Temporal clusters
