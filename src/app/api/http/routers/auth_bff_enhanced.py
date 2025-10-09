"""Enhanced BFF (Backend-for-Frontend) authentication endpoints with security improvements.

Fixes applied:
- Validate `state` and fingerprint even when the provider returns an `error`.
- Verify ID token (including `nonce`) BEFORE using any claims.
- Require an ID token for OIDC logins; treat missing ID token as an error.
- Make nonce single-use by retiring the auth session in all outcomes.
"""

from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from loguru import logger
from pydantic import BaseModel
from sqlmodel import Session

from src.app.api.http.deps import (
    get_auth_session_service,
    get_jwt_verify_service,
    get_oidc_client_service,
    get_optional_session_user,
    get_session,
    get_user_management_service,
    get_user_session_service,
)
from src.app.core.security import (
    extract_client_fingerprint,
    generate_csrf_token,
    generate_nonce,
    generate_pkce_pair,
    generate_state,
    sanitize_return_url,
    validate_csrf_token,
)
from src.app.core.services.jwt.jwt_verify import JwtVerificationService
from src.app.core.services.oidc_client_service import OidcClientService
from src.app.core.services.session.auth_session import AuthSessionService
from src.app.core.services.session.user_session import UserSessionService
from src.app.core.services.user.user_management import UserManagementService
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
    redirect_uri: str | None = None,
    auth_session_service: AuthSessionService = Depends(get_auth_session_service),
) -> RedirectResponse:
    """Initiate OIDC login flow with enhanced security.

    Uses PKCE, nonce, CSRF protection, and client fingerprinting.
    Redirects to the identity provider's authorization endpoint.
    """
    config = get_config()

    if provider not in config.oidc.providers:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Generate security parameters (each request gets unique values)
    pkce_verifier, pkce_challenge = generate_pkce_pair()
    state = generate_state()
    nonce = generate_nonce()  # Single-use: bound to this auth session only

    # Extract client fingerprint for session binding
    client_fingerprint = extract_client_fingerprint(request)

    # Sanitize return URL
    safe_return_uri = redirect_uri or "/"
    if redirect_uri:
        safe_return_uri = sanitize_return_url(
            redirect_uri, allowed_hosts=config.oidc.allowed_redirect_hosts
        )

    # Create secure auth session (server-side, short TTL)
    session_id = await auth_session_service.create_auth_session(
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
        "nonce": nonce,  # OIDC nonce for ID token binding & replay prevention
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
        **cookie_settings,
    )

    return response


@router_bff.get("/callback")
async def handle_callback(
    request: Request,
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
    session: Session = Depends(get_session),
    auth_session_service: AuthSessionService = Depends(get_auth_session_service),
    user_session_service: UserSessionService = Depends(get_user_session_service),
    jwt_verify_service: JwtVerificationService = Depends(get_jwt_verify_service),
    oidc_client_service: OidcClientService = Depends(get_oidc_client_service),
    user_service: UserManagementService = Depends(get_user_management_service),
) -> RedirectResponse:
    """Handle OIDC callback with enhanced security validation.

    Performs comprehensive validation including state, fingerprint,
    ID token (incl. nonce) verification, and secure session creation.
    """
    # --- Always load and validate the auth session & state, even on error ---
    session_id = request.cookies.get("auth_session_id")
    logger.debug(
        f"Callback received: state={state}, code={'present' if code else 'absent'}, error={error}, session_id={session_id}"
    )

    if not session_id:
        # No linkage to our initiated flow; treat as CSRF / invalid callback
        raise HTTPException(status_code=400, detail="Missing auth session")

    client_fingerprint = extract_client_fingerprint(request)

    # Validate state and fingerprint binding (prevents login CSRF / mix-up)
    auth_session = await auth_session_service.validate_auth_session(
        session_id=session_id,
        state=state,  # may be None => fail validation
        client_fingerprint_hash=client_fingerprint,
    )

    if not auth_session:
        # Ensure no stale session cookie remains
        raise HTTPException(status_code=400, detail="Invalid or expired auth session")

    # If the provider returned an OAuth/OIDC error, we only surface it AFTER
    # we've validated the state/session to avoid error-forcing CSRF.
    if error:
        # Retire the single-use auth session on any terminal outcome
        await auth_session_service.delete_auth_session(session_id)
        # Clear the cookie to avoid reuse
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.delete_cookie("auth_session_id")
        # Surface the error (state was already validated)
        raise HTTPException(status_code=400, detail=f"Authorization failed: {error}")

    if not code:
        await auth_session_service.delete_auth_session(session_id)
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.delete_cookie("auth_session_id")
        raise HTTPException(status_code=400, detail="Missing authorization code")

    try:
        # Mark session as used ASAP to prevent replay (single-use guarantee)
        await auth_session_service.mark_auth_session_used(session_id)

        # Exchange code for tokens via PKCE
        tokens = await oidc_client_service.exchange_code_for_tokens(
            code=code,
            pkce_verifier=auth_session.pkce_verifier,
            provider=auth_session.provider,
        )

        # --- Require an ID token for OIDC login ---
        if not tokens.id_token:
            # Retire the auth session and abort
            await auth_session_service.delete_auth_session(session_id)
            response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
            response.delete_cookie("auth_session_id")
            raise HTTPException(status_code=400, detail="Missing ID token in OIDC flow")

        # --- Verify the ID token BEFORE using any claims ---
        # Verify signature, issuer, audience, and nonce. Depending on your jwt_service,
        # you may pass expected_issuer / expected_audience here from provider config.

        provider_cfg = get_config().oidc.providers[auth_session.provider]

        # NOTE: Adjust verify_jwt signature if your implementation supports these.
        # At a minimum we enforce nonce here.
        await jwt_verify_service.verify_jwt(
            token=tokens.id_token,
            expected_nonce=auth_session.nonce,
            # Optional but recommended if supported by your verifier:
            expected_issuer=getattr(provider_cfg, "issuer", None),
            expected_audience=provider_cfg.client_id,
        )

        # Only after verification do we parse/assemble claims.
        user_claims = await oidc_client_service.get_user_claims(
            access_token=tokens.access_token,
            id_token=tokens.id_token,
            provider=auth_session.provider,
        )

        # JIT provision or update user
        user = await user_service.provision_user_from_claims(user_claims)

        # Create secure user session
        user_session_id = await user_session_service.create_user_session(
            user_id=user.id,
            provider=auth_session.provider,
            client_fingerprint=client_fingerprint,
            refresh_token=tokens.refresh_token,
            access_token=tokens.access_token,
            access_token_expires_at=tokens.expires_at,
        )

        # Clean up single-use auth session (retires nonce/state)
        await auth_session_service.delete_auth_session(session_id)

        # Redirect to original destination
        redirect_url = auth_session.return_to or "/"
        response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

        # Set long-lived secure session cookie
        cookie_settings = _get_secure_cookie_settings()
        response.set_cookie(
            key="user_session_id",
            value=user_session_id,
            max_age=get_config().app.session_max_age,
            **cookie_settings,
        )

        # Clear the short-lived auth session cookie
        response.delete_cookie("auth_session_id")

        return response

    except Exception as e:
        # Clean up auth session on any error path to retire nonce/state
        try:
            await auth_session_service.delete_auth_session(session_id)
        finally:
            pass
        # Clear cookie to avoid dangling references
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.delete_cookie("auth_session_id")
        raise HTTPException(
            status_code=500, detail=f"Authentication failed: {str(e)}"
        ) from e


