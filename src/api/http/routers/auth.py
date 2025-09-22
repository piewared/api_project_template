from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from src.api.http.deps import get_current_user, require_role, require_scope
from src.entities.user import User

router_jit = APIRouter(prefix="/jit", tags=["auth-jit"])


class MeResponse(BaseModel):
    user_id: str
    email: str
    scopes: list[str]
    roles: list[str]
    claims: dict[str, Any]


@router_jit.get("/me", response_model=MeResponse)
async def get_me(
    request: Request, user: User = Depends(get_current_user)
) -> dict[str, Any]:
    # Mirror the authenticated user context for clients that need their claims
    return {
        "user_id": str(user.id),
        "email": user.email,
        "scopes": list(getattr(request.state, "scopes", [])),
        "roles": list(getattr(request.state, "roles", [])),
        "claims": getattr(request.state, "claims", {}),
    }


@router_jit.get("/protected-scope")
async def protected_scope(
    user: User = Depends(get_current_user),
    dep: None = Depends(require_scope("read:protected")),
) -> dict[str, Any]:
    # Example endpoint that enforces a scope requirement
    return {"message": "You have the required scope!", "user_id": str(user.id)}


@router_jit.get("/protected-role")
async def protected_role(
    user: User = Depends(get_current_user), dep: None = Depends(require_role("admin"))
) -> dict[str, Any]:
    # Example endpoint that enforces a role requirement
    return {"message": "You have the required role!", "user_id": str(user.id)}
