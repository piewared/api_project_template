"""Enhanced session management service with security improvements."""

import secrets
import time
from typing import Any

from sqlmodel import Session

from src.app.core.models.session import AuthSession, UserSession
from src.app.core.security import (
    generate_csrf_token,
    hash_client_fingerprint,
    sanitize_return_url,
    validate_csrf_token,
)
from src.app.core.services import jwt_service, oidc_client_service
from src.app.core.storage.session_storage import get_session_storage
from src.app.entities.core.user import User, UserRepository
from src.app.entities.core.user_identity import UserIdentity, UserIdentityRepository
from src.app.runtime.context import get_config

main_config = get_config()


async def create_auth_session(
    pkce_verifier: str,
    state: str,
    nonce: str,
    provider: str,
    return_to: str,
    client_fingerprint_hash: str,
) -> str:
    """Create secure auth session for OIDC flow.

    Args:
        pkce_verifier: PKCE code verifier
        state: CSRF state parameter
        nonce: OIDC nonce parameter
        provider: OIDC provider identifier
        return_to: Post-auth redirect URI (sanitized)
        client_fingerprint: Client browser fingerprint hash

    Returns:
        Session ID
    """
    storage = await get_session_storage()

    # Sanitize return URL for security
    safe_return_to = sanitize_return_url(
        return_to, allowed_hosts=main_config.oidc.allowed_redirect_hosts
    )

    auth_session = AuthSession.create(
        session_id=secrets.token_urlsafe(32),
        pkce_verifier=pkce_verifier,
        state=state,
        nonce=nonce,
        provider=provider,
        return_to=safe_return_to,
        client_fingerprint_hash=client_fingerprint_hash,
        ttl_seconds=600,  # 10 minutes
    )

    await storage.set(f"auth:{auth_session.id}", auth_session, 600)
    return auth_session.id


async def get_auth_session(session_id: str) -> AuthSession | None:
    """Get auth session by ID with security validation.

    Args:
        session_id: Session identifier

    Returns:
        Auth session or None if not found/expired/invalid
    """
    storage = await get_session_storage()
    auth_session: AuthSession | None = await storage.get(
        f"auth:{session_id}", AuthSession
    )

    if not auth_session:
        return None

    # Validate session hasn't been used and isn't expired
    if auth_session.used or auth_session.is_expired():
        await storage.delete(f"auth:{session_id}")
        return None

    return auth_session


async def validate_auth_session(
    session_id: str,
    state: str,
    client_fingerprint_hash: str,
) -> AuthSession | None:
    """Validate auth session with security checks.

    Args:
        session_id: Session identifier
        state: State parameter to validate
        client_fingerprint_hash: Client fingerprint to validate

    Returns:
        Valid auth session or None if validation fails
    """
    auth_session = await get_auth_session(session_id)
    if not auth_session:
        return None

    # Validate state parameter (CSRF protection)
    if state != auth_session.state:
        await delete_auth_session(session_id)
        return None
    # Validate client fingerprint (session hijacking protection)
    if client_fingerprint_hash != auth_session.client_fingerprint_hash:
        await delete_auth_session(session_id)
        return None

    return auth_session


async def mark_auth_session_used(session_id: str) -> None:
    """Mark auth session as used to prevent replay attacks.

    Args:
        session_id: Session identifier
    """
    storage = await get_session_storage()
    auth_session = await storage.get(f"auth:{session_id}", AuthSession)

    if auth_session:
        auth_session.mark_used()
        await storage.set(f"auth:{auth_session.id}", auth_session, 600)


async def delete_auth_session(session_id: str) -> None:
    """Delete auth session.

    Args:
        session_id: Session identifier
    """
    storage = await get_session_storage()
    await storage.delete(f"auth:{session_id}")


