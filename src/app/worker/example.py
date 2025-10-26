import asyncio
import uuid
from datetime import timedelta
from time import sleep

from loguru import logger
from temporalio.client import Client
from temporalio.service import TLSConfig

from src.app.runtime.context import get_config
from src.app.worker.workflows.example import OrderInput, OrderProcessingWorkflow

# =============================================================================
# Example 1: Blocking Workflow Execution
# =============================================================================


async def example_1_execute_workflow_blocking() -> None:
    """
    Execute a workflow and wait for completion (blocking).

    This is the simplest pattern - start workflow and wait for result.
    """
    print("\n=== Example 1: Blocking Workflow Execution ===")

    config = get_config()
    temporal_config = config.temporal

    tls = None
    if temporal_config.tls:
        if TLSConfig is None:
            logger.error(
                "TLS requested but TLSConfig is unavailable in temporalio package."
            )
            raise RuntimeError("TLSConfig unavailable")
        tls = (
            TLSConfig()
        )  # customize as needed (server_root_ca_cert, client cert/key, etc.)

    print("Connecting to Temporal server...")
    # Connect to Temporal server
    client = await Client.connect(
        temporal_config.url,
        namespace=temporal_config.namespace,
        tls=tls or False,
    )

    # Create input with strong typing
    order_input = OrderInput(
        order_id=f"ORD-{uuid.uuid4().hex[:8]}",
        customer_email="customer@example.com",
        amount=99.99,
        items=[{"sku": "WIDGET-1", "quantity": 2}],
    )

    print(f"Starting workflow for order {order_input.order_id}...")

    # Option 1: Start and wait for result using registry
    handle = await OrderProcessingWorkflow.start_workflow(
        client,
        order_input,
        id=f"order-workflow-{order_input.order_id}",
    )

    # Wait for the workflow to complete
    result = await handle.result()

    print(f"Workflow completed: {result.status}")
    print(f"Message: {result.message}")
    print(f"Total: ${result.total_amount}")


if __name__ == "__main__":
    print("Starting example workflow execution...")
    asyncio.run(example_1_execute_workflow_blocking())
