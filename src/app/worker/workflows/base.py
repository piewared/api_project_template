# worker/workflows/base.py
from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any, Self

from temporalio import workflow
from temporalio.client import Client, WorkflowHandle
from temporalio.common import RetryPolicy

DEFAULT_ACTIVITY_OPTS = {
    # Per-attempt max run time (required for activities)
    "start_to_close_timeout": timedelta(minutes=4, seconds=50),

    # Total time across all retries; optional but recommended
    "schedule_to_close_timeout": timedelta(minutes=5),

    # Retries: use common.RetryPolicy, not workflow.RetryPolicy
    "retry_policy": RetryPolicy(
        maximum_attempts=5,
        non_retryable_error_types=["ValidationError"],
        # optional knobs:
        # initial_interval=timedelta(seconds=1),
        # backoff_coefficient=2.0,
        # maximum_interval=timedelta(seconds=60),
    ),
}


class BaseWorkflow[TArgs, TReturn](ABC):
    # common signal/query patterns

    def __init__(self) -> None:
        self._state: dict[str, Any] = {}

    @workflow.run
    @abstractmethod
    async def run(self, input: TArgs) -> TReturn:
        ...

    @workflow.query
    def state(self) -> dict: return self._state

    @workflow.signal
    def cancel(self): self._state["cancelled"] = True

    @classmethod
    async def start_workflow(
        cls: type[Self],
        client: Client,
        input: TArgs,
        id: str,
        **temporal_kwargs,
    ) -> WorkflowHandle[Self, TReturn]:
        """
        Start a workflow execution asynchronously and return its handle. Handle can be used
        to query or signal the running workflow, or to wait for its completion with handle.result().

        Args:
            client: Connected Temporal client instance
            input: Input data for the workflow (type-checked)
            id: Unique workflow ID (used for deduplication)
            **temporal_kwargs: Additional arguments to pass to client.start_workflow
                              (e.g., task_timeout, retry_policy, memo, search_attributes)

        Returns:
            WorkflowHandle for querying/signaling the running workflow

        Raises:
            ValueError: If workflow_type has no declared queue

        Example:
            handle = await WorkflowType.start_workflow(
                client,
                OrderWorkflow,
                input=OrderInput(order_id="123", items=[...]),
                id="order-123",
                execution_timeout=timedelta(hours=1)
            )
            result = await handle.result()
        """
        q = getattr(cls, "__workflow_queue__", None)
        if not q:
            raise ValueError(f"{cls.__name__} has no declared queue")

        handle = await client.start_workflow(
            cls.run,
            input,
            id=id,
            task_queue=q,
            execution_timeout=timedelta(minutes=5),
            **temporal_kwargs,
        )

        return handle

    @classmethod
    async def execute_workflow(
        cls,
        client: Client,
        input: TArgs,
        id: str,
        **temporal_kwargs,
    ) -> TReturn:
        """
        Execute a workflow synchronously, blocking until it completes and returning the result.

        This is a convenience method that combines start_workflow() and handle.result().
        Use this when you want to wait for the workflow to finish and get the return value
        immediately, rather than working with a handle.

        Args:
            client: Connected Temporal client instance
            input: Input data for the workflow (type-checked)
            id: Unique workflow ID (used for deduplication)
            **temporal_kwargs: Additional arguments to pass to client.execute_workflow
                              (e.g., execution_timeout, retry_policy, memo, search_attributes)

        Returns:
            The workflow's return value (type TReturn)

        Raises:
            ValueError: If workflow_type has no declared queue
            WorkflowFailureError: If the workflow fails during execution

        Example:
            result = await OrderWorkflow.execute_workflow(
                client,
                input=OrderInput(order_id="123", items=[...]),
                id="order-123",
                execution_timeout=timedelta(hours=1)
            )
            print(f"Order status: {result.status}")
        """
        q = getattr(cls, "__workflow_queue__", None)
        if not q:
            raise ValueError(f"{cls.__name__} has no declared queue")

        result = await client.execute_workflow(
            cls.run,
            input,
            id=id,
            task_queue=q,
            execution_timeout=timedelta(minutes=5),
            **temporal_kwargs,
        )

        return result

    @classmethod
    async def schedule_workflow(
        cls: type[Self],
        client: Client,
        input: TArgs,
        id: str,
        start_delay: timedelta,
        **temporal_kwargs,
    ) -> WorkflowHandle[Self, TReturn]:
        """
        Schedule a workflow to start at a future time.

        Uses Temporal's start_delay feature to defer workflow execution. The workflow
        will be created immediately but will not start executing until the delay elapses.

        Args:
            client: Connected Temporal client instance
            input: Input data for the workflow (type-checked)
            id: Unique workflow ID (used for deduplication)
            start_delay: How long to wait before starting the workflow
            **temporal_kwargs: Additional arguments to pass to client.start_workflow
                              (e.g., execution_timeout, retry_policy, memo, search_attributes)

        Returns:
            WorkflowHandle for the scheduled workflow

        Raises:
            ValueError: If workflow_type has no declared queue

        Example:
            # Schedule workflow to start in 1 hour
            handle = await OrderWorkflow.schedule_workflow(
                client,
                input=OrderInput(order_id="123", items=[...]),
                id="order-123",
                start_delay=timedelta(hours=1),
                execution_timeout=timedelta(hours=2)
            )

            # Can query/signal before it starts
            status = await handle.query(OrderWorkflow.state)

            # Wait for it to complete
            result = await handle.result()
        """
        q = getattr(cls, "__workflow_queue__", None)
        if not q:
            raise ValueError(f"{cls.__name__} has no declared queue")

        handle = await client.start_workflow(
            cls.run,
            input,
            id=id,
            task_queue=q,
            start_delay=start_delay,
            execution_timeout=timedelta(minutes=5),
            **temporal_kwargs,
        )

        return handle
