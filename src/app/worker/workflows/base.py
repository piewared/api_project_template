# worker/workflows/base.py
from abc import ABC, abstractmethod
from datetime import timedelta

from temporalio import workflow
from temporalio.client import Client
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
    _state: dict = {}

    @abstractmethod
    @workflow.run
    async def run(self, input: TArgs) -> TReturn:
        ...

    @workflow.query
    def state(self) -> dict: return self._state

    @workflow.signal
    def cancel(self): self._state["cancelled"] = True

    @classmethod
    async def start_workflow(
        cls,
        client: Client,
        input: TArgs,
        id: str,
        **temporal_kwargs,
    ):
        """
        Start a workflow execution with type safety.

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
            handle = await registry.start_workflow(
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
