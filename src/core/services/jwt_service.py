"""JWT verification helpers used by the authentication dependencies."""

from __future__ import annotations

import base64
import json
import time
from typing import Any, Dict, Optional, Sequence, Set

from authlib.jose import JsonWebKey, JoseError, jwt
from cachetools import TTLCache
from fastapi import HTTPException

from src.runtime.settings import settings

_JWKS_CACHE: TTLCache[str, Dict[str, Any]] = TTLCache(maxsize=10, ttl=3600)


def _decode_segment(segment: str, exc_message: str) -> Dict[str, Any]:
    padding = "=" * (-len(segment) % 4)
    try:
        decoded = base64.urlsafe_b64decode(segment + padding)
        return json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail=exc_message) from exc


def decode_header(token: str) -> Dict[str, Any]:
    try:
        header_segment, _, _ = token.split(".", 2)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid JWT format") from exc
    return _decode_segment(header_segment, "Invalid JWT header")


def decode_claims(token: str) -> Dict[str, Any]:
    try:
        _header, payload, _signature = token.split(".", 2)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid JWT format") from exc
    return _decode_segment(payload, "Invalid JWT payload")


async def fetch_jwks(issuer: str) -> Dict[str, Any]:
    if issuer not in settings.issuer_jwks_map:
        raise HTTPException(status_code=401, detail="Unknown issuer")
    jwks_url = settings.issuer_jwks_map[issuer]
    if jwks_url in _JWKS_CACHE:
        return _JWKS_CACHE[jwks_url]

    import httpx  # local import to avoid forcing httpx at import time

    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
        jwks = resp.json()
        _JWKS_CACHE[jwks_url] = jwks
        return jwks


async def verify_jwt(token: str, audiences: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    header = decode_header(token)

    alg = header.get("alg")
    if alg not in settings.allowed_algorithms:
        raise HTTPException(status_code=401, detail="Disallowed JWT algorithm")

    claims_preview = decode_claims(token)
    issuer = claims_preview.get("iss")
    if not issuer:
        raise HTTPException(status_code=401, detail="Missing iss claim")

    try:
        jwks = await fetch_jwks(issuer)
        key_set = JsonWebKey.import_key_set(jwks)
    except HTTPException as exc:
        raise HTTPException(status_code=401, detail=f"Failed to fetch JWKS: {exc.detail}")
    except Exception as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=401, detail=f"Failed to parse JWKS: {exc}") from exc

    audience_values = audiences or settings.audiences
    if not audience_values:
        raise HTTPException(status_code=401, detail="No audience configured for verification")

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


def extract_uid(claims: Dict[str, Any]) -> str:
    uid_claim = settings.uid_claim
    if uid_claim and uid_claim in claims:
        return claims[uid_claim]
    return f"{claims.get('iss')}|{claims.get('sub')}"


def extract_scopes(claims: Dict[str, Any]) -> Set[str]:
    scopes: Set[str] = set()
    if "scope" in claims:
        scopes.update(str(claims["scope"]).split())
    if "scp" in claims:
        value = claims["scp"]
        if isinstance(value, str):
            scopes.update(value.split())
        else:
            scopes.update(value)
    return scopes


def extract_roles(claims: Dict[str, Any]) -> Set[str]:
    roles: Set[str] = set()
    if "roles" in claims:
        value = claims["roles"]
        if isinstance(value, str):
            roles.update(value.split())
        else:
            roles.update(value)
    if "realm_access" in claims and "roles" in claims["realm_access"]:
        roles.update(claims["realm_access"]["roles"])
    return roles
