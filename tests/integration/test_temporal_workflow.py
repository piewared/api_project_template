"""Integration tests for Temporal workflows and activities.

These tests use a real Temporal server connection to test the example
OrderProcessingWorkflow with actual workflow execution. Minimal mocking is used.
"""

import uuid
from collections.abc import AsyncGenerator
from datetime import timedelta

import pytest
from pydantic import ValidationError
from temporalio.client import Client
from temporalio.worker import Worker

from src.app.runtime.context import get_config
from src.app.worker.activities.example import (
    PaymentInput,
    process_payment,
    send_notification,
)
from src.app.worker.registry import autodiscover_modules
from src.app.worker.workflows.example import (
    OrderInput,
    OrderOutput,
    OrderProcessingWorkflow,
)


@pytest.fixture(scope="module")
def temporal_url() -> str:
    """Get Temporal server URL from config."""
    config = get_config()
    return config.temporal.url


@pytest.fixture(scope="module")
def temporal_namespace() -> str:
    """Get Temporal namespace from config."""
    config = get_config()
    return config.temporal.namespace


@pytest.fixture(scope="module")
async def temporal_client(temporal_url: str, temporal_namespace: str) -> Client:
    """Create a Temporal client for testing."""
    client = await Client.connect(
        temporal_url,
        namespace=temporal_namespace,
    )
    return client


@pytest.fixture
def task_queue() -> str:
    """Generate a unique task queue name for test isolation."""
    return f"test-queue-{uuid.uuid4().hex[:8]}"


@pytest.fixture
async def temporal_worker(
    temporal_client: Client,
    task_queue: str,
) -> AsyncGenerator[Worker]:
    """Create a Temporal worker with the example workflow and activities."""
    # Discover all workflows and activities
    autodiscover_modules()

    # Create worker with our test task queue
    worker = Worker(
        temporal_client,
        task_queue=task_queue,
        workflows=[OrderProcessingWorkflow],
        activities=[process_payment, send_notification],
    )

    # Start the worker in the background
    async with worker:
        yield worker


