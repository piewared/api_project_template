"""
User-friendly Temporal workflow engine abstraction for FastAPI applications.

This module provides an intuitive API for working with Temporal workflows and activities
without needing to understand Temporal's low-level details.

Example usage:

    # In your FastAPI app startup
    temporal = TemporalEngine()
    await temporal.start()

    # Execute a workflow
    result = await temporal.workflows.execute(
        "send_email",
        {"to": "user@example.com", "subject": "Welcome!"},
        workflow_id="email-user-123"
    )

    # Execute async (fire and forget)
    handle = await temporal.workflows.start(
        "process_order",
        {"order_id": "123"},
        workflow_id="order-123"
    )

    # Query workflow status
    status = await temporal.workflows.get_status(handle.id)

    # Schedule a delayed task
    await temporal.workflows.schedule(
        "send_reminder",
        {"user_id": "123"},
        delay_seconds=3600  # Run in 1 hour
    )
"""

import asyncio
import uuid
from collections.abc import Callable
from datetime import timedelta
from enum import Enum
from typing import Any

from loguru import logger
from pydantic import BaseModel
from temporalio import activity
from temporalio.client import Client, WorkflowExecutionStatus, WorkflowHandle
from temporalio.common import RetryPolicy, WorkflowIDConflictPolicy
from temporalio.worker import Worker

from src.app.runtime.context import get_config