async def update_auth_session(
    session_id: str,
    return_to: str | None = None,
    extension_seconds: int | None = None,
) -> AuthSession:
    """Update auth session with new data.

    Args:
        session_id: Session identifier
        return_to: Updated return URL (will be sanitized)
        extension_seconds: Extension time in seconds (can be negative to expire early)

    Returns:
        Updated auth session

    Raises:
        ValueError: If session not found or already used
    """
    storage = await get_session_storage()
    auth_session = await storage.get(f"auth:{session_id}", AuthSession)

    if not auth_session:
        raise ValueError("Auth session not found")

    if auth_session.used:
        raise ValueError("Auth session already used")

    if auth_session.is_expired():
        await storage.delete(f"auth:{session_id}")
        raise ValueError("Auth session expired")

    # Update return URL if provided (with sanitization)
    if return_to is not None:
        safe_return_to = sanitize_return_url(
            return_to, allowed_hosts=main_config.oidc.allowed_redirect_hosts
        )
        auth_session.return_to = safe_return_to

    # Extend/modify session expiry if requested
    if extension_seconds is not None and extension_seconds != 0:
        auth_session.expires_at = int(time.time()) + extension_seconds

    # Check if session is now expired (e.g., from negative extension)
    if auth_session.is_expired():
        await storage.delete(f"auth:{auth_session.id}")
        return auth_session  # Return the expired session without storing it

    # Save updated session
    ttl = max(
        1, auth_session.expires_at - int(time.time())
    )  # Ensure ttl is at least 1 second
    await storage.set(f"auth:{auth_session.id}", auth_session, ttl)

    return auth_session


async def provision_user_from_claims(session: Session, claims: jwt_service.TokenClaims, provider: str) -> User:
    """Provision user from OIDC claims (JIT provisioning).

    Args:
        claims: User claims from OIDC provider
        provider: OIDC provider identifier

    Returns:
        User object (created or existing)
    """
    try:
        issuer = claims.issuer
        subject = claims.subject

        if not issuer or not subject:
            raise ValueError("Missing required iss or sub claims")

        uid = jwt_service.extract_uid(claims.all_claims)
        identity_repo = UserIdentityRepository(session)
        user_repo = UserRepository(session)

        # Try to find existing identity
        identity = None
        if uid:
            identity = identity_repo.get_by_uid(uid)
        if identity is None:
            identity = identity_repo.get_by_issuer_subject(issuer, subject)

        if identity is None:
            # Create new user
            email = claims.email
            first_name = claims.given_name
            last_name = claims.family_name

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
            session.commit()
            return created_user
        else:
            # Return existing user - but should we update their info?
            user = user_repo.get(identity.user_id)
            if user is None:
                raise ValueError("User identity exists but user not found")

            # Update user with fresh claims data
            email = claims.email
            first_name = claims.given_name
            last_name = claims.family_name

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
                session.commit()

            return user
    except Exception as e:
        session.rollback()
        raise

    finally:
        session.close()


async def create_user_session(
    user_id: str,
    provider: str,
    client_fingerprint: str,
    refresh_token: str | None = None,
    access_token: str | None = None,
    access_token_expires_at: int | None = None,
) -> str:
    """Create secure user session.

    Args:
        user_id: Internal user ID
        provider: OIDC provider identifier
        client_fingerprint: Client browser fingerprint
        refresh_token: OAuth refresh token
        access_token: OAuth access token
        access_token_expires_at: Access token expiry timestamp

    Returns:
        Session ID
    """
    storage = await get_session_storage()

    user_session = UserSession.create(
        session_id=secrets.token_urlsafe(32),
        user_id=user_id,
        provider=provider,
        client_fingerprint=hash_client_fingerprint(client_fingerprint),
        session_max_age=main_config.app.session_max_age,
    )

    # Set token information if provided
    if access_token:
        user_session.update_tokens(
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expires_at=access_token_expires_at,
        )

    await storage.set(
        f"user:{user_session.id}", user_session, main_config.app.session_max_age
    )
    return user_session.id


async def get_user_session(session_id: str) -> UserSession | None:
    """Get user session by ID with security validation.

    Args:
        session_id: Session identifier

    Returns:
        User session or None if not found/expired
    """
    storage = await get_session_storage()
    user_session = await storage.get(f"user:{session_id}", UserSession)

    if not user_session:
        return None

    # Check expiry
    if user_session.is_expired():
        await storage.delete(f"user:{session_id}")
        return None

    # Update last accessed time
    user_session.update_access()
    await storage.set(
        f"user:{user_session.id}", user_session, main_config.app.session_max_age
    )

    return user_session


