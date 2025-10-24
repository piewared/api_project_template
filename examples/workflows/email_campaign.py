"""
Example: Complete Email Workflow System

This example demonstrates a real-world use case of the Temporal Engine
for managing email campaigns with retries, delays, and tracking.
"""

import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from loguru import logger
from pydantic import BaseModel, EmailStr
from temporalio import workflow
from temporalio.common import RetryPolicy

from src.app.core.services.tasks.temporal_engine import TemporalEngine

# Initialize FastAPI app and Temporal engine
app = FastAPI(title="Email Campaign Service")
temporal = TemporalEngine()
router = APIRouter(prefix="/campaigns", tags=["campaigns"])


# ============================================================================
# Data Models
# ============================================================================


class EmailRecipient(BaseModel):
    """Email recipient information."""

    email: EmailStr
    name: str
    user_id: str


class EmailCampaign(BaseModel):
    """Email campaign configuration."""

    campaign_id: str | None = None
    subject: str
    body: str
    recipients: list[EmailRecipient]
    send_at: str | None = None  # ISO datetime for scheduled send
    batch_size: int = 50  # Emails per batch


class CampaignStatus(BaseModel):
    """Campaign execution status."""

    campaign_id: str
    status: str
    total_recipients: int
    sent: int = 0
    failed: int = 0
    pending: int = 0


# ============================================================================
# Activities (Individual Units of Work)
# ============================================================================


@temporal.activities.register
async def send_single_email(
    recipient_email: str, recipient_name: str, subject: str, body: str
) -> bool:
    """
    Send a single email.

    This is an idempotent operation - can be safely retried.
    """
    logger.info(f"Sending email to {recipient_email}")

    try:
        # Simulate email sending (replace with actual email service)
        # e.g., AWS SES, SendGrid, Mailgun, etc.

        # For demo purposes, we'll simulate success/failure
        import random

        if random.random() < 0.1:  # 10% failure rate for demo
            raise Exception(f"Failed to send email to {recipient_email}")

        logger.info(f"Email sent successfully to {recipient_email}")
        return True

    except Exception as e:
        logger.error(f"Email sending failed: {e}")
        raise  # Let Temporal handle the retry


@temporal.activities.register
async def record_email_sent(campaign_id: str, recipient_email: str) -> None:
    """Record that an email was sent successfully."""
    logger.info(f"Recording email sent: {campaign_id} -> {recipient_email}")

    # In a real app, update database
    # await db.execute(
    #     "INSERT INTO email_logs (campaign_id, recipient, sent_at) VALUES (?, ?, ?)",
    #     campaign_id, recipient_email, datetime.now()
    # )


@temporal.activities.register
async def record_email_failed(
    campaign_id: str, recipient_email: str, error: str
) -> None:
    """Record that an email failed to send."""
    logger.error(f"Recording email failure: {campaign_id} -> {recipient_email}: {error}")

    # In a real app, update database
    # await db.execute(
    #     "INSERT INTO email_failures (campaign_id, recipient, error, failed_at) VALUES (?, ?, ?, ?)",
    #     campaign_id, recipient_email, error, datetime.now()
    # )


@temporal.activities.register
async def notify_campaign_complete(campaign_id: str, stats: dict[str, int]) -> None:
    """Notify admin that campaign is complete."""
    logger.info(f"Campaign {campaign_id} completed. Stats: {stats}")

    # In a real app, send notification to admin
    # await send_slack_notification(f"Campaign {campaign_id} completed")


# ============================================================================
# Workflows (Orchestration)
# ============================================================================

assert temporal.workers is not None, "Temporal workers not initialized"


