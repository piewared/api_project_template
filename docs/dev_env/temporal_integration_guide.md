"""
Integration guide: Adding Temporal to your existing FastAPI app.

This shows how to integrate the Temporal Engine into the template's
existing app structure.
"""

# ============================================================================
# 1. Update src/app/api/http/app.py
# ============================================================================

# Add imports at the top
from src.app.core.services.tasks.temporal_engine import TemporalEngine

# Initialize Temporal engine (add after imports)
temporal = TemporalEngine()

# Update lifespan context manager (replace existing)
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    # Startup
    await startup()
    await temporal.start()  # ← Add this line

    yield

    # Shutdown
    await temporal.stop()  # ← Add this line
    await shutdown()


# Export temporal for use in other modules
__all__ = ["app", "startup", "shutdown", "temporal"]


# ============================================================================
# 2. Create src/app/workflows/activities.py
# ============================================================================

"""
Activity definitions for your application.

Activities are reusable units of work that can be composed into workflows.
"""

from loguru import logger

# Import the global temporal instance
from src.app.api.http.app import temporal


@temporal.activities.register
async def send_notification_email(
    user_id: str, notification_type: str, data: dict
) -> bool:
    """Send a notification email to a user."""
    from src.app.service.user_management_service import UserManagementService

    logger.info(f"Sending {notification_type} notification to user {user_id}")

    # Get user email from database
    user_service = UserManagementService()
    user = await user_service.get_user_by_id(user_id)

    if not user:
        logger.error(f"User not found: {user_id}")
        return False

    # Send email using your email service
    # email_service.send(to=user.email, template=notification_type, data=data)

    logger.info(f"Notification sent to {user.email}")
    return True


@temporal.activities.register
async def process_user_action(user_id: str, action: str, params: dict) -> dict:
    """Process a user action."""
    logger.info(f"Processing action {action} for user {user_id}")

    # Your business logic here based on action type
    if action == "update_profile":
        # Update user profile
        pass
    elif action == "verify_email":
        # Send verification email
        pass

    return {"status": "completed", "action": action}


# ============================================================================
# 3. Create src/app/workflows/definitions.py
# ============================================================================

"""
Workflow definitions for your application.

Workflows orchestrate activities and handle retries, timeouts, and recovery.
"""

from datetime import timedelta

from loguru import logger
from temporalio import workflow

# Import the global temporal instance
from src.app.api.http.app import temporal


@temporal.workers.register_workflow
@workflow.defn
class UserOnboardingWorkflow:
    """Complete user onboarding process."""

    @workflow.run
    async def run(self, user_id: str, email: str) -> dict:
        """
        Onboard a new user with multiple steps.

        Args:
            user_id: The user's ID
            email: The user's email address

        Returns:
            Onboarding result
        """
        workflow.logger.info(f"Starting onboarding for user {user_id}")

        # Import activities
        from .activities import process_user_action, send_notification_email

        # Step 1: Process initial setup
        setup_result = await workflow.execute_activity(
            process_user_action,
            args=[user_id, "initial_setup", {}],
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Step 2: Send welcome email
        await workflow.execute_activity(
            send_notification_email,
            args=[user_id, "welcome", {"email": email}],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=workflow.RetryPolicy(maximum_attempts=3),
        )

        # Step 3: Wait 24 hours then send follow-up
        await workflow.sleep(timedelta(days=1))

        await workflow.execute_activity(
            send_notification_email,
            args=[user_id, "getting_started", {}],
            start_to_close_timeout=timedelta(seconds=30),
        )

        return {
            "user_id": user_id,
            "status": "completed",
            "setup": setup_result,
        }


# ============================================================================
# 4. Add to your existing routers (e.g., src/app/api/http/routers/users.py)
# ============================================================================

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.app.api.http.app import temporal
from src.app.entities.core.user import User

router = APIRouter(prefix="/users", tags=["users"])


class UserCreate(BaseModel):
    email: str
    first_name: str
    last_name: str


@router.post("/", status_code=201)
async def create_user(user_data: UserCreate) -> dict:
    """Create a new user and start onboarding workflow."""

    # Your existing user creation logic
    # user_service = UserManagementService()
    # user = await user_service.create_user(user_data)

    user_id = "user-123"  # Replace with actual user ID

    # Start onboarding workflow in background
    try:
        handle = await temporal.workflows.start(
            "UserOnboardingWorkflow",
            args=[user_id, user_data.email],
            workflow_id=f"onboarding-{user_id}",
        )

        return {
            "user_id": user_id,
            "email": user_data.email,
            "onboarding_workflow_id": handle.id,
            "status": "created",
        }

    except Exception as e:
        logger.error(f"Failed to start onboarding workflow: {e}")
        # Still return user creation success, log workflow failure
        return {
            "user_id": user_id,
            "email": user_data.email,
            "status": "created",
            "note": "Onboarding workflow failed to start",
        }


@router.get("/{user_id}/onboarding")
async def get_onboarding_status(user_id: str) -> dict:
    """Get the status of a user's onboarding workflow."""

    workflow_id = f"onboarding-{user_id}"

    try:
        status = await temporal.workflows.get_status(workflow_id)

        return {
            "user_id": user_id,
            "workflow_id": workflow_id,
            "status": status.status.value,
            "workflow_type": status.workflow_type,
            "start_time": status.start_time,
        }

    except Exception as e:
        raise HTTPException(
            status_code=404, detail=f"Onboarding workflow not found for user {user_id}"
        ) from None


# ============================================================================
# 5. Add health check endpoint
# ============================================================================

# In src/app/api/http/routers/health.py (or create new file)

from fastapi import APIRouter

from src.app.api.http.app import temporal

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check() -> dict:
    """Complete health check including Temporal."""
    return {
        "status": "healthy",
        "components": {
            "api": "healthy",
            "temporal": "healthy" if temporal.is_ready else "degraded",
        },
        "temporal_details": temporal.health_check(),
    }


# ============================================================================
# 6. File structure after integration
# ============================================================================

"""
src/
├── app/
│   ├── api/
│   │   └── http/
│   │       ├── app.py              # ← Updated with temporal initialization
│   │       └── routers/
│   │           ├── users.py        # ← Updated with workflow triggers
│   │           └── health.py       # ← New health check
│   ├── workflows/                  # ← New directory
│   │   ├── __init__.py
│   │   ├── activities.py           # ← Activity definitions
│   │   └── definitions.py          # ← Workflow definitions
│   └── core/
│       └── services/
│           └── tasks/
│               ├── temporal_engine.py    # ← Main engine
│               └── README.md             # ← Documentation
"""

# ============================================================================
# 7. Testing the integration
# ============================================================================

"""
# Start your FastAPI app
uv run cli dev start-server

# Or directly:
PYTHONPATH=src uv run uvicorn src.app.api.http.app:app --reload

# Create a user (triggers onboarding workflow)
curl -X POST http://localhost:8000/users/ \\
  -H "Content-Type: application/json" \\
  -d '{"email": "test@example.com", "first_name": "Test", "last_name": "User"}'

# Check onboarding status
curl http://localhost:8000/users/user-123/onboarding

# Check health
curl http://localhost:8000/health/

# View workflows in Temporal UI
# Open http://localhost:8081 in browser
"""
