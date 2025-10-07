"""OIDC client service for handling authorization code flow with PKCE."""

import httpx
from loguru import logger
from pydantic import BaseModel

from src.app.core.security import (
    generate_pkce_pair as security_generate_pkce_pair,
)
from src.app.core.security import (
    generate_state as security_generate_state,
)
from src.app.core.services.jwt_service import TokenClaims, create_token_claims
from src.app.runtime.context import get_config


class TokenResponse(BaseModel):
    """OIDC token response model."""

    access_token: str # In the OIDC spec, this is always lowercase with an underscore. It refers to the token used to access protected resources for the user.
    token_type: str # In the OIDC spec, this is always lowercase with an underscore. It indicates the type of token issued, typically "Bearer".
    expires_in: int # Lifetime in seconds of the access token
    refresh_token: str | None = None # Optional refresh token to obtain new access tokens
    id_token: str | None = None # Optional ID token containing user claims

    @property
    def expires_at(self) -> int:
        """Calculate absolute expiry timestamp."""
        import time

        return int(time.time()) + self.expires_in


def generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code verifier and challenge.

    Returns:
        Tuple of (code_verifier, code_challenge)
    """
    return security_generate_pkce_pair()


def generate_state() -> str:
    """Generate random state parameter for CSRF protection."""
    return security_generate_state()


async def exchange_code_for_tokens(
    code: str, pkce_verifier: str, provider: str
) -> TokenResponse:
    """Exchange authorization code for tokens using PKCE.

    Args:
        code: Authorization code from callback
        pkce_verifier: PKCE code verifier
        provider: OIDC provider identifier

    Returns:
        Token response with access/refresh tokens
    """
    provider_config = get_config().oidc.providers[provider]

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": provider_config.redirect_uri,
        "client_id": provider_config.client_id,
        "code_verifier": pkce_verifier,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # Add client authentication if client secret is configured
    if provider_config.client_secret:
        import base64

        credentials = f"{provider_config.client_id}:{provider_config.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers["Authorization"] = f"Basic {encoded_credentials}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            provider_config.token_endpoint, data=token_data, headers=headers
        )
        response.raise_for_status()

        token_data = response.json()
        return TokenResponse(**token_data)


async def get_user_claims(access_token: str, id_token: str | None, provider: str) -> TokenClaims:
    """Get user claims from ID token or userinfo endpoint.

    Args:
        access_token: Access token for userinfo endpoint.
        id_token: ID token with user claims (optional)
        provider: OIDC provider identifier

    Returns:
        User claims dictionary
    """

    # If we have an ID token, decode it for user claims
    if id_token:
        from src.app.core.services import jwt_service

        try:
            # Validate ID token and extract claims
            return await jwt_service.verify_jwt(id_token)
        except Exception as e:
            logger.debug(f"ID token validation failed: {e}")
            # Fall back to userinfo endpoint if ID token validation fails
            pass

    # Fall back to userinfo endpoint. the user endpoint is an optional
    # part of the OIDC spec, so not all providers will have it. It provides
    # additional user information that may not be included in the ID token. The format is as follows:
    #
    # {
    #     "sub": "user-12345",
    #     "email": "test@example.com",
    #     "name": "Test User",
    #     "picture": "https://example.com/avatar.jpg"
    # }

    provider_config = get_config().oidc.providers[provider]
    if provider_config.userinfo_endpoint:
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                provider_config.userinfo_endpoint, headers=headers
            )
            response.raise_for_status()
            claims = response.json()
            return create_token_claims(token=access_token, claims=claims, token_type="access_token", issuer=provider_config.issuer)

    # Best practice is to raise an exception, as this is an unexpected error state.
    raise ValueError(
        "Unable to retrieve user claims - no ID token or userinfo endpoint"
    )


async def refresh_access_token(refresh_token: str, provider: str) -> TokenResponse:
    """Refresh access token using refresh token.

    Args:
        refresh_token: Refresh token
        provider: OIDC provider identifier

    Returns:
        New token response
    """
    provider_config = get_config().oidc.providers[provider]

    token_data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": provider_config.client_id,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    # Add client authentication if client secret is configured
    if provider_config.client_secret:
        import base64

        credentials = f"{provider_config.client_id}:{provider_config.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        headers["Authorization"] = f"Basic {encoded_credentials}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            provider_config.token_endpoint, data=token_data, headers=headers
        )
        response.raise_for_status()

        token_data = response.json()
        return TokenResponse(**token_data)