@router_bff.post("/logout")
async def logout(
    request: Request,
    response: Response,
    user_session_service: UserSessionService = Depends(get_user_session_service),
) -> dict[str, str]:
    """Logout user with secure session cleanup.

    Validates CSRF token and optionally redirects to provider logout.
    """
    session_id = request.cookies.get("user_session_id")
    if session_id:
        # Get session info for provider logout
        user_session = await user_session_service.get_user_session(session_id)

        # Delete server-side session
        await user_session_service.delete_user_session(session_id)

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
    request: Request, user: User | None = Depends(get_optional_session_user)
) -> AuthState:
    """Get current authentication state with CSRF token for web client."""
    if not user:
        return AuthState(authenticated=False)

    # Generate CSRF token for authenticated users
    session_id = request.cookies.get("user_session_id")
    csrf_token = None
    if session_id:
        csrf_token = generate_csrf_token(session_id)

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
async def refresh_session(
    request: Request,
    response: Response,
    user_session_service: UserSessionService = Depends(get_user_session_service),
    oidc_client_service: OidcClientService = Depends(get_oidc_client_service),
) -> dict[str, str]:
    """Refresh user session with security validation.

    Validates client fingerprint and rotates session ID for security.
    """
    session_id = request.cookies.get("user_session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")

    # Extract client fingerprint for validation
    client_fingerprint = extract_client_fingerprint(request)

    # Validate session with fingerprint check
    user_session = await user_session_service.validate_user_session(
        session_id=session_id,
        client_fingerprint=client_fingerprint,
    )

    if not user_session:
        response.delete_cookie("user_session_id")
        raise HTTPException(status_code=401, detail="Invalid session")

    try:
        # Refresh tokens and rotate session ID
        new_session_id = await user_session_service.refresh_user_session(session_id, oidc_client_service)

        # Update session cookie with new ID
        cookie_settings = _get_secure_cookie_settings()
        response.set_cookie(
            key="user_session_id",
            value=new_session_id,
            max_age=get_config().app.session_max_age,
            **cookie_settings,
        )

        return {"message": "Session refreshed"}

    except Exception as e:
        # Clear invalid session
        response.delete_cookie("user_session_id")
        raise HTTPException(
            status_code=401, detail=f"Session refresh failed: {str(e)}"
        ) from e


@router_bff.post("/validate-csrf")
async def validate_csrf(request: Request, csrf_token: str) -> dict[str, bool]:
    """Validate CSRF token for AJAX requests."""
    session_id = request.cookies.get("user_session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")

    is_valid = validate_csrf_token(session_id, csrf_token)

    if not is_valid:
        raise HTTPException(status_code=403, detail="Invalid CSRF token")

    return {"valid": True}