async def validate_user_session(
    session_id: str,
    client_fingerprint: str,
) -> UserSession | None:
    """Validate user session with security checks.

    Args:
        session_id: Session identifier
        client_fingerprint: Client fingerprint to validate

    Returns:
        Valid user session or None if validation fails
    """
    user_session = await get_user_session(session_id)
    if not user_session:
        return None

    # Validate client fingerprint (session hijacking protection)
    expected_hash = hash_client_fingerprint(client_fingerprint)
    if expected_hash != user_session.client_fingerprint:
        await delete_user_session(session_id)
        return None

    return user_session


async def rotate_user_session(session_id: str) -> str:
    """Rotate user session ID for security.

    Args:
        session_id: Current session identifier

    Returns:
        New session ID

    Raises:
        ValueError: If session not found
    """
    storage = await get_session_storage()
    user_session = await storage.get(f"user:{session_id}", UserSession)

    if not user_session:
        raise ValueError("Session not found")

    # Generate new session ID
    new_session_id = secrets.token_urlsafe(32)
    user_session.rotate_session_id(new_session_id)

    # Store with new ID and remove old
    await storage.set(
        f"user:{user_session.id}", user_session, main_config.app.session_max_age
    )
    await storage.delete(f"user:{session_id}")

    return new_session_id


async def delete_user_session(session_id: str) -> None:
    """Delete user session.

    Args:
        session_id: Session identifier
    """
    storage = await get_session_storage()
    await storage.delete(f"user:{session_id}")


async def refresh_user_session(session_id: str) -> str:
    """Refresh user session using stored refresh token.

    Args:
        session_id: Current session identifier

    Returns:
        New session ID

    Raises:
        ValueError: If session not found or refresh fails
    """
    user_session = await get_user_session(session_id)
    if not user_session:
        raise ValueError("Session not found or expired")

    if not user_session.refresh_token:
        raise ValueError("No refresh token available")

    try:
        # Refresh tokens with provider
        tokens = await oidc_client_service.refresh_access_token(
            user_session.refresh_token, user_session.provider
        )

        # Update session with refreshed tokens
        user_session.update_tokens(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token or user_session.refresh_token,
            access_token_expires_at=tokens.expires_at,
        )

        # Save the updated session with new tokens first
        storage = await get_session_storage()
        await storage.set(
            f"user:{user_session.id}", user_session, main_config.app.session_max_age
        )

        # Then rotate session ID for added security
        new_session_id = await rotate_user_session(session_id)
        return new_session_id

    except Exception as e:
        # Delete invalid session
        await delete_user_session(session_id)
        raise ValueError(f"Token refresh failed: {str(e)}") from e


async def update_user_session(
    session_id: str,
    access_token: str | None = None,
    refresh_token: str | None = None,
    access_token_expires_at: int | None = None,
    client_fingerprint: str | None = None,
    extension_seconds: int | None = None,
) -> UserSession:
    """Update user session with new data.

    Args:
        session_id: Session identifier
        access_token: New access token (optional)
        refresh_token: New refresh token (optional)
        access_token_expires_at: New access token expiry (optional)
        client_fingerprint: Updated client fingerprint (optional)
        extension_seconds: Custom extension time (defaults to session_max_age if extend_session=True)

    Returns:
        Updated user session

    Raises:
        ValueError: If session not found
    """
    storage = await get_session_storage()
    user_session = await storage.get(f"user:{session_id}", UserSession)

    if not user_session:
        raise ValueError("Session not found")

    # Update tokens if provided
    if (
        access_token is not None
        or refresh_token is not None
        or access_token_expires_at is not None
    ):
        user_session.update_tokens(
            access_token=access_token,
            refresh_token=refresh_token,
            access_token_expires_at=access_token_expires_at,
        )

    # Update client fingerprint if provided (re-hash for security)
    if client_fingerprint is not None:
        user_session.client_fingerprint = hash_client_fingerprint(client_fingerprint)

    # Update access time
    user_session.update_access()

    # Extend session expiry if requested
    if extension_seconds is not None:
        extension_time = extension_seconds or main_config.app.session_max_age
        user_session.expires_at = int(time.time()) + extension_time

    # Check if session is now expired (e.g., from negative extension)
    if user_session.is_expired():
        await storage.delete(f"user:{user_session.id}")
        return user_session  # Return the expired session without storing it

    # Save updated session
    ttl = max(
        1, user_session.expires_at - int(time.time())
    )  # Ensure ttl is at least 1 second
    await storage.set(f"user:{user_session.id}", user_session, ttl)

    return user_session


