"""Enhanced BFF (Backend-for-Frontend) authentication endpoints with security improvements."""

from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlmodel import Session

from src.app.api.http.deps import get_optional_session_user, get_session
from src.app.core.security import (
    extract_client_fingerprint,
    generate_nonce,
    sanitize_return_url,
)
from src.app.core.services import oidc_client_service, session_service
from src.app.entities.core.user import User
from src.app.runtime.context import get_config

router_bff = APIRouter(prefix="/web", tags=["auth-bff"])


class LoginRequest(BaseModel):
    """Request to initiate login flow."""

    redirect_uri: str | None = None
    provider: str = "default"


class AuthState(BaseModel):
    """Current authentication state for web clients."""

    authenticated: bool
    user: dict[str, Any] | None = None
    csrf_token: str | None = None


def _get_secure_cookie_settings() -> dict[str, Any]:
    """Get secure cookie configuration."""
    config = get_config()
    return {
        "httponly": True,
        "secure": config.app.environment == "production",
        "samesite": "lax",
    }


@router_bff.get("/login")
async def initiate_login(
    request: Request,
    provider: str = "default",
    redirect_uri: str | None = None
) -> RedirectResponse:
    """Initiate OIDC login flow with enhanced security.

    Uses PKCE, nonce, CSRF protection, and client fingerprinting.
    Redirects to the identity provider's authorization endpoint.
    """
    config = get_config()

    if provider not in config.oidc.providers:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Generate security parameters
    pkce_verifier, pkce_challenge = oidc_client_service.generate_pkce_pair()
    state = oidc_client_service.generate_state()
    nonce = generate_nonce()

    # Extract client fingerprint for session binding
    client_fingerprint = extract_client_fingerprint(request)

    # Sanitize return URL
    safe_return_uri = redirect_uri or "/"
    if redirect_uri:
        safe_return_uri = sanitize_return_url(
            redirect_uri,
            allowed_hosts=config.oidc.allowed_redirect_hosts
        )

    # Create secure auth session
    session_id = await session_service.create_auth_session(
        pkce_verifier=pkce_verifier,
        state=state,
        nonce=nonce,
        provider=provider,
        return_to=safe_return_uri,
        client_fingerprint_hash=client_fingerprint,
    )

    # Build authorization URL with nonce
    provider_config = config.oidc.providers[provider]
    auth_params = {
        "client_id": provider_config.client_id,
        "response_type": "code",
        "scope": " ".join(provider_config.scopes),
        "redirect_uri": provider_config.redirect_uri,
        "state": state,
        "nonce": nonce,  # OIDC nonce for ID token validation
        "code_challenge": pkce_challenge,
        "code_challenge_method": "S256",
    }

    auth_url = f"{provider_config.authorization_endpoint}?{urlencode(auth_params)}"

    # Set secure session cookie and redirect
    response = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    cookie_settings = _get_secure_cookie_settings()
    response.set_cookie(
        key="auth_session_id",
        value=session_id,
        max_age=600,  # 10 minutes for auth flow
        **cookie_settings
    )

    return response


