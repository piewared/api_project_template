"""FastAPI dependency implementations."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from src.core.entities.user import User as UserEntity
from src.core.entities.user_identity import UserIdentity
from src.core.repositories.user_repo import UserIdentityRepository, UserRepository
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
    id='93743658555595339',
    first_name="Development",
    last_name="User",
    email="dev@example.com",
)


async def get_current_user(request: Request, db: Session = Depends(get_session)) -> UserEntity:
    """Authenticate the request using a Bearer token, with JIT user provisioning."""

    if settings.environment == "development":
        request.state.claims = getattr(
            request.state, "claims", {"iss": "local-dev", "sub": "dev-user"}
        )
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

    if not issuer or not subject:
        raise HTTPException(
            status_code=401, detail="JWT missing required issuer or subject claims"
        )

    identity_repo = UserIdentityRepository(db)
    user_repo = UserRepository(db)

    # Try to find existing identity
    identity = None
    if uid:
        identity = identity_repo.get_by_uid(uid)
    if identity is None:
        identity = identity_repo.get_by_issuer_subject(issuer, subject)

    # JIT provisioning: create user and identity if they don't exist
    if identity is None:
        # Extract user information from JWT claims
        email = claims.get("email")
        first_name = claims.get("given_name", claims.get("first_name", ""))
        last_name = claims.get("family_name", claims.get("last_name", ""))

        # Fallback to extracting name from email or subject if no name claims
        if not first_name and not last_name:
            if email and "@" in email:
                name_part = email.split("@")[0]
                first_name = name_part.replace(".", " ").replace("_", " ").title()
                last_name = ""
            elif subject:
                first_name = f"User {subject[-8:]}"  # Use last 8 chars of subject
                last_name = ""

        # Create the new user
        new_user = UserEntity(
            first_name=first_name or "Unknown",
            last_name=last_name or "User",
            email=email,
        )

        created_user = user_repo.create(new_user)

        # Create the identity mapping
        new_identity = UserIdentity(
            issuer=issuer,
            subject=subject,
            uid_claim=uid,
            user_id=created_user.id,
        )

        identity = identity_repo.create(new_identity)
        user = created_user
    else:
        # Load existing user
        user = user_repo.get(identity.user_id)
        if user is None:
            raise HTTPException(
                status_code=500, detail="User identity exists but user not found"
            )

    request.state.claims = claims
    request.state.scopes = jwt_service.extract_scopes(claims)
    request.state.roles = jwt_service.extract_roles(claims)
    request.state.uid = uid
    return user


def require_scope(required_scope: str):
    async def dep(request: Request) -> None:
        scopes: set[str] = getattr(request.state, "scopes", set())
        if required_scope not in scopes:
            raise HTTPException(
                status_code=403, detail=f"Missing required scope: {required_scope}"
            )

    return dep


def require_role(required_role: str):
    async def dep(request: Request) -> None:
        roles: set[str] = getattr(request.state, "roles", set())
        if required_role not in roles:
            raise HTTPException(
                status_code=403, detail=f"Missing required role: {required_role}"
            )

    return dep
