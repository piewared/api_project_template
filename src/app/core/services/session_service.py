"""Session management service for BFF authentication pattern."""

import hashlib
import hmac
import secrets
import time
from typing import Any

from pydantic import BaseModel

from src.app.core.services import jwt_service, oidc_client_service
from src.app.entities.core.user import User, UserRepository
from src.app.entities.core.user_identity import UserIdentity, UserIdentityRepository
from src.app.runtime.context import get_config
from src.app.runtime.db import session

main_config = get_config()


class AuthSession(BaseModel):
    """Temporary session for OIDC authorization flow."""

    id: str
    pkce_verifier: str
    state: str
    provider: str
    redirect_uri: str
    created_at: int
    expires_at: int


class UserSession(BaseModel):
    """Persistent user session after successful authentication."""

    id: str
    user_id: str
    provider: str
    refresh_token: str | None
    access_token: str | None
    access_token_expires_at: int | None
    created_at: int
    last_accessed_at: int
    expires_at: int


# In-memory storage for auth sessions (use Redis in production)
_auth_sessions: dict[str, AuthSession] = {}
_user_sessions: dict[str, UserSession] = {}


def create_auth_session(
    pkce_verifier: str, state: str, provider: str, redirect_uri: str
) -> str:
    """Create temporary auth session for OIDC flow.

    Args:
        pkce_verifier: PKCE code verifier
        state: CSRF state parameter
        provider: OIDC provider identifier
        redirect_uri: Post-auth redirect URI

    Returns:
        Session ID
    """
    session_id = secrets.token_urlsafe(32)
    now = int(time.time())

    auth_session = AuthSession(
        id=session_id,
        pkce_verifier=pkce_verifier,
        state=state,
        provider=provider,
        redirect_uri=redirect_uri,
        created_at=now,
        expires_at=now + 600,  # 10 minutes
    )

    _auth_sessions[session_id] = auth_session
    return session_id


def get_auth_session(session_id: str) -> AuthSession | None:
    """Get auth session by ID.

    Args:
        session_id: Session identifier

    Returns:
        Auth session or None if not found/expired
    """
    auth_session = _auth_sessions.get(session_id)
    if not auth_session:
        return None

    # Check expiry
    if time.time() > auth_session.expires_at:
        del _auth_sessions[session_id]
        return None

    return auth_session


def delete_auth_session(session_id: str) -> None:
    """Delete auth session.

    Args:
        session_id: Session identifier
    """
    _auth_sessions.pop(session_id, None)


async def provision_user_from_claims(claims: dict[str, Any], provider: str) -> User:
    """Provision user from OIDC claims (JIT provisioning).

    Args:
        claims: User claims from OIDC provider
        provider: OIDC provider identifier

    Returns:
        User object (created or existing)
    """
    db = session()
    try:
        issuer = claims.get("iss")
        subject = claims.get("sub")

        if not issuer or not subject:
            raise ValueError("Missing required iss or sub claims")

        uid = jwt_service.extract_uid(claims)
        identity_repo = UserIdentityRepository(db)
        user_repo = UserRepository(db)

        # Try to find existing identity
        identity = None
        if uid:
            identity = identity_repo.get_by_uid(uid)
        if identity is None:
            identity = identity_repo.get_by_issuer_subject(issuer, subject)

        if identity is None:
            # Create new user
            email = claims.get("email")
            first_name = claims.get("given_name", claims.get("first_name", ""))
            last_name = claims.get("family_name", claims.get("last_name", ""))

            # Fallback name generation
            if not first_name and not last_name:
                if email and "@" in email:
                    name_part = email.split("@")[0]
                    first_name = name_part.replace(".", " ").replace("_", " ").title()
                    last_name = ""
                elif subject:
                    first_name = f"User {subject[-8:]}"
                    last_name = ""

            new_user = User(
                first_name=first_name or "Unknown",
                last_name=last_name or "User",
                email=email,
            )

            created_user = user_repo.create(new_user)

            # Create identity mapping
            new_identity = UserIdentity(
                issuer=issuer,
                subject=subject,
                uid_claim=uid,
                user_id=created_user.id,
            )

            identity_repo.create(new_identity)
            db.commit()
            return created_user
        else:
            # Return existing user - but should we update their info?
            user = user_repo.get(identity.user_id)
            if user is None:
                raise ValueError("User identity exists but user not found")

            # Update user with fresh claims data
            email = claims.get("email")
            first_name = claims.get("given_name", claims.get("first_name", ""))
            last_name = claims.get("family_name", claims.get("last_name", ""))

            # Update user fields if they exist in claims
            updated = False
            if email and email != user.email:
                user.email = email
                updated = True
            if first_name and first_name != user.first_name:
                user.first_name = first_name
                updated = True
            if last_name and last_name != user.last_name:
                user.last_name = last_name
                updated = True

            if updated:
                user_repo.update(user)
                db.commit()

            return user

    finally:
        db.close()


