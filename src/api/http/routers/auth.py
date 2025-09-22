import time
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from jose import jwt

router_jit = APIRouter(prefix="/jit", tags=["auth-jit"])

# ---------- Config + stubs ----------
class TenantOIDC:
    def __init__(self, issuer: str, audience: str):
        self.issuer = issuer.rstrip("/")
        self.audience = audience

# Replace with your DB/secret-manager lookup
def get_tenant_oidc(tenant: str) -> TenantOIDC:
    # Example: different tenants use different IdPs
    # return TenantOIDC(issuer="https://YOUR_DOMAIN.auth0.com", audience="https://api.yourapp.com")
    # return TenantOIDC(issuer="https://login.microsoftonline.com/<tenant>/v2.0", audience="api://your-api-id")
    raise NotImplementedError("Implement tenant OIDC lookup")

# Simple in-memory JWKS cache (swap for redis/memory cache in prod)
_JWKS_CACHE: dict[str, dict[str, Any]] = {}
_JWKS_EXP: dict[str, float] = {}

async def load_jwks(issuer: str) -> dict[str, Any]:
    now = time.time()
    if issuer in _JWKS_CACHE and _JWKS_EXP.get(issuer, 0) > now:
        return _JWKS_CACHE[issuer]
    # Discover jwks_uri
    async with httpx.AsyncClient(timeout=15) as c:
        disc = await c.get(f"{issuer}/.well-known/openid-configuration")
        disc.raise_for_status()
        jwks_uri = disc.json()["jwks_uri"]
        jwks_resp = await c.get(jwks_uri)
        jwks_resp.raise_for_status()
        jwks = jwks_resp.json()
    _JWKS_CACHE[issuer] = jwks
    _JWKS_EXP[issuer] = now + 60 * 60  # 1h
    return jwks

# ---------- Domain persistence stubs ----------
def db_get_user_by_iss_sub(iss: str, sub: str) -> dict[str, Any] | None:
    """Return your domain user row or None."""
    return None

def db_create_user_from_claims(iss: str, sub: str, email: str | None, profile: dict[str, Any]) -> dict[str, Any]:
    """Create your domain user. Return user row (must include your user_id)."""
    # Persist (iss, sub) mapping in user_identities table.
    return {"user_id": "uuid-generated", "email": email, "iss": iss, "sub": sub, **profile}

# ---------- JWT verification + JIT upsert ----------
async def verify_and_upsert(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")

    token = auth.split(" ", 1)[1]
    tenant = request.headers.get("X-Tenant", "default")  # or derive from host
    cfg = get_tenant_oidc(tenant)

    jwks = await load_jwks(cfg.issuer)
    try:
        claims = jwt.decode(
            token,
            jwks,
            algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
            audience=cfg.audience,
            issuer=cfg.issuer,
            options={"verify_at_hash": False},  # tweak as needed
        )
    except Exception as e:
        raise HTTPException(401, f"Invalid token: {e}")

    iss = claims.get("iss")
    sub = claims.get("sub")
    if not iss or not sub:
        raise HTTPException(401, "Token missing iss/sub")

    # JIT: find-or-create user
    user = db_get_user_by_iss_sub(iss, sub)
    if user:
        return user

    email = claims.get("email") if claims.get("email_verified") else None
    profile = {
        "name": claims.get("name"),
        "locale": claims.get("locale"),
        "picture": claims.get("picture"),
        # Add more claim mappings as you see fit
    }
    user = db_create_user_from_claims(iss, sub, email, profile)
    return user

# ---------- Example protected route that JITs the user ----------
@router_jit.get("/me")
async def me(current_user: Dict[str, Any] = Depends(verify_and_upsert)):
    # Return your domain’s view of the user
    return {
        "user_id": current_user["user_id"],
        "email": current_user.get("email"),
        "profile": {
            "name": current_user.get("name"),
            "picture": current_user.get("picture"),
        },
    }
