"""JWT verification helpers used by the authentication dependencies."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Sequence
from typing import Any

from authlib.jose import JoseError, JsonWebKey, jwt
from cachetools import TTLCache
from fastapi import HTTPException

from src.runtime.config import OIDCProviderConfig
from src.runtime.settings import settings

_JWKS_CACHE: TTLCache[str, dict[str, Any]] = TTLCache(maxsize=10, ttl=3600)


def _decode_segment(segment: str, exc_message: str) -> dict[str, Any]:
    padding = "=" * (-len(segment) % 4)
    try:
        decoded = base64.urlsafe_b64decode(segment + padding)
        return json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail=exc_message) from exc


def decode_header(token: str) -> dict[str, Any]:
    try:
        header_segment, _, _ = token.split(".", 2)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid JWT format") from exc
    return _decode_segment(header_segment, "Invalid JWT header")


def decode_claims(token: str) -> dict[str, Any]:
    try:
        _header, payload, _signature = token.split(".", 2)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid JWT format") from exc
    return _decode_segment(payload, "Invalid JWT payload")


async def fetch_jwks(issuer: OIDCProviderConfig) -> dict[str, Any]:
    jwks_url = issuer.jwks_uri
    if not jwks_url:
        raise HTTPException(status_code=401, detail="Issuer has no JWKS URI configured")

    if jwks_url in _JWKS_CACHE:
        return _JWKS_CACHE[jwks_url]

    import httpx  # local import to avoid forcing httpx at import time

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()
            jwks = resp.json()
            _JWKS_CACHE[jwks_url] = jwks
            return jwks
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch JWKS: {exc}"
        ) from exc


async def verify_jwt(
    token: str, audiences: Sequence[str] | None = None
) -> dict[str, Any]:
    header = decode_header(token)

    alg = header.get("alg")
    if alg not in settings.allowed_algorithms:
        raise HTTPException(status_code=401, detail="Disallowed JWT algorithm")

    claims_preview = decode_claims(token)
    issuer = claims_preview.get("iss")
    if not issuer:
        raise HTTPException(status_code=401, detail="Missing iss claim")

    # Find provider config by issuer
    provider_config = None
    for provider in settings.oidc_providers.values():
        if provider.issuer and issuer.startswith(provider.issuer):
            provider_config = provider
            break

    if not provider_config:
        raise HTTPException(status_code=401, detail=f"Unknown issuer: {issuer}")

    try:
        jwks = await fetch_jwks(provider_config)
        key_set = JsonWebKey.import_key_set(jwks)
    except HTTPException as exc:
        raise HTTPException(
            status_code=401, detail=f"Failed to fetch JWKS: {exc.detail}"
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=401, detail=f"Failed to parse JWKS: {exc}"
        ) from exc

    audience_values = audiences or settings.audiences
    if not audience_values:
        raise HTTPException(
            status_code=401, detail="No audience configured for verification"
        )

    try:
        claims = jwt.decode(
            token,
            key_set,
            claims_options={
                "iss": {"essential": True, "values": [issuer]},
                "aud": {"essential": True, "values": list(audience_values)},
            },
        )
        claims.validate(leeway=settings.clock_skew)
    except JoseError as exc:
        raise HTTPException(status_code=401, detail=f"JWT error: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=f"JWT error: {exc}") from exc

    now = int(time.time())
    exp = claims.get("exp")
    if exp is not None and now > exp + settings.clock_skew:
        raise HTTPException(status_code=401, detail="Token expired (skew)")
    nbf = claims.get("nbf")
    if nbf is not None and now < nbf - settings.clock_skew:
        raise HTTPException(status_code=401, detail="Token not yet valid (skew)")

    return dict(claims)


def extract_uid(claims: dict[str, Any]) -> str:
    uid_claim = settings.uid_claim
    if uid_claim and uid_claim in claims:
        return claims[uid_claim]
    return f"{claims.get('iss')}|{claims.get('sub')}"


def extract_scopes(claims: dict[str, Any]) -> set[str]:
    """Extract scopes from JWT claims.

    Scopes can be in various claims: 'scope' (space-separated), 'scp' (string or array),
    or 'scopes' (array). Returns as set for deduplication.
    """
    scopes: set[str] = set()

    # Check for 'scope' claim (space-separated string)
    if "scope" in claims:
        scopes.update(str(claims["scope"]).split())

    # Check for 'scp' claim (Auth0 style)
    if "scp" in claims:
        value = claims["scp"]
        if isinstance(value, str):
            scopes.update(value.split())
        else:
            scopes.update(value)

    # Check for 'scopes' claim (array)
    if "scopes" in claims and isinstance(claims["scopes"], list):
        scopes.update(claims["scopes"])

    return scopes


def extract_roles(claims: dict[str, Any]) -> list[str]:
    """Extract roles from JWT claims.

    Roles can be in various claims and nested structures.
    """
    roles: list[str] = []

    # Check for common role claims
    for role_claim in ["roles", "groups", "authorities"]:
        value = claims.get(role_claim)
        if value:
            if isinstance(value, list):
                roles.extend(value)
            elif isinstance(value, str):
                # Handle space-separated roles string
                roles.extend(value.split())
            else:
                roles.append(str(value))

    # Check for Auth0 style roles (e.g., in app_metadata or custom claims)
    app_metadata = claims.get("app_metadata", {})
    if isinstance(app_metadata, dict) and "roles" in app_metadata:
        auth0_roles = app_metadata["roles"]
        if isinstance(auth0_roles, list):
            roles.extend(auth0_roles)

    # Check for Keycloak realm roles
    if "realm_access" in claims and "roles" in claims["realm_access"]:
        keycloak_roles = claims["realm_access"]["roles"]
        if isinstance(keycloak_roles, list):
            roles.extend(keycloak_roles)

    # Check for custom namespace roles (Auth0 custom claims pattern)
    for key, value in claims.items():
        if "roles" in key.lower() and isinstance(value, list):
            roles.extend(value)

    return roles
