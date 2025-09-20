"""FastAPI dependency implementations."""

from __future__ import annotations

from typing import Iterator, Set

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from src.core.entities.user import User as UserEntity
from src.core.repositories.user_repo import UserRepository, UserIdentityRepository
from src.core.services import jwt_service
from src.runtime.db import session
from src.runtime.settings import settings


def get_session() -> Iterator[Session]:
    """Yield a database session tied to the current request lifecycle."""

    db = session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Add your application-specific repository dependencies here
# Example:
# def get_your_repo(db: Session = Depends(get_session)) -> YourRepository:
#     return YourRepository(db)


_DEV_USER = UserEntity(
    id=93743658555595339,
    first_name="Development",
    last_name="User",
    email="dev@example.com",
)


async def get_current_user(request: Request, db: Session = Depends(get_session)) -> UserEntity:
    """Authenticate the request using a Bearer token, or return the dev user when allowed."""

    if settings.environment == "development":
        request.state.claims = getattr(request.state, "claims", {"iss": "local-dev", "sub": "dev-user"})
        request.state.scopes = getattr(request.state, "scopes", set()) or {"read:all"}
        request.state.roles = getattr(request.state, "roles", set()) or {"admin"}
        request.state.uid = getattr(request.state, "uid", "dev-user")
        return _DEV_USER

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = auth_header.split(" ", 1)[1]
    claims = await jwt_service.verify_jwt(token)
    uid = jwt_service.extract_uid(claims)
    issuer = claims.get("iss")
    subject = claims.get("sub")

    identity_repo = UserIdentityRepository(db)
    user_repo = UserRepository(db)

    identity = None
    if uid:
        identity = identity_repo.get_by_uid(uid)
    if identity is None and issuer and subject:
        identity = identity_repo.get_by_issuer_subject(issuer, subject)

    if identity is None:
        raise HTTPException(status_code=403, detail="User identity not mapped")

    user = user_repo.get(identity.user_id)
    if user is None:
        raise HTTPException(status_code=403, detail="User not found")

    request.state.claims = claims
    request.state.scopes = jwt_service.extract_scopes(claims)
    request.state.roles = jwt_service.extract_roles(claims)
    request.state.uid = uid
    return user


def require_scope(required_scope: str):
    async def dep(request: Request) -> None:
        scopes: Set[str] = getattr(request.state, "scopes", set())
        if required_scope not in scopes:
            raise HTTPException(status_code=403, detail=f"Missing required scope: {required_scope}")

    return dep


def require_role(required_role: str):
    async def dep(request: Request) -> None:
        roles: Set[str] = getattr(request.state, "roles", set())
        if required_role not in roles:
            raise HTTPException(status_code=403, detail=f"Missing required role: {required_role}")

    return dep
