"""
Simple integration example showing how to add Temporal to your FastAPI app.

This demonstrates the minimal setup needed to use the Temporal Engine.
"""

from datetime import timedelta
from typing import Any

from fastapi import FastAPI, HTTPException
from loguru import logger
from pydantic import BaseModel
from temporalio import workflow
from temporalio.common import RetryPolicy

from src.app.core.services.tasks.temporal_engine import TemporalEngine

# ============================================================================
# Initialize FastAPI and Temporal
# ============================================================================

app = FastAPI(title="My API with Temporal")
temporal = TemporalEngine()


# ============================================================================
# Define your activities (simple functions)
# ============================================================================


@temporal.activities.register
async def process_user_registration(user_id: str, email: str) -> dict[str, str]:
    """Process a new user registration."""
    logger.info(f"Processing registration for user: {user_id}")

    # Your business logic here
    # - Create user profile
    # - Send welcome email
    # - Set up default preferences
    # - etc.

    return {"user_id": user_id, "status": "active"}


@temporal.activities.register
async def send_welcome_email(email: str, username: str) -> bool:
    """Send welcome email to new user."""
    logger.info(f"Sending welcome email to: {email}")

    # Your email sending logic here
    # email_service.send(to=email, template="welcome", data={"username": username})

    return True


# ============================================================================
# Define your workflows (orchestration)
# ============================================================================

assert temporal.workers is not None, "Temporal workers not initialized"


@temporal.workers.register_workflow
@workflow.defn
class UserOnboardingWorkflow:
    """Workflow to onboard a new user."""

    @workflow.run
    async def run(self, user_data: dict[str, str]) -> dict[str, Any]:
        """
        Onboard a new user with multiple steps.

        Args:
            user_data: Dict with user_id, email, username

        Returns:
            Dict with onboarding status
        """
        workflow.logger.info(f"Starting onboarding for {user_data['user_id']}")

        # Step 1: Process registration
        registration = await workflow.execute_activity(
            process_user_registration,
            args=[user_data["user_id"], user_data["email"]],
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Step 2: Send welcome email
        email_sent = await workflow.execute_activity(
            send_welcome_email,
            args=[user_data["email"], user_data["username"]],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        return {
            "user_id": user_data["user_id"],
            "registration": registration,
            "email_sent": email_sent,
            "status": "completed",
        }


# ============================================================================
# App lifecycle
# ============================================================================


@app.on_event("startup")
async def startup() -> None:
    """Start Temporal engine when app starts."""
    logger.info("Starting application...")
    await temporal.start()
    logger.info("✓ Temporal engine ready")


@app.on_event("shutdown")
async def shutdown() -> None:
    """Stop Temporal engine when app shuts down."""
    logger.info("Shutting down application...")
    await temporal.stop()
    logger.info("✓ Temporal engine stopped")


# ============================================================================
# API Endpoints
# ============================================================================


class UserRegistration(BaseModel):
    """User registration request."""

    email: str
    username: str
    user_id: str | None = None


@app.post("/users/register")
async def register_user(user: UserRegistration) -> dict[str, Any]:
    """
    Register a new user (processes onboarding in background).

    Example:
        curl -X POST http://localhost:8000/users/register \
          -H "Content-Type: application/json" \
          -d '{"email": "user@example.com", "username": "johndoe"}'
    """
    import uuid

    assert temporal.workflows is not None, "Temporal workflows not initialized"

    user_id = user.user_id or str(uuid.uuid4())

    try:
        # Start onboarding workflow asynchronously
        handle = await temporal.workflows.start(
            "UserOnboardingWorkflow",
            arg={
                "user_id": user_id,
                "email": user.email,
                "username": user.username,
            },
            workflow_id=f"onboarding-{user_id}",
        )

        return {
            "user_id": user_id,
            "status": "registration_started",
            "workflow_id": handle.id,
            "message": "User onboarding in progress",
        }

    except Exception as e:
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from None


@app.get("/users/{user_id}/onboarding-status")
async def get_onboarding_status(user_id: str) -> dict[str, Any]:
    """
    Check the status of a user's onboarding workflow.

    Example:
        curl http://localhost:8000/users/user-123/onboarding-status
    """
    assert temporal.workflows is not None, "Temporal workflows not initialized"

    workflow_id = f"onboarding-{user_id}"

    try:
        status = await temporal.workflows.get_status(workflow_id)

        return {
            "user_id": user_id,
            "workflow_id": workflow_id,
            "status": status.status.value,
            "start_time": status.start_time,
            "close_time": status.close_time,
        }

    except Exception:
        raise HTTPException(
            status_code=404, detail=f"Onboarding not found for user: {user_id}"
        ) from None


@app.get("/health")
async def health() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy" if temporal.is_ready else "degraded",
        "temporal": temporal.health_check(),
    }


# ============================================================================
# Run the app
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
