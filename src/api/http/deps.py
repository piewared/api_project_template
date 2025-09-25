"""FastAPI dependency implementations."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from src.core.services import jwt_service
from src.core.services.session_service import get_user_session
from src.entities.user import User, UserRepository
from src.entities.user_identity.entity import UserIdentity
from src.entities.user_identity.repository import UserIdentityRepository
from src.runtime.config import get_config
from src.runtime.db import session

main_config = get_config()


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


_DEV_USER = User(
    id="93743658555595339",
    first_name="Development",
    last_name="User",
    email="dev@example.com",
)


async def get_current_user(
    request: Request, db: Session = Depends(get_session)
) -> User:
    """Authenticate the request using a Bearer token, with JIT user provisioning."""

    if main_config.environment == "development":
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
        new_user = User(
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
    """Create a dependency that requires a specific scope for the authenticated user."""

    async def dep(request: Request) -> None:
        scopes: set[str] = getattr(request.state, "scopes", set())
        if required_scope not in scopes:
            raise HTTPException(
                status_code=403, detail=f"Missing required scope: {required_scope}"
            )

    return dep


def require_role(required_role: str):
    """Create a dependency that requires a specific role for the authenticated user."""

    async def dep(request: Request) -> None:
        roles: set[str] = getattr(request.state, "roles", set())
        if required_role not in roles:
            raise HTTPException(
                status_code=403, detail=f"Missing required role: {required_role}"
            )

    return dep


async def _authenticate_with_session(
    request: Request, db: Session, required: bool = False
) -> User | None:
    """
    Common helper for session-based authentication.

    Args:
        request: FastAPI request object
        db: Database session
        required: If True, raises HTTPException when session is missing/invalid
                 If False, returns None when session is missing/invalid

    Returns:
        User object if authenticated, None if not authenticated and not required

    Raises:
        HTTPException: If required=True and authentication fails
    """
    # Development mode bypass
    if main_config.environment == "development":
        request.state.claims = getattr(
            request.state, "claims", {"iss": "local-dev", "sub": "dev-user"}
        )
        request.state.scopes = getattr(request.state, "scopes", set()) or {"read:all"}
        request.state.roles = getattr(request.state, "roles", set()) or {"admin"}
        request.state.uid = getattr(request.state, "uid", "dev-user")
        request.state.auth_method = "development"
        return _DEV_USER

    # Try session-based authentication
    session_id = request.cookies.get("session_id")
    if not session_id:
        if required:
            raise HTTPException(status_code=401, detail="Session required")
        return None

    try:
        user_session = get_user_session(session_id)
        if not user_session:
            if required:
                raise HTTPException(
                    status_code=401, detail="Invalid or expired session"
                )
            return None

        # Load user from database
        user_repo = UserRepository(db)
        user = user_repo.get(str(user_session.user_id))
        if not user:
            if required:
                raise HTTPException(status_code=401, detail="User not found")
            return None

        # Store session info in request state
        request.state.session_id = session_id
        request.state.user_session = user_session
        request.state.auth_method = "session"

        # Set empty scope/role info for session auth (could be extended to store in session)
        request.state.scopes = set()
        request.state.roles = set()
        request.state.uid = None
        request.state.claims = {}

        return user
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception:
        # Other exceptions - return None or raise based on required flag
        if required:
            raise HTTPException(
                status_code=401, detail="Session authentication failed"
            ) from None
        return None


async def get_authenticated_user(
    request: Request, db: Session = Depends(get_session)
) -> User:
    """
    Unified authentication dependency that works with both JWT and session-based auth.

    Authentication priority:
    1. Session cookie (BFF pattern) - for web clients
    2. Bearer token (JWT pattern) - for mobile/API clients
    3. Development mode fallback
    """

    # Try session-based authentication first (BFF pattern)
    user = await _authenticate_with_session(request, db, required=False)
    if user:
        return user

    # Try JWT Bearer token authentication (mobile/API pattern)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            claims = await jwt_service.verify_jwt(token)
            uid = jwt_service.extract_uid(claims)
            issuer = claims.get("iss")
            subject = claims.get("sub")

            if not issuer or not subject:
                raise HTTPException(
                    status_code=401,
                    detail="JWT missing required issuer or subject claims",
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
                        first_name = (
                            name_part.replace(".", " ").replace("_", " ").title()
                        )
                        last_name = ""
                    elif subject:
                        first_name = (
                            f"User {subject[-8:]}"  # Use last 8 chars of subject
                        )
                        last_name = ""

                # Create the new user
                new_user = User(
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
                        status_code=500,
                        detail="User identity exists but user not found",
                    )

            # Store JWT info in request state
            request.state.claims = claims
            request.state.scopes = jwt_service.extract_scopes(claims)
            request.state.roles = jwt_service.extract_roles(claims)
            request.state.uid = uid
            request.state.auth_method = "jwt"

            return user

        except HTTPException:
            # Re-raise HTTP exceptions (auth failures)
            raise
        except Exception:
            # JWT auth failed, continue to no auth found
            pass

    # No valid authentication found
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide either a session cookie or Bearer token.",
    )


async def get_session_only_user(
    request: Request, db: Session = Depends(get_session)
) -> User:
    """
    Session-only authentication dependency for BFF endpoints.
    Only accepts session cookies, not JWT tokens.
    """
    user = await _authenticate_with_session(request, db, required=True)
    # Type checker doesn't know that required=True guarantees non-None return
    assert user is not None  # This should never be None when required=True
    return user


async def get_optional_session_user(
    request: Request, db: Session = Depends(get_session)
) -> User | None:
    """
    Optional session-only authentication dependency for BFF endpoints.
    Returns None if no session, doesn't raise HTTPException.
    Only accepts session cookies, not JWT tokens.
    """
    return await _authenticate_with_session(request, db, required=False)