@router_bff.get("/callback")
async def handle_callback(
    request: Request,
    state: str,
    code: str | None = None,
    error: str | None = None,
    session: Session = Depends(get_session)
) -> RedirectResponse:
    """Handle OIDC callback with enhanced security validation.

    Performs comprehensive validation including state, fingerprint,
    nonce verification, and secure session creation.
    """
    if error:
        raise HTTPException(status_code=400, detail=f"Authorization failed: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    # Get auth session from cookie
    session_id = request.cookies.get("auth_session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing auth session")

    # Extract client fingerprint for validation
    client_fingerprint = extract_client_fingerprint(request)

    # Validate auth session with security checks
    auth_session = await session_service.validate_auth_session(
        session_id=session_id,
        state=state,
        client_fingerprint_hash=client_fingerprint,
    )

    if not auth_session:
        raise HTTPException(status_code=400, detail="Invalid or expired auth session")

    try:
        # Mark session as used to prevent replay attacks
        await session_service.mark_auth_session_used(session_id)

        # Exchange code for tokens
        tokens = await oidc_client_service.exchange_code_for_tokens(
            code=code,
            pkce_verifier=auth_session.pkce_verifier,
            provider=auth_session.provider,
        )
        # Get user info from ID token with nonce validation
        user_claims = await oidc_client_service.get_user_claims(
            access_token=tokens.access_token,
            id_token=tokens.id_token,
            provider=auth_session.provider,
        )
        # Validate nonce in ID token if present
        if tokens.id_token and auth_session.nonce:
            from src.app.core.services import jwt_service
            await jwt_service.verify_jwt(
                token=tokens.id_token,
                expected_nonce=auth_session.nonce
            )
        # Create or update user via JIT provisioning
        user = await session_service.provision_user_from_claims(session,
            user_claims, auth_session.provider
        )
        # Create secure user session
        user_session_id = await session_service.create_user_session(
            user_id=user.id,
            provider=auth_session.provider,
            client_fingerprint=client_fingerprint,
            refresh_token=tokens.refresh_token,
            access_token=tokens.access_token,
            access_token_expires_at=tokens.expires_at,
        )
        # Clean up auth session
        await session_service.delete_auth_session(session_id)

        # Redirect with secure user session cookie
        redirect_url = auth_session.return_to or "/"
        response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

        # Set long-lived secure session cookie
        cookie_settings = _get_secure_cookie_settings()
        response.set_cookie(
            key="user_session_id",
            value=user_session_id,
            max_age=get_config().app.session_max_age,
            **cookie_settings
        )

        # Clear auth session cookie
        response.delete_cookie("auth_session_id")

        return response

    except Exception as e:
        # Clean up auth session on error
        await session_service.delete_auth_session(session_id)
        raise HTTPException(
            status_code=500,
            detail=f"Authentication failed: {str(e)}"
        ) from e


@router_bff.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, str]:
    """Logout user with secure session cleanup.

    Validates CSRF token and optionally redirects to provider logout.
    """
    session_id = request.cookies.get("user_session_id")
    if session_id:
        # Get session info for provider logout
        user_session = await session_service.get_user_session(session_id)

        # Delete server-side session
        await session_service.delete_user_session(session_id)

        # Clear session cookie
        response.delete_cookie("user_session_id")

        # Optionally trigger provider logout
        if (
            user_session
            and get_config().oidc.providers[user_session.provider].end_session_endpoint
        ):
            provider_config = get_config().oidc.providers[user_session.provider]
            logout_params = {
                "post_logout_redirect_uri": get_config().app.base_url,
                "client_id": provider_config.client_id,
            }
            logout_url = (
                f"{provider_config.end_session_endpoint}?{urlencode(logout_params)}"
            )
            return {"message": "Logged out", "provider_logout_url": logout_url}

    return {"message": "Logged out"}


@router_bff.get("/me")
async def get_auth_state(
    request: Request,
    user: User | None = Depends(get_optional_session_user)
) -> AuthState:
    """Get current authentication state with CSRF token for web client."""
    if not user:
        return AuthState(authenticated=False)

    # Generate CSRF token for authenticated users
    session_id = request.cookies.get("user_session_id")
    csrf_token = None
    if session_id:
        csrf_token = session_service.get_csrf_token_for_session(session_id)

    return AuthState(
        authenticated=True,
        user={
            "id": str(user.id),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
        },
        csrf_token=csrf_token,
    )


@router_bff.get("/refresh")
async def refresh_session(request: Request, response: Response) -> dict[str, str]:
    """Refresh user session with security validation.

    Validates client fingerprint and rotates session ID for security.
    """
    session_id = request.cookies.get("user_session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")

    # Extract client fingerprint for validation
    client_fingerprint = extract_client_fingerprint(request)

    # Validate session with fingerprint check
    user_session = await session_service.validate_user_session(
        session_id=session_id,
        client_fingerprint=client_fingerprint,
    )

    if not user_session:
        response.delete_cookie("user_session_id")
        raise HTTPException(status_code=401, detail="Invalid session")

    try:
        # Refresh tokens and rotate session ID
        new_session_id = await session_service.refresh_user_session(session_id)

        # Update session cookie with new ID
        cookie_settings = _get_secure_cookie_settings()
        response.set_cookie(
            key="user_session_id",
            value=new_session_id,
            max_age=get_config().app.session_max_age,
            **cookie_settings
        )

        return {"message": "Session refreshed"}

    except Exception as e:
        # Clear invalid session
        response.delete_cookie("user_session_id")
        raise HTTPException(
            status_code=401,
            detail=f"Session refresh failed: {str(e)}"
        ) from e


@router_bff.post("/validate-csrf")
async def validate_csrf(
    request: Request,
    csrf_token: str
) -> dict[str, bool]:
    """Validate CSRF token for AJAX requests."""
    session_id = request.cookies.get("user_session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")

    is_valid = session_service.validate_csrf_token_for_session(session_id, csrf_token)

    if not is_valid:
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    return {"valid": True}