@temporal.workers.register_workflow
@workflow.defn
class EmailCampaignWorkflow:
    """
    Orchestrates an email campaign with batching, retries, and tracking.

    Features:
    - Sends emails in configurable batches
    - Automatic retries with exponential backoff
    - Tracks success/failure for each email
    - Reports campaign completion
    """

    @workflow.run
    async def run(self, campaign_data: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the email campaign.

        Args:
            campaign_data: Dict containing campaign configuration

        Returns:
            Dict with campaign execution statistics
        """
        campaign_id = campaign_data["campaign_id"]
        subject = campaign_data["subject"]
        body = campaign_data["body"]
        recipients = campaign_data["recipients"]
        batch_size = campaign_data.get("batch_size", 50)

        workflow.logger.info(
            f"Starting email campaign: {campaign_id} "
            f"with {len(recipients)} recipients"
        )

        sent_count = 0
        failed_count = 0

        # Process recipients in batches to avoid overwhelming the email service
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i : i + batch_size]
            workflow.logger.info(
                f"Processing batch {i // batch_size + 1} "
                f"({len(batch)} recipients)"
            )

            # Send emails in the current batch
            for recipient in batch:
                try:
                    # Send the email with retry policy
                    success = await workflow.execute_activity(
                        send_single_email,
                        args=[
                            recipient["email"],
                            recipient["name"],
                            subject,
                            body,
                        ],
                        start_to_close_timeout=timedelta(seconds=30),
                        retry_policy=RetryPolicy(
                            maximum_attempts=3,
                            initial_interval=timedelta(seconds=1),
                            maximum_interval=timedelta(seconds=10),
                            backoff_coefficient=2.0,
                        ),
                    )

                    if success:
                        # Record success
                        await workflow.execute_activity(
                            record_email_sent,
                            args=[campaign_id, recipient["email"]],
                            start_to_close_timeout=timedelta(seconds=10),
                        )
                        sent_count += 1

                except Exception as e:
                    # Record failure after all retries exhausted
                    workflow.logger.error(
                        f"Failed to send email to {recipient['email']}: {e}"
                    )

                    await workflow.execute_activity(
                        record_email_failed,
                        args=[campaign_id, recipient["email"], str(e)],
                        start_to_close_timeout=timedelta(seconds=10),
                    )
                    failed_count += 1

            # Small delay between batches to respect rate limits
            if i + batch_size < len(recipients):
                await workflow.sleep(timedelta(seconds=5))

        # Campaign complete - send notification
        stats = {"sent": sent_count, "failed": failed_count, "total": len(recipients)}

        await workflow.execute_activity(
            notify_campaign_complete,
            args=[campaign_id, stats],
            start_to_close_timeout=timedelta(seconds=30),
        )

        workflow.logger.info(f"Campaign {campaign_id} completed. Stats: {stats}")

        return {
            "campaign_id": campaign_id,
            "status": "completed",
            "sent": sent_count,
            "failed": failed_count,
            "total": len(recipients),
        }


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/", response_model=dict)
async def create_campaign(campaign: EmailCampaign) -> dict[str, Any]:
    """
    Create and start an email campaign.

    The campaign will be executed asynchronously in the background.
    """
    assert temporal.workflows is not None, "Temporal workflows not initialized"

    # Generate campaign ID if not provided
    campaign_id = campaign.campaign_id or f"campaign-{uuid.uuid4()}"

    # Prepare campaign data
    campaign_data = {
        "campaign_id": campaign_id,
        "subject": campaign.subject,
        "body": campaign.body,
        "recipients": [r.model_dump() for r in campaign.recipients],
        "batch_size": campaign.batch_size,
    }

    try:
        if campaign.send_at:
            # Schedule for future delivery
            from datetime import datetime

            send_time = datetime.fromisoformat(campaign.send_at)
            delay = (send_time - datetime.now()).total_seconds()

            if delay < 0:
                raise HTTPException(
                    status_code=400, detail="Send time must be in the future"
                )

            handle = await temporal.workflows.start_after(
                "EmailCampaignWorkflow",
                arg=campaign_data,
                delay_seconds=int(delay),
                workflow_id=campaign_id,
            )

            return {
                "campaign_id": campaign_id,
                "status": "scheduled",
                "workflow_id": handle.id,
                "send_at": campaign.send_at,
                "recipients": len(campaign.recipients),
            }
        else:
            # Start immediately
            handle = await temporal.workflows.start(
                "EmailCampaignWorkflow",
                arg=campaign_data,
                workflow_id=campaign_id,
            )

            return {
                "campaign_id": campaign_id,
                "status": "started",
                "workflow_id": handle.id,
                "recipients": len(campaign.recipients),
            }

    except Exception as e:
        logger.error(f"Failed to create campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{campaign_id}/status", response_model=CampaignStatus)
async def get_campaign_status(campaign_id: str) -> CampaignStatus:
    """Get the current status of an email campaign."""
    assert temporal.workflows is not None, "Temporal workflows not initialized"

    try:
        status = await temporal.workflows.get_status(campaign_id)

        # For running campaigns, we can't get partial results yet
        # In a real app, you'd query the database for real-time stats
        return CampaignStatus(
            campaign_id=campaign_id,
            status=status.status.value,
            total_recipients=0,  # Would come from DB
            sent=0,  # Would come from DB
            failed=0,  # Would come from DB
            pending=0,  # Would come from DB
        )

    except Exception:
        raise HTTPException(
            status_code=404, detail=f"Campaign not found: {campaign_id}"
        ) from None


@router.get("/{campaign_id}/results")
async def get_campaign_results(campaign_id: str) -> dict[str, Any]:
    """Get the final results of a completed campaign."""
    assert temporal.workflows is not None, "Temporal workflows not initialized"

    try:
        # Try to get results with 30 second timeout
        result: dict[str, Any] = await temporal.workflows.get_result(campaign_id, timeout_seconds=30)

        return result

    except TimeoutError:
        # Campaign still running
        return {
            "campaign_id": campaign_id,
            "status": "running",
            "message": "Campaign is still being processed",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{campaign_id}")
async def cancel_campaign(campaign_id: str) -> dict[str, str]:
    """Cancel a running email campaign."""
    assert temporal.workflows is not None, "Temporal workflows not initialized"

    try:
        await temporal.workflows.cancel(campaign_id)

        return {
            "campaign_id": campaign_id,
            "status": "cancelled",
            "message": "Campaign has been cancelled",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel: {str(e)}") from e


# ============================================================================
# Application Setup
# ============================================================================


@app.on_event("startup")
async def startup() -> None:
    """Initialize Temporal engine on app startup."""
    logger.info("Starting Email Campaign Service")
    await temporal.start()
    logger.info("Temporal engine initialized")


@app.on_event("shutdown")
async def shutdown() -> None:
    """Cleanup on app shutdown."""
    logger.info("Shutting down Email Campaign Service")
    await temporal.stop()


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy" if temporal.is_ready else "degraded",
        "temporal": temporal.health_check(),
    }


# Register router
app.include_router(router)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    """
    Example usage:

    1. Start the service:
       uvicorn examples.email_campaign:app --reload

    2. Create a campaign:
       curl -X POST http://localhost:8000/campaigns/ \
         -H "Content-Type: application/json" \
         -d '{
           "subject": "Welcome to our service!",
           "body": "Thanks for joining us!",
           "recipients": [
             {"email": "user1@example.com", "name": "User One", "user_id": "1"},
             {"email": "user2@example.com", "name": "User Two", "user_id": "2"}
           ]
         }'

    3. Check campaign status:
       curl http://localhost:8000/campaigns/campaign-{id}/status

    4. Get campaign results:
       curl http://localhost:8000/campaigns/campaign-{id}/results

    5. Cancel a campaign:
       curl -X DELETE http://localhost:8000/campaigns/campaign-{id}
    """
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
