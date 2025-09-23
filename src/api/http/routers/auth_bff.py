"""BFF (Backend-for-Frontend) authentication endpoints for web clients."""

from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from src.api.http.deps import get_session_only_user
from src.core.services import oidc_client_service, session_service
from src.entities.user import User
from src.runtime.config import get_config

main_config = get_config()

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


@router_bff.get("/login")
async def initiate_login(
    request: Request, provider: str = "default", redirect_uri: str | None = None
) -> RedirectResponse:
    """Initiate OIDC login flow with PKCE.

    Redirects to the identity provider's authorization endpoint.
    Stores PKCE verifier and state in session for security.
    """
    if provider not in main_config.oidc_providers:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Generate PKCE challenge and state
    pkce_verifier, pkce_challenge = oidc_client_service.generate_pkce_pair()
    state = oidc_client_service.generate_state()

    # Store PKCE verifier and state in session for callback
    session_id = session_service.create_auth_session(
        pkce_verifier=pkce_verifier,
        state=state,
        provider=provider,
        redirect_uri=redirect_uri or "/",
    )

    # Build authorization URL
    provider_config = main_config.oidc_providers[provider]
    auth_params = {
        "client_id": provider_config.client_id,
        "response_type": "code",
        "scope": " ".join(provider_config.scopes),
        "redirect_uri": provider_config.redirect_uri,
        "state": state,
        "code_challenge": pkce_challenge,
        "code_challenge_method": "S256",
    }

    auth_url = f"{provider_config.authorization_endpoint}?{urlencode(auth_params)}"

    # Set session cookie and redirect
    response = RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="auth_session_id",
        value=session_id,
        httponly=True,
        secure=main_config.environment == "production",
        samesite="lax",
        max_age=600,  # 10 minutes for auth flow
    )

    return response


@router_bff.get("/callback")
async def handle_callback(
    request: Request, code: str, state: str, error: str | None = None
) -> RedirectResponse:
    """Handle OIDC callback with authorization code.

    Exchanges code for tokens, creates user session, and redirects.
    """
    if error:
        raise HTTPException(status_code=400, detail=f"Authorization failed: {error}")

    # Get auth session from cookie
    session_id = request.cookies.get("auth_session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing auth session")

    auth_session = session_service.get_auth_session(session_id)
    if not auth_session:
        raise HTTPException(status_code=400, detail="Invalid or expired auth session")

    # Validate state parameter
    if state != auth_session.state:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    try:
        # Exchange code for tokens
        tokens = await oidc_client_service.exchange_code_for_tokens(
            code=code,
            pkce_verifier=auth_session.pkce_verifier,
            provider=auth_session.provider,
        )

        # Get user info from ID token or userinfo endpoint
        user_claims = await oidc_client_service.get_user_claims(
            tokens.access_token, tokens.id_token, auth_session.provider
        )

        # Create or update user via JIT provisioning
        user = await session_service.provision_user_from_claims(
            user_claims, auth_session.provider
        )

        # Create user session
        user_session_id = session_service.create_user_session(
            user_id=UUID(user.id),
            provider=auth_session.provider,
            refresh_token=tokens.refresh_token,
            access_token=tokens.access_token,
            expires_at=tokens.expires_at,
        )

        # Clean up auth session
        session_service.delete_auth_session(session_id)

        # Redirect with user session cookie
        redirect_url = auth_session.redirect_uri or "/"
        response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)

        # Set long-lived session cookie
        response.set_cookie(
            key="user_session_id",
            value=user_session_id,
            httponly=True,
            secure=main_config.environment == "production",
            samesite="lax",
            max_age=main_config.session_max_age,
        )

        # Clear auth session cookie
        response.delete_cookie("auth_session_id")

        return response

    except Exception as e:
        # Clean up auth session on error
        session_service.delete_auth_session(session_id)
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}") from e


@router_bff.post("/logout")
async def logout(request: Request, response: Response) -> dict[str, str]:
    """Logout user and clear session.

    Optionally redirects to provider logout endpoint.
    """
    session_id = request.cookies.get("user_session_id")
    if session_id:
        # Get session info for provider logout
        user_session = session_service.get_user_session(session_id)

        # Delete server-side session
        session_service.delete_user_session(session_id)

        # Clear session cookie
        response.delete_cookie("user_session_id")

        # Optionally trigger provider logout
        if (
            user_session
            and main_config.oidc_providers[user_session.provider].end_session_endpoint
        ):
            provider_config = main_config.oidc_providers[user_session.provider]
            logout_params = {
                "post_logout_redirect_uri": main_config.base_url,
                "client_id": provider_config.client_id,
            }
            logout_url = (
                f"{provider_config.end_session_endpoint}?{urlencode(logout_params)}"
            )
            return {"message": "Logged out", "provider_logout_url": logout_url}

    return {"message": "Logged out"}


@router_bff.get("/me")
async def get_auth_state(
    request: Request, user: User | None = Depends(get_session_only_user)
) -> AuthState:
    """Get current authentication state for web client."""
    if not user:
        return AuthState(authenticated=False)

    # Generate CSRF token for authenticated users
    session_id = request.cookies.get("user_session_id")
    csrf_token = session_service.generate_csrf_token(session_id) if session_id else None

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
    """Refresh user session using stored refresh token."""
    session_id = request.cookies.get("user_session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")

    try:
        # Refresh tokens and update session
        new_session_id = await session_service.refresh_user_session(session_id)

        # Update session cookie
        response.set_cookie(
            key="user_session_id",
            value=new_session_id,
            httponly=True,
            secure=main_config.environment == "production",
            samesite="lax",
            max_age=main_config.session_max_age,
        )

        return {"message": "Session refreshed"}

    except Exception as e:
        # Clear invalid session
        response.delete_cookie("user_session_id")
        raise HTTPException(status_code=401, detail=f"Session refresh failed: {str(e)}") from e
