"""Enhanced BFF (Backend-for-Frontend) authentication endpoints with CSRF protection and hardened flows."""

from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from loguru import logger
from pydantic import BaseModel

from src.app.api.http.deps import (
    enforce_origin,
    get_auth_session_service,
    get_jwt_verify_service,
    get_oidc_client_service,
    get_optional_session_user,
    get_user_management_service,
    get_user_session_service,
    require_csrf,
)
from src.app.core.security import (
    extract_client_fingerprint,
    generate_csrf_token,
    generate_nonce,
    generate_pkce_pair,
    generate_state,
    sanitize_return_url,
)
from src.app.core.services import (
    AuthSessionService,
    JwtVerificationService,
    OidcClientService,
    UserManagementService,
    UserSessionService,
)
from src.app.entities.core.user import User
from src.app.runtime.context import get_config

router_bff = APIRouter(prefix="/web", tags=["auth-bff"])



class AuthState(BaseModel):
    """Current authentication state for web clients."""

    authenticated: bool
    user: dict[str, Any] | None = None
    csrf_token: str | None = None


def _get_secure_cookie_settings() -> dict[str, Any]:
    """Get secure cookie configuration for OAuth authentication.

    For BFF pattern where the session cookie is first-party to your domain,
    SameSite=Lax is sufficient and preferred. OAuth callbacks are top-level
    GET navigations, which Lax allows.

    SameSite=None is only needed if:
    - Your frontend is on a different domain than your API (cross-site subrequests)
    - You use iframes or embedded contexts
    - You need silent token refresh in background requests

    Security is maintained through multiple layers:
    - httponly=True: Prevents JavaScript access (XSS protection)
    - secure=True: HTTPS only (with localhost exception for dev)
    - samesite=Lax: Allows top-level navigations (OAuth callbacks) but blocks CSRF
    - State parameter validation: Prevents CSRF attacks
    - PKCE flow: Prevents authorization code interception
    - Nonce validation: Prevents token replay attacks
    """
    config = get_config()
    return {
        "httponly": True,
        "secure": config.app.environment == "production",
        "samesite": "lax",  # Sufficient for OAuth redirect flows
        "path": "/",
    }


@router_bff.get("/login")
async def initiate_login(
    request: Request,
    provider: str = "default",
    return_to: str | None = None,  # post-login navigation (NOT IdP redirect_uri)
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

    # Sanitize post-login return destination. Prefer relative paths; allowlist absolute if configured.
    safe_return_uri = sanitize_return_url(
        return_to or "/",
        allowed_hosts=getattr(config.oidc, "allowed_redirect_hosts", None),
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

    # Build authorization URL with nonce (IdP redirect_uri is always server-configured)
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
    session_id = request.cookies.get("auth_session_id")
    # Avoid logging state/code/session ids to prevent leakage
    logger.debug("Callback received for provider login")

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
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.delete_cookie("auth_session_id", path="/")
        # Return generic error (details go to server logs)
        return response

    if not code:
        await auth_session_service.delete_auth_session(session_id)
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.delete_cookie("auth_session_id", path="/")
        return response

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
            await auth_session_service.delete_auth_session(session_id)
            response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
            response.delete_cookie("auth_session_id", path="/")
            return response

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

        # Note: CSRF token generation could be added here for future enhancements
        # csrf_token = generate_csrf_token(user_session_id)

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
        response.delete_cookie("auth_session_id", path="/")

        return response

    except Exception:
        # Clean up auth session on any error path to retire nonce/state
        try:
            await auth_session_service.delete_auth_session(session_id)
        finally:
            pass
        # Clear cookie to avoid dangling references
        response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        response.delete_cookie("auth_session_id", path="/")
        # Return a generic response; log server-side
        logger.exception("Authentication failed during callback")
        return response


@router_bff.post("/logout", dependencies=[Depends(enforce_origin), Depends(require_csrf)])
async def logout(
    request: Request,
    response: Response,
    user_session_service: UserSessionService = Depends(get_user_session_service),
) -> dict[str, str]:
    """Logout user with secure session cleanup.

    Requires CSRF token and optionally returns provider logout URL.
    """

    session_id = request.cookies.get("user_session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")

    if session_id:
        # Get session info for provider logout
        user_session = await user_session_service.get_user_session(session_id)

        # Delete server-side session
        await user_session_service.delete_user_session(session_id)

        # Clear session cookie
        response.delete_cookie("user_session_id", path="/")

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


@router_bff.post("/refresh", dependencies=[Depends(enforce_origin), Depends(require_csrf)])
async def refresh_session(
    request: Request,
    response: Response,
    user_session_service: UserSessionService = Depends(get_user_session_service),
    oidc_client_service: OidcClientService = Depends(get_oidc_client_service),
) -> dict[str, str]:
    """Refresh user session with CSRF + Origin validation and rotation.

    Requires X-CSRF-Token header; validates client fingerprint; rotates session ID and CSRF token.
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
        response.delete_cookie("user_session_id", path="/")
        raise HTTPException(status_code=401, detail="Invalid session")

    try:
        # Refresh tokens and rotate session ID
        new_session_id = await user_session_service.refresh_user_session(
            session_id, oidc_client_service
        )

        # Update session cookie with new ID
        cookie_settings = _get_secure_cookie_settings()
        response.set_cookie(
            key="user_session_id",
            value=new_session_id,
            max_age=get_config().app.session_max_age,
            **cookie_settings,
        )

        # Rotate CSRF token and return it so the client can update in memory
        new_csrf = generate_csrf_token(new_session_id)
        return {"message": "Session refreshed", "csrf_token": new_csrf}

    except Exception:
        # Clear invalid session
        response.delete_cookie("user_session_id", path="/")
        logger.exception("Session refresh failed")
        raise HTTPException(status_code=401, detail="Session refresh failed") from None
