"""Authentication endpoints for OIDC relying party (client)."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from src.app.api.http.deps import get_authenticated_user, require_role, require_scope
from src.app.entities.core.user import User

router_jit = APIRouter(prefix="/jit", tags=["auth-jit"])


class MeResponse(BaseModel):
    """Response model for the /me endpoint - useful for clients to understand their auth state."""

    user_id: str
    email: str
    scopes: list[str]
    roles: list[str]
    claims: dict[str, Any]


@router_jit.get("/me", response_model=MeResponse)
async def get_me(
    request: Request, user: User = Depends(get_authenticated_user)
) -> dict[str, Any]:
    """Development/debugging endpoint - mirrors authenticated user context.

    This endpoint allows clients to understand their current authentication state
    including the domain User object and the claims from their OIDC token.
    Works with both JWT and session-based authentication.
    """
    # Include auth method in response for debugging
    print(f"Request state: {request.state}")
    print(f"user: {user}")
    auth_method = getattr(request.state, "auth_method", "unknown")

    return {
        "user_id": str(user.id),
        "email": user.email,
        "scopes": list(getattr(request.state, "scopes", [])),
        "roles": list(getattr(request.state, "roles", [])),
        "claims": getattr(request.state, "claims", {}),
        "auth_method": auth_method,
    }


@router_jit.get("/protected-scope")
async def protected_scope(
    user: User = Depends(get_authenticated_user),
    dep: None = Depends(require_scope("read:protected")),
) -> dict[str, Any]:
    """Example endpoint demonstrating scope-based authorization."""
    return {"message": "You have the required scope!", "user_id": str(user.id)}


@router_jit.get("/protected-role")
async def protected_role(
    user: User = Depends(get_authenticated_user),
    dep: None = Depends(require_role("admin")),
) -> dict[str, Any]:
    """Example endpoint demonstrating role-based authorization."""
    return {"message": "You have the required role!", "user_id": str(user.id)}