class WorkflowStatus(str, Enum):
    """Simplified workflow status enum."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class WorkflowResult(BaseModel):
    """Result of a workflow execution."""

    workflow_id: str
    status: WorkflowStatus
    result: Any | None = None
    error: str | None = None


class WorkflowInfo(BaseModel):
    """Information about a workflow execution."""

    workflow_id: str
    workflow_type: str
    status: WorkflowStatus
    run_id: str
    start_time: str | None = None
    close_time: str | None = None


class WorkflowsAPI:
    """High-level API for workflow operations."""

    def __init__(self, client: Client, namespace: str, task_queue: str):
        self._client = client
        self._namespace = namespace
        self._task_queue = task_queue

    async def execute(
        self,
        workflow_name: str,
        arg: Any = None,
        workflow_id: str | None = None,
        timeout_seconds: int | None = None,
        retry_policy: RetryPolicy | None = None,
        id_conflict_policy: WorkflowIDConflictPolicy = WorkflowIDConflictPolicy.FAIL,
    ) -> Any:
        """
        Execute a workflow and wait for the result.

        Args:
            workflow_name: Name of the workflow to execute
            arg: Single argument to pass to the workflow (preferably a Pydantic model or dataclass)
            workflow_id: Unique ID for the workflow (auto-generated if not provided)
            timeout_seconds: Maximum time to wait for completion (execution_timeout)
            retry_policy: Retry policy for the workflow execution
            id_conflict_policy: How to handle workflow ID conflicts (default: FAIL)

        Returns:
            The workflow result

        Raises:
            WorkflowFailureError: If workflow execution fails
            TimeoutError: If execution times out

        Example:
            # With typed input
            result = await temporal.workflows.execute(
                "SendEmailWorkflow",
                SendEmailInput(to="user@example.com", subject="Hello"),
                workflow_id="email-123"
            )

            # With dict (less recommended)
            result = await temporal.workflows.execute(
                "SendEmailWorkflow",
                {"to": "user@example.com", "subject": "Hello"}
            )
        """
        workflow_id = workflow_id or f"{workflow_name}-{uuid.uuid4()}"

        logger.info(
            "Executing workflow",
            workflow_name=workflow_name,
            workflow_id=workflow_id,
        )

        try:
            # Use execute_workflow which is the documented convenience API
            # for start + wait. It's clearer than start_workflow + handle.result()
            result = await self._client.execute_workflow(
                workflow_name,
                arg,
                id=workflow_id,
                task_queue=self._task_queue,
                execution_timeout=timedelta(seconds=timeout_seconds)
                if timeout_seconds
                else None,
                retry_policy=retry_policy,
                id_conflict_policy=id_conflict_policy,
            )

            logger.info("Workflow completed", workflow_id=workflow_id)
            return result

        except Exception as e:
            logger.error("Workflow failed", workflow_id=workflow_id, error=str(e))
            # Let Temporal exceptions bubble for proper error handling by callers
            raise

    async def start(
        self,
        workflow_name: str,
        arg: Any = None,
        workflow_id: str | None = None,
        timeout_seconds: int | None = None,
        retry_policy: RetryPolicy | None = None,
        id_conflict_policy: WorkflowIDConflictPolicy = WorkflowIDConflictPolicy.FAIL,
    ) -> WorkflowHandle:
        """
        Start a workflow without waiting for completion (async execution).

        Args:
            workflow_name: Name of the workflow to execute
            arg: Single argument to pass to the workflow (preferably typed)
            workflow_id: Unique ID for the workflow (auto-generated if not provided)
            timeout_seconds: Maximum time for workflow to run (execution_timeout)
            retry_policy: Retry policy for the workflow
            id_conflict_policy: How to handle workflow ID conflicts (default: FAIL)

        Returns:
            WorkflowHandle that can be used to query status or get result later

        Example:
            handle = await temporal.workflows.start(
                "ProcessLargeFileWorkflow",
                ProcessFileInput(file_id="abc123"),
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING
            )
            # Continue with other work...
            # Later: result = await handle.result()
        """
        workflow_id = workflow_id or f"{workflow_name}-{uuid.uuid4()}"

        logger.info(
            "Starting workflow (async)",
            workflow_name=workflow_name,
            workflow_id=workflow_id,
        )

        handle = await self._client.start_workflow(
            workflow_name,
            arg,
            id=workflow_id,
            task_queue=self._task_queue,
            execution_timeout=timedelta(seconds=timeout_seconds)
            if timeout_seconds
            else None,
            retry_policy=retry_policy,
            id_conflict_policy=id_conflict_policy,
        )

        logger.info("Workflow started", workflow_id=workflow_id)
        return handle

    async def start_after(
        self,
        workflow_name: str,
        arg: Any = None,
        delay_seconds: int = 0,
        workflow_id: str | None = None,
        retry_policy: RetryPolicy | None = None,
        id_conflict_policy: WorkflowIDConflictPolicy = WorkflowIDConflictPolicy.FAIL,
    ) -> WorkflowHandle:
        """
        Start a workflow after a delay (one-off delayed execution).

        Note: This uses start_delay for one-off delayed starts. It is NOT compatible
        with Temporal Schedules (recurring/cron workflows). For recurring tasks,
        use Temporal's Schedule API directly.

        Args:
            workflow_name: Name of the workflow to execute
            arg: Single argument to pass to the workflow
            delay_seconds: Delay in seconds before starting the workflow
            workflow_id: Unique ID for the workflow (auto-generated if not provided)
            retry_policy: Retry policy for the workflow
            id_conflict_policy: How to handle workflow ID conflicts

        Returns:
            WorkflowHandle for the delayed workflow

        Example:
            # Send a reminder in 1 hour
            await temporal.workflows.start_after(
                "SendReminderWorkflow",
                ReminderInput(user_id="123", message="Don't forget!"),
                delay_seconds=3600
            )
        """
        workflow_id = workflow_id or f"{workflow_name}-{uuid.uuid4()}"

        logger.info(
            "Scheduling workflow with delay",
            workflow_name=workflow_name,
            workflow_id=workflow_id,
            delay_seconds=delay_seconds,
        )

        handle = await self._client.start_workflow(
            workflow_name,
            arg,
            id=workflow_id,
            task_queue=self._task_queue,
            start_delay=timedelta(seconds=delay_seconds),
            retry_policy=retry_policy,
            id_conflict_policy=id_conflict_policy,
        )

        logger.info("Workflow scheduled with delay", workflow_id=workflow_id)
        return handle

    async def get_status(self, workflow_id: str) -> WorkflowInfo:
        """
        Get the current status of a workflow.

        Args:
            workflow_id: ID of the workflow to query

        Returns:
            WorkflowInfo with current status and details

        Example:
            status = await temporal.workflows.get_status("email-123")
            if status.status == WorkflowStatus.COMPLETED:
                print("Email sent successfully!")
        """
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            description = await handle.describe()

            # Map Temporal status to our simplified status
            status_map = {
                WorkflowExecutionStatus.RUNNING: WorkflowStatus.RUNNING,
                WorkflowExecutionStatus.COMPLETED: WorkflowStatus.COMPLETED,
                WorkflowExecutionStatus.FAILED: WorkflowStatus.FAILED,
                WorkflowExecutionStatus.CANCELED: WorkflowStatus.CANCELLED,
                WorkflowExecutionStatus.TERMINATED: WorkflowStatus.FAILED,
                WorkflowExecutionStatus.TIMED_OUT: WorkflowStatus.TIMEOUT,
            }

            workflow_status = (
                status_map.get(description.status, WorkflowStatus.UNKNOWN)
                if description.status
                else WorkflowStatus.UNKNOWN
            )

            return WorkflowInfo(
                workflow_id=workflow_id,
                workflow_type=description.workflow_type,
                status=workflow_status,
                run_id=description.run_id,
                start_time=description.start_time.isoformat()
                if description.start_time
                else None,
                close_time=description.close_time.isoformat()
                if description.close_time
                else None,
            )
        except Exception as e:
            logger.error(f"Failed to get workflow status: {workflow_id}", error=str(e))
            raise

    async def cancel(self, workflow_id: str) -> None:
        """
        Cancel a running workflow.

        Args:
            workflow_id: ID of the workflow to cancel

        Example:
            await temporal.workflows.cancel("long-running-task-123")
        """
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            await handle.cancel()
            logger.info(f"Workflow cancelled: {workflow_id}")
        except Exception as e:
            logger.error(f"Failed to cancel workflow: {workflow_id}", error=str(e))
            raise

    async def get_result(self, workflow_id: str, timeout_seconds: int = 30) -> Any:
        """
        Get the result of a workflow execution.

        Args:
            workflow_id: ID of the workflow
            timeout_seconds: Maximum time to wait for result

        Returns:
            The workflow result

        Raises:
            TimeoutError: If timeout is reached
            WorkflowFailureError: If workflow failed

        Example:
            result = await temporal.workflows.get_result("email-123")
        """
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            result = await asyncio.wait_for(
                handle.result(), timeout=timeout_seconds if timeout_seconds else None
            )
            return result
        except TimeoutError:
            logger.warning("Timeout waiting for workflow result", workflow_id=workflow_id)
            raise
        except Exception as e:
            logger.error("Failed to get workflow result", workflow_id=workflow_id, error=str(e))
            raise

    async def signal(self, workflow_id: str, signal_name: str, *args: Any) -> None:
        """
        Send a signal to a running workflow.

        Signals allow external events to notify and interact with running workflows.

        Args:
            workflow_id: ID of the workflow to signal
            signal_name: Name of the signal (must match workflow's @workflow.signal def)
            *args: Arguments to pass to the signal handler

        Example:
            # Signal a workflow to approve
            await temporal.workflows.signal("approval-123", "approve")

            # Signal with data
            await temporal.workflows.signal(
                "order-456",
                "update_quantity",
                10  # new quantity
            )
        """
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            await handle.signal(signal_name, *args)
            logger.info(
                "Signal sent to workflow",
                workflow_id=workflow_id,
                signal_name=signal_name,
            )
        except Exception as e:
            logger.error(
                "Failed to send signal",
                workflow_id=workflow_id,
                signal_name=signal_name,
                error=str(e),
            )
            raise

    async def query(self, workflow_id: str, query_name: str, *args: Any) -> Any:
        """
        Query a running workflow for information.

        Queries allow you to get data from a running workflow without affecting its state.

        Args:
            workflow_id: ID of the workflow to query
            query_name: Name of the query (must match workflow's @workflow.query def)
            *args: Arguments to pass to the query handler

        Returns:
            The query result

        Example:
            # Query workflow progress
            progress = await temporal.workflows.query("job-789", "get_progress")

            # Query with parameters
            items = await temporal.workflows.query(
                "cart-123",
                "get_items_by_category",
                "electronics"
            )
        """
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            result = await handle.query(query_name, *args)
            logger.info(
                "Query executed on workflow",
                workflow_id=workflow_id,
                query_name=query_name,
            )
            return result
        except Exception as e:
            logger.error(
                "Failed to query workflow",
                workflow_id=workflow_id,
                query_name=query_name,
                error=str(e),
            )
            raise


class ActivitiesAPI:
    """High-level API for activity operations."""

    def __init__(self):
        self._registered_activities: list[Callable] = []

    def register(self, func: Callable) -> Callable:
        """
        Register a function as a Temporal activity.

        Can be used as a decorator or called directly.

        Args:
            func: The function to register as an activity

        Returns:
            The decorated function

        Example:
            @temporal.activities.register
            async def send_email(to: str, subject: str, body: str) -> bool:
                # Send email logic
                return True

            # Or without decorator:
            temporal.activities.register(send_email)
        """
        activity_func = activity.defn(func)
        self._registered_activities.append(activity_func)
        logger.info(f"Registered activity: {func.__name__}")
        return activity_func

    def get_registered(self) -> list[Callable]:
        """Get list of all registered activities."""
        return self._registered_activities


class WorkersAPI:
    """High-level API for worker management."""

    def __init__(self, client: Client, task_queue: str, activities: list[Callable]):
        self._client = client
        self._task_queue = task_queue
        self._activities = activities
        self._workflows: list[type] = []
        self._worker: Worker | None = None

    def register_workflow(self, workflow_class: type) -> type:
        """
        Register a workflow class.

        Args:
            workflow_class: The workflow class to register

        Returns:
            The workflow class (for use as decorator)

        Example:
            @temporal.workers.register_workflow
            @workflow.defn
            class SendEmailWorkflow:
                @workflow.run
                async def run(self, email_data: dict) -> bool:
                    # Workflow logic
                    return True
        """
        self._workflows.append(workflow_class)
        logger.info(f"Registered workflow: {workflow_class.__name__}")
        return workflow_class

    async def start(self) -> None:
        """Start the worker to process workflows and activities."""
        if not self._workflows and not self._activities:
            logger.warning("No workflows or activities registered, skipping worker start")
            return

        logger.info(
            f"Starting Temporal worker on task queue: {self._task_queue}",
            workflows=len(self._workflows),
            activities=len(self._activities),
        )

        self._worker = Worker(
            self._client,
            task_queue=self._task_queue,
            workflows=self._workflows,
            activities=self._activities,
        )

        # Run worker in background
        asyncio.create_task(self._worker.run())
        logger.info("Temporal worker started")

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        if self._worker:
            logger.info("Stopping Temporal worker")
            await self._worker.shutdown()
            logger.info("Temporal worker stopped")


class TemporalEngine:
    """
    Main Temporal engine providing high-level APIs for workflows, activities, and workers.

    This is the primary interface for interacting with Temporal in your FastAPI application.

    Example usage:

        # Initialize in your FastAPI app
        temporal = TemporalEngine()

        @app.on_event("startup")
        async def startup():
            await temporal.start()

        @app.on_event("shutdown")
        async def shutdown():
            await temporal.stop()

        # Register activities
        @temporal.activities.register
        async def send_email(to: str, subject: str) -> bool:
            # Your email sending logic
            return True

        # Register workflows
        @temporal.workers.register_workflow
        @workflow.defn
        class EmailWorkflow:
            @workflow.run
            async def run(self, data: dict) -> bool:
                result = await workflow.execute_activity(
                    send_email,
                    args=[data["to"], data["subject"]],
                    start_to_close_timeout=timedelta(seconds=30)
                )
                return result

        # Use in your API endpoints
        @app.post("/send-email")
        async def api_send_email(email: EmailRequest):
            result = await temporal.workflows.execute(
                "EmailWorkflow",
                {"to": email.to, "subject": email.subject}
            )
            return {"success": result}
    """

    def __init__(self):
        """Initialize the Temporal engine with configuration from app config."""
        self._config = get_config().temporal
        self._client: Client | None = None
        self._started = False

        # Initialize sub-APIs
        self.activities = ActivitiesAPI()
        self.workflows: WorkflowsAPI | None = None
        self.workers: WorkersAPI | None = None

    async def start(self) -> None:
        """
        Start the Temporal engine and connect to the Temporal server.

        This should be called during FastAPI app startup.

        Example:
            @app.on_event("startup")
            async def startup():
                await temporal.start()
        """
        if self._started:
            logger.warning("Temporal engine already started")
            return

        if not self._config.enabled:
            logger.info("Temporal is disabled in configuration")
            return

        logger.info(f"Connecting to Temporal server: {self._config.url}")

        try:
            # Connect to Temporal server
            self._client = await Client.connect(
                self._config.url, namespace=self._config.namespace
            )

            # Initialize APIs with client
            self.workflows = WorkflowsAPI(
                self._client, self._config.namespace, self._config.task_queue
            )

            self.workers = WorkersAPI(
                self._client,
                self._config.task_queue,
                self.activities.get_registered(),
            )

            # Start worker if enabled
            if self._config.worker.enabled:
                await self.workers.start()

            self._started = True
            logger.info("Temporal engine started successfully")

        except Exception as e:
            logger.error(f"Failed to start Temporal engine: {e}")
            raise

    async def stop(self) -> None:
        """
        Stop the Temporal engine and close connections.

        This should be called during FastAPI app shutdown.

        Example:
            @app.on_event("shutdown")
            async def shutdown():
                await temporal.stop()
        """
        if not self._started:
            return

        logger.info("Stopping Temporal engine")

        try:
            if self.workers:
                await self.workers.stop()

            # Temporal client doesn't require explicit close in recent versions
            # Connection is managed automatically

            self._started = False
            logger.info("Temporal engine stopped")

        except Exception as e:
            logger.error(f"Error stopping Temporal engine: {e}")
            raise

    @property
    def is_ready(self) -> bool:
        """Check if the Temporal engine is ready to accept requests."""
        return self._started and self._client is not None

    def health_check(self) -> dict[str, Any]:
        """
        Get health status of the Temporal engine.

        Returns:
            Dictionary with health status information

        Example:
            @app.get("/health")
            async def health():
                return {
                    "temporal": temporal.health_check()
                }
        """
        return {
            "enabled": self._config.enabled,
            "connected": self._started,
            "server_url": self._config.url,
            "namespace": self._config.namespace,
            "task_queue": self._config.task_queue,
            "worker_enabled": self._config.worker.enabled,
            "activities_registered": len(self.activities.get_registered()),
        }