class TestOrderProcessingWorkflow:
    """Integration tests for OrderProcessingWorkflow."""

    @pytest.mark.asyncio
    async def test_successful_order_processing(
        self,
        temporal_client: Client,
        temporal_worker: Worker,
        task_queue: str,
    ):
        """Test successful order processing with payment and notification."""
        # Arrange
        order_input = OrderInput(
            order_id=f"order-{uuid.uuid4().hex[:8]}",
            customer_email="customer@example.com",
            amount=99.99,
            items=[{"product_id": "prod-1", "quantity": 2, "price": 49.995}],
        )

        # Act
        result = await temporal_client.execute_workflow(
            OrderProcessingWorkflow.run,
            order_input,
            id=f"workflow-{uuid.uuid4()}",
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=30),
        )

        # Assert
        assert isinstance(result, OrderOutput)
        assert result.order_id == order_input.order_id
        assert result.status == "completed"
        assert result.total_amount == order_input.amount
        assert "successfully" in result.message.lower()
        assert "txn_" in result.message  # Transaction ID present

    @pytest.mark.asyncio
    async def test_order_with_zero_amount(
        self,
        temporal_client: Client,
        temporal_worker: Worker,
        task_queue: str,
    ):
        """Test order processing with zero amount (edge case)."""
        # Arrange
        order_input = OrderInput(
            order_id=f"order-{uuid.uuid4().hex[:8]}",
            customer_email="customer@example.com",
            amount=0.0,
            items=[],
        )

        # Act
        result = await temporal_client.execute_workflow(
            OrderProcessingWorkflow.run,
            order_input,
            id=f"workflow-{uuid.uuid4()}",
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=30),
        )

        # Assert
        assert isinstance(result, OrderOutput)
        assert result.order_id == order_input.order_id
        assert result.status == "completed"
        assert result.total_amount == 0.0

    @pytest.mark.asyncio
    async def test_order_cancellation_before_payment(
        self,
        temporal_client: Client,
        temporal_worker: Worker,
        task_queue: str,
    ):
        """Test order cancellation via signal before payment processing."""
        # Arrange
        workflow_id = f"workflow-{uuid.uuid4()}"
        order_input = OrderInput(
            order_id=f"order-{uuid.uuid4().hex[:8]}",
            customer_email="customer@example.com",
            amount=150.00,
            items=[{"product_id": "prod-2", "quantity": 1, "price": 150.00}],
        )

        # Start the workflow (don't wait for completion)
        handle = await temporal_client.start_workflow(
            OrderProcessingWorkflow.run,
            order_input,
            id=workflow_id,
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=30),
        )

        # Send cancel signal immediately
        await handle.signal(OrderProcessingWorkflow.cancel_order, "Customer requested cancellation")

        # Wait for workflow to complete
        result = await handle.result()

        # Assert
        assert isinstance(result, OrderOutput)
        assert result.status == "cancelled"
        assert "Customer requested cancellation" in result.message

    @pytest.mark.asyncio
    async def test_workflow_status_query(
        self,
        temporal_client: Client,
        temporal_worker: Worker,
        task_queue: str,
    ):
        """Test querying workflow status during execution."""
        # Arrange
        workflow_id = f"workflow-{uuid.uuid4()}"
        order_input = OrderInput(
            order_id=f"order-{uuid.uuid4().hex[:8]}",
            customer_email="test@example.com",
            amount=50.00,
            items=[{"product_id": "prod-3", "quantity": 1, "price": 50.00}],
        )

        # Start the workflow
        handle = await temporal_client.start_workflow(
            OrderProcessingWorkflow.run,
            order_input,
            id=workflow_id,
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=30),
        )

        # Query the workflow status (may be in various states)
        status = await handle.query(OrderProcessingWorkflow.get_status)

        # Status should be a non-empty string
        assert isinstance(status, str)
        assert len(status) > 0

        # Query cancellation status
        is_cancelled = await handle.query(OrderProcessingWorkflow.is_cancelled)
        assert isinstance(is_cancelled, bool)
        assert is_cancelled is False  # Not cancelled

        # Wait for completion
        result = await handle.result()
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_workflow_update_status_signal(
        self,
        temporal_client: Client,
        temporal_worker: Worker,
        task_queue: str,
    ):
        """Test updating workflow status via signal."""
        # Arrange
        workflow_id = f"workflow-{uuid.uuid4()}"
        order_input = OrderInput(
            order_id=f"order-{uuid.uuid4().hex[:8]}",
            customer_email="update@example.com",
            amount=75.00,
            items=[{"product_id": "prod-4", "quantity": 1, "price": 75.00}],
        )

        # Start the workflow
        handle = await temporal_client.start_workflow(
            OrderProcessingWorkflow.run,
            order_input,
            id=workflow_id,
            task_queue=task_queue,
            execution_timeout=timedelta(seconds=30),
        )

        # Send update status signal
        await handle.signal(OrderProcessingWorkflow.update_status, "on_hold")

        # Query the status (may or may not reflect the signal yet due to async nature)
        status = await handle.query(OrderProcessingWorkflow.get_status)
        assert isinstance(status, str)
        assert len(status) > 0

        # Wait for workflow completion - the important part is it completes successfully
        result = await handle.result()
        assert isinstance(result, OrderOutput)
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_multiple_orders_concurrent(
        self,
        temporal_client: Client,
        temporal_worker: Worker,
        task_queue: str,
    ):
        """Test processing multiple orders concurrently."""
        # Arrange - create 3 orders
        orders = [
            OrderInput(
                order_id=f"order-{uuid.uuid4().hex[:8]}",
                customer_email=f"customer{i}@example.com",
                amount=100.0 + i * 10,
                items=[{"product_id": f"prod-{i}", "quantity": 1, "price": 100.0 + i * 10}],
            )
            for i in range(3)
        ]

        # Act - start all workflows concurrently
        handles = []
        for order in orders:
            handle = await temporal_client.start_workflow(
                OrderProcessingWorkflow.run,
                order,
                id=f"workflow-{uuid.uuid4()}",
                task_queue=task_queue,
                execution_timeout=timedelta(seconds=30),
            )
            handles.append(handle)

        # Wait for all to complete
        results = []
        for handle in handles:
            result = await handle.result()
            results.append(result)

        # Assert - all orders completed successfully
        assert len(results) == 3
        for i, result in enumerate(results):
            assert isinstance(result, OrderOutput)
            assert result.order_id == orders[i].order_id
            assert result.status == "completed"
            assert result.total_amount == orders[i].amount

    @pytest.mark.asyncio
    async def test_workflow_with_invalid_email(
        self,
        temporal_client: Client,
        temporal_worker: Worker,
        task_queue: str,
    ):
        """Test that workflow validation catches invalid email."""
        # Arrange - invalid email should fail at Pydantic validation
        with pytest.raises(ValidationError):
            OrderInput(
                order_id=f"order-{uuid.uuid4().hex[:8]}",
                customer_email="not-an-email",  # Invalid email
                amount=50.00,
                items=[],
            )


class TestPaymentActivity:
    """Integration tests for payment activity."""

    @pytest.mark.asyncio
    async def test_payment_activity_direct_call(self):
        """Test payment activity can be called directly (unit test style)."""
        # Arrange
        payment_input = PaymentInput(
            order_id="test-order-123",
            amount=99.99,
        )

        # Act
        result = await process_payment(payment_input)

        # Assert
        assert result.transaction_id.startswith("txn_")
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_notification_activity_direct_call(self):
        """Test notification activity can be called directly."""
        # Act
        result = await send_notification(
            email="test@example.com",
            message="Test notification",
        )

        # Assert
        assert result is True


class TestWorkflowRegistry:
    """Integration tests for workflow registry system."""

    def test_autodiscover_finds_example_workflow(self):
        """Test that autodiscovery finds the OrderProcessingWorkflow."""
        from src.app.worker.registry import (
            autodiscover_modules,
            get_workflows_by_queue,
        )

        # Act
        autodiscover_modules()
        workflows = get_workflows_by_queue()

        # Assert
        assert "example" in workflows
        assert OrderProcessingWorkflow in workflows["example"]

    def test_autodiscover_finds_example_activities(self):
        """Test that autodiscovery finds the example activities."""
        from src.app.worker.registry import (
            autodiscover_modules,
            get_activities_by_queue,
        )

        # Act
        autodiscover_modules()
        activities = get_activities_by_queue()

        # Assert
        assert "example" in activities
        activity_set = activities["example"]
        activity_names = {act.__name__ for act in activity_set}
        assert "process_payment" in activity_names
        assert "send_notification" in activity_names