def create_user_session(
    user_id: str,
    provider: str,
    refresh_token: str | None,
    access_token: str | None,
    expires_at: int | None,
) -> str:
    """Create persistent user session.

    Args:
        user_id: Internal user ID
        provider: OIDC provider identifier
        refresh_token: OAuth refresh token
        access_token: OAuth access token
        expires_at: Access token expiry timestamp

    Returns:
        Session ID
    """
    session_id = secrets.token_urlsafe(32)
    now = int(time.time())

    user_session = UserSession(
        id=session_id,
        user_id=user_id,
        provider=provider,
        refresh_token=refresh_token,
        access_token=access_token,
        access_token_expires_at=expires_at,
        created_at=now,
        last_accessed_at=now,
        expires_at=now + main_config.app.session_max_age,
    )

    _user_sessions[session_id] = user_session
    return session_id


def get_user_session(session_id: str) -> UserSession | None:
    """Get user session by ID.

    Args:
        session_id: Session identifier

    Returns:
        User session or None if not found/expired
    """
    user_session = _user_sessions.get(session_id)
    if not user_session:
        return None

    # Check expiry
    now = int(time.time())
    if now > user_session.expires_at:
        del _user_sessions[session_id]
        return None

    # Update last accessed time
    user_session.last_accessed_at = now
    return user_session


def delete_user_session(session_id: str) -> None:
    """Delete user session.

    Args:
        session_id: Session identifier
    """
    _user_sessions.pop(session_id, None)


async def refresh_user_session(session_id: str) -> str:
    """Refresh user session using stored refresh token.

    Args:
        session_id: Current session identifier

    Returns:
        New session ID

    Raises:
        ValueError: If session not found or refresh fails
    """
    user_session = get_user_session(session_id)
    if not user_session:
        raise ValueError("Session not found or expired")

    if not user_session.refresh_token:
        raise ValueError("No refresh token available")

    try:
        # Refresh tokens with provider
        tokens = await oidc_client_service.refresh_access_token(
            user_session.refresh_token, user_session.provider
        )

        # Create new session with refreshed tokens
        new_session_id = create_user_session(
            user_id=user_session.user_id,
            provider=user_session.provider,
            refresh_token=tokens.refresh_token or user_session.refresh_token,
            access_token=tokens.access_token,
            expires_at=tokens.expires_at,
        )

        # Delete old session
        delete_user_session(session_id)

        return new_session_id

    except Exception as e:
        # Delete invalid session
        delete_user_session(session_id)
        raise ValueError(f"Token refresh failed: {str(e)}") from e


def generate_csrf_token(session_id: str) -> str:
    """Generate CSRF token for session.

    Args:
        session_id: Session identifier

    Returns:
        CSRF token
    """
    # Create HMAC-based CSRF token
    secret_key = (
        main_config.app.session_jwt_secret.encode() if main_config.app.session_jwt_secret else b"dev-secret"
    )
    message = f"{session_id}:{int(time.time() // 3600)}"  # Hour-based

    csrf_token = hmac.new(secret_key, message.encode(), hashlib.sha256).hexdigest()

    return csrf_token


def validate_csrf_token(session_id: str, csrf_token: str | None) -> bool:
    """Validate CSRF token for session.

    Args:
        session_id: Session identifier
        csrf_token: CSRF token to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        if csrf_token is None:
            return False
        expected_token = generate_csrf_token(session_id)
        return hmac.compare_digest(expected_token, csrf_token)
    except Exception:
        return False