def get_csrf_token_for_session(session_id: str) -> str:
    """Generate CSRF token for session using security utility.

    Args:
        session_id: Session identifier

    Returns:
        CSRF token
    """
    return generate_csrf_token(session_id)


def validate_csrf_token_for_session(session_id: str, csrf_token: str | None) -> bool:
    """Validate CSRF token for session using security utility.

    Args:
        session_id: Session identifier
        csrf_token: CSRF token to validate

    Returns:
        True if valid, False otherwise
    """
    if csrf_token is None:
        return False

    return validate_csrf_token(session_id, csrf_token)


async def extend_user_session(
    session_id: str, additional_seconds: int | None = None
) -> UserSession:
    """Extend user session expiry time.

    Args:
        session_id: Session identifier
        additional_seconds: Additional seconds to extend (defaults to session_max_age)

    Returns:
        Updated user session

    Raises:
        ValueError: If session not found
    """
    return await update_user_session(
        session_id=session_id, extension_seconds=additional_seconds
    )


async def list_auth_sessions() -> list[AuthSession]:
    """List all active auth sessions.

    Returns:
        List of active auth sessions
    """
    storage = await get_session_storage()
    return await storage.list_sessions("auth:*", AuthSession)


async def list_user_sessions(user_id: str | None = None) -> list[UserSession]:
    """List active user sessions, optionally filtered by user ID.

    Args:
        user_id: Optional user ID to filter sessions by

    Returns:
        List of active user sessions
    """
    storage = await get_session_storage()
    sessions = await storage.list_sessions("user:*", UserSession)

    # Filter by user_id if provided
    if user_id is not None:
        sessions = [s for s in sessions if s.user_id == user_id]

    return sessions


async def count_active_sessions() -> dict[str, int]:
    """Count active auth and user sessions.

    Returns:
        Dictionary with 'auth' and 'user' session counts
    """
    auth_sessions = await list_auth_sessions()
    user_sessions = await list_user_sessions()

    return {"auth": len(auth_sessions), "user": len(user_sessions)}


async def cleanup_expired_sessions() -> dict[str, int]:
    """Clean up expired sessions and return counts.

    Returns:
        Dictionary with cleanup counts for auth and user sessions
    """
    storage = await get_session_storage()
    counts = {"auth": 0, "user": 0}

    # Use storage's built-in cleanup if available
    await storage.cleanup_expired()

    # Get lists of all sessions and check expiry
    try:
        auth_keys = await storage.list_keys("auth:*")
        for key in auth_keys:
            try:
                auth_session = await storage.get(key, AuthSession)
                if not auth_session or auth_session.is_expired():
                    await storage.delete(key)
                    counts["auth"] += 1
            except Exception:
                # Delete corrupted sessions
                await storage.delete(key)
                counts["auth"] += 1

        user_keys = await storage.list_keys("user:*")
        for key in user_keys:
            try:
                user_session = await storage.get(key, UserSession)
                if not user_session or user_session.is_expired():
                    await storage.delete(key)
                    counts["user"] += 1
            except Exception:
                # Delete corrupted sessions
                await storage.delete(key)
                counts["user"] += 1
    except Exception:
        # Fall back to storage cleanup count
        pass

    return counts


async def clear_all_sessions() -> dict[str, int]:
    """Clear all auth and user sessions (admin/testing function).

    WARNING: This will log out all users and invalidate all auth sessions.
    Use with caution, typically only for testing or emergency situations.

    Returns:
        Dictionary with counts of cleared sessions
    """
    storage = await get_session_storage()
    counts = {"auth": 0, "user": 0}

    try:
        # Clear auth sessions
        auth_keys = await storage.list_keys("auth:*")
        for key in auth_keys:
            await storage.delete(key)
            counts["auth"] += 1

        # Clear user sessions
        user_keys = await storage.list_keys("user:*")
        for key in user_keys:
            await storage.delete(key)
            counts["user"] += 1
    except Exception:
        # Fall back gracefully
        pass

    return counts
