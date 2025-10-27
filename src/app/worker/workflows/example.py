# worker/workflows/order_workflow.py
import asyncio
from datetime import timedelta
from typing import Any

from pydantic import BaseModel, EmailStr
from temporalio import workflow

from src.app.worker.activities.example import (
    PaymentInput,
    process_payment,
    send_notification,
)
from src.app.worker.registry import workflow_defn
from src.app.worker.workflows.base import BaseWorkflow, RetryPolicy


class OrderInput(BaseModel):
    """Input for order processing workflow."""

    order_id: str
    customer_email: EmailStr
    amount: float
    items: list[dict[str, Any]]


class OrderOutput(BaseModel):
    """Output from order processing workflow."""

    order_id: str
    status: str
    total_amount: float
    message: str


@workflow_defn(queue="example")
class OrderProcessingWorkflow(BaseWorkflow[OrderInput, OrderOutput]):
    """
    Order processing workflow with full type safety.

    Demonstrates:
    - Strongly typed workflow method
    - Signal handlers for external events
    - Query handlers for state inspection
    """

    def __init__(self) -> None:
        self._status: str = "initialized"
        self._cancelled: bool = False
        self._cancel_reason: str | None = None

    @workflow.run
    async def run(self, input: OrderInput) -> OrderOutput:
        """
        Main workflow execution method.

        Note: Return type is strongly typed with Pydantic model.
        """
        self._status = "processing"
        await asyncio.sleep(1)  # yield control to event loop

        try:
            # Check if cancelled before starting
            if self._cancelled:
                self._status = "cancelled"
                return OrderOutput(
                    order_id=input.order_id,
                    status="cancelled",
                    total_amount=0.0,
                    message=f"Order cancelled: {self._cancel_reason}",
                )

            # Execute payment activity with strong typing
            payment_result = await workflow.execute_activity(
                process_payment,
                PaymentInput(order_id=input.order_id, amount=input.amount),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(
                    maximum_attempts=3,
                    initial_interval=timedelta(seconds=1),
                    maximum_interval=timedelta(seconds=10),
                    backoff_coefficient=2.0,
                ),
            )

            # Check cancellation after payment
            if self._cancelled:
                self._status = "cancelled_after_payment"
                return OrderOutput(
                    order_id=input.order_id,
                    status="cancelled_after_payment",
                    total_amount=input.amount,
                    message=f"Order cancelled after payment: {self._cancel_reason}",
                )

            self._status = "payment_completed"

            # Send notification
            await workflow.execute_activity(
                send_notification,
                args=[
                    input.customer_email,
                    f"Order {input.order_id} processed successfully",
                ],
                start_to_close_timeout=timedelta(seconds=10),
            )

            self._status = "completed"

            return OrderOutput(
                order_id=input.order_id,
                status="completed",
                total_amount=input.amount,
                message=f"Order processed successfully. Transaction: {payment_result.transaction_id}",
            )

        except Exception as e:
            self._status = "failed"
            return OrderOutput(
                order_id=input.order_id,
                status="failed",
                total_amount=0.0,
                message=f"Order processing failed: {str(e)}",
            )

    @workflow.signal(name="cancel_order")
    def cancel_order(self, reason: str) -> None:
        """
        Signal handler to cancel the order.

        Note: Signals can be sent while workflow is running.
        """
        self._cancelled = True
        self._cancel_reason = reason
        self._status = f"cancelling: {reason}"

    @workflow.signal(name="update_status")
    async def update_status(self, new_status: str) -> None:
        """
        Signal handler to update status.

        Note: Signal handlers can be async if needed.
        """
        self._status = f"manual_update: {new_status}"

    @workflow.query(name="get_status")
    def get_status(self) -> str:
        """
        Query handler to get current status.

        Note: Queries are read-only and return immediately.
        """
        return self._status

    @workflow.query(name="is_cancelled")
    def is_cancelled(self) -> bool:
        """Query if the workflow has been cancelled."""
        return self._cancelled
