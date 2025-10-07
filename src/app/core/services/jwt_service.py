"""JWT verification and generation helpers used by the authentication dependencies."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Sequence
from typing import Any

from authlib.jose import JoseError, JsonWebKey, jwt
from cachetools import TTLCache
from fastapi import HTTPException
from loguru import logger

from src.app.core.models.session import TokenClaims
from src.app.runtime.config.config_data import ConfigData, OIDCProviderConfig
from src.app.runtime.context import get_config

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
    token: str,
    key: str | None = None,
    audiences: Sequence[str] | None = None,
    expected_nonce: str | None = None,
    skip_issuer_validation: bool = False,
) -> TokenClaims:
    """Verify a JWT token using either a provided key or JWKS fetching.

    Args:
        token: JWT token to verify
        key: Optional secret key for internal tokens. If None, will fetch JWKS based on issuer
        audiences: Expected audience values
        expected_nonce: Expected nonce for OIDC ID tokens
        skip_issuer_validation: Skip issuer validation for internal tokens

    Returns:
        Verified claims dictionary

    Raises:
        HTTPException: If verification fails
    """
    main_config = get_config()
    header = decode_header(token)
    alg = header.get("alg")
    if alg not in main_config.jwt.allowed_algorithms:
        raise HTTPException(status_code=401, detail="Disallowed JWT algorithm")

    claims_preview = decode_claims(token)
    issuer = claims_preview.get("iss")

    # For external tokens (JWKS), issuer is required
    if key is None and not issuer:
        raise HTTPException(status_code=401, detail="Missing iss claim")

    # Determine key material
    if key is not None:
        # Internal token verification with provided key
        verification_key = key
        # For internal tokens, use basic validation without strict issuer/audience checks
        claims_options = None
    else:
        # External token verification with JWKS
        # Find provider config by issuer
        provider_config = None
        for provider in main_config.oidc.providers.values():
            if provider.issuer and issuer and issuer.startswith(provider.issuer):
                provider_config = provider
                break

        if not provider_config:
            raise HTTPException(status_code=401, detail=f"Unknown issuer: {issuer}")

        try:
            jwks = await fetch_jwks(provider_config)
            verification_key = JsonWebKey.import_key_set(jwks)
        except HTTPException as exc:
            raise HTTPException(
                status_code=401, detail=f"Failed to fetch JWKS: {exc.detail}"
            ) from exc
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(
                status_code=401, detail=f"Failed to parse JWKS: {exc}"
            ) from exc

        # For external tokens, enforce strict issuer/audience validation
        audience_values = audiences or main_config.jwt.audiences
        if not audience_values:
            raise HTTPException(
                status_code=401, detail="No audience configured for verification"
            )

        claims_options = {
            "iss": {"essential": True, "values": [issuer]},
            "aud": {"essential": True, "values": list(audience_values)},
        }

    try:
        claims = jwt.decode(
            token,
            verification_key,
            claims_options=claims_options,
        )
        claims.validate(leeway=main_config.jwt.clock_skew)
    except JoseError as exc:
        raise HTTPException(status_code=401, detail=f"JWT error: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=f"JWT error: {exc}") from exc

    # Additional time validation with clock skew (redundant but explicit)
    now = int(time.time())
    exp = claims.get("exp")
    if exp is not None and now > exp + main_config.jwt.clock_skew:
        raise HTTPException(status_code=401, detail="Token expired (skew)")
    nbf = claims.get("nbf")
    if nbf is not None and now < nbf - main_config.jwt.clock_skew:
        raise HTTPException(status_code=401, detail="Token not yet valid (skew)")

    # Validate nonce if expected (OIDC ID token validation)
    if expected_nonce:
        token_nonce = claims.get("nonce")
        if not token_nonce:
            raise HTTPException(status_code=401, detail="Missing nonce claim in token")
        if token_nonce != expected_nonce:
            raise HTTPException(status_code=401, detail="Invalid nonce in token")

    return create_token_claims(
        token=token,
        claims=claims,
        token_type="id_token" if "nonce" in claims else "access_token",
        issuer=issuer,
    )


def extract_uid(claims: dict[str, Any]) -> str:
    main_config = get_config()
    uid_claim = main_config.jwt.claims.user_id
    if uid_claim and uid_claim in claims:
        return claims[uid_claim]
    return f"{claims.get('iss')}|{claims.get('sub')}"


def extract_scopes(claims: dict[str, Any]) -> list[str]:
    """Extract scopes from JWT claims, preserving order.

    Scopes can be in various claims: 'scope' (space-separated), 'scp' (string or array),
    or 'scopes' (array). Returns as a list with deduplication, preserving first occurrence order.
    """
    seen = set()
    scopes = []

    # Helper to add scopes while preserving order and deduplication
    def add_scope_items(items):
        for item in items:
            if item not in seen:
                seen.add(item)
                scopes.append(item)

    # 'scope' claim (space-separated string)
    if "scope" in claims:
        add_scope_items(str(claims["scope"]).split())

    # 'scp' claim (string or array)
    if "scp" in claims:
        value = claims["scp"]
        if isinstance(value, str):
            add_scope_items(value.split())
        elif isinstance(value, (list, tuple)):
            add_scope_items(value)

    # 'scopes' claim (array)
    if "scopes" in claims and isinstance(claims["scopes"], (list, tuple)):
        add_scope_items(claims["scopes"])

    return scopes


def extract_roles(claims: dict[str, Any]) -> list[str]:
    """Extract roles from JWT claims.

    Roles can be in various claims and nested structures.
    """
    roles: list[str] = []

    # Check for common role claims (both singular and plural)
    for role_claim in ["role", "roles", "groups", "authorities"]:
        value = claims.get(role_claim)
        if value:
            if isinstance(value, list):
                print("Extracted roles from list:", value)
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
        if key != "roles" and "roles" in key.lower() and isinstance(value, list):
            roles.extend(value)
    return roles


def create_token_claims(
    token: str,
    claims: dict[str, Any],
    token_type: str = "id_token",
    issuer: str | None = None,
) -> TokenClaims:
    """Create TokenClaims instance from verified JWT claims.

    Args:
        token: The raw JWT token
        claims: Verified JWT claims
        token_type: Type of token (id_token, access_token)
        issuer: Fallback issuer if not present in claims (mainly for userinfo endpoint responses)

    Returns:
        TokenClaims instance with parsed claims
    """
    # Secure defaults for exp (expiration) and iat (issued at):
    # - iat: current time (int(time.time()))
    # - exp: current time + reasonable lifetime (e.g., 3600 seconds = 1 hour)
    # If claims do not provide these, set defaults.

    now = int(time.time())

    # Make a copy to avoid modifying the original claims dict
    remaining_claims = claims.copy()

    logger.debug(f"Creating TokenClaims from claims: {remaining_claims}")

    uid = extract_uid(remaining_claims)

    # Extract standard JWT claims (pop them as we parse)
    expires_at = remaining_claims.pop("exp", now + 3600)  # Default: 1 hour from now
    issued_at = remaining_claims.pop("iat", now)  # Default: now
    not_before = remaining_claims.pop("nbf", None)
    subject = remaining_claims.pop("sub", "")
    audience = remaining_claims.pop("aud", [])
    token_issuer = remaining_claims.pop("iss", None) or issuer or ""

    # Extract OIDC claims that we use
    nonce = remaining_claims.pop("nonce", None)
    jti = remaining_claims.pop("jti", None)

    # Extract profile claims that we use
    email = remaining_claims.pop("email", None)
    email_verified = remaining_claims.pop("email_verified", False)
    name = remaining_claims.pop("name", None)
    given_name = remaining_claims.pop("given_name", None) or remaining_claims.pop(
        "first_name", None
    )
    family_name = remaining_claims.pop("family_name", None) or remaining_claims.pop(
        "last_name", None
    )

    # Extract scopes and roles (these functions will handle multiple claim variations)
    scopes = extract_scopes(claims)  # Use original claims for extraction
    roles = extract_roles(claims)  # Use original claims for extraction

    # Remove only the claims that we've explicitly extracted and mapped to TokenClaims fields
    # This ensures we don't lose any information - all unmapped claims stay in custom_claims

    # Remove scope/role claims that we've processed into dedicated fields
    # Note: We need to be careful here since extract_scopes/extract_roles handle multiple variations
    for scope_claim in ["scope", "scopes", "scp"]:
        remaining_claims.pop(scope_claim, None)
    for role_claim in ["role", "roles", "groups", "authorities"]:
        remaining_claims.pop(role_claim, None)

    # Remove nested structures that we've processed for roles
    # Only remove these if they were actually used for role extraction
    if "realm_access" in remaining_claims and "roles" in remaining_claims.get(
        "realm_access", {}
    ):
        remaining_claims.pop("realm_access", None)
    if "app_metadata" in remaining_claims and "roles" in remaining_claims.get(
        "app_metadata", {}
    ):
        remaining_claims.pop("app_metadata", None)

    return TokenClaims(
        raw_token=token,
        uid=uid,
        email_verified=email_verified,
        all_claims=claims.copy(),
        issuer=token_issuer,
        subject=subject,
        audience=audience,
        expires_at=expires_at,
        issued_at=issued_at,
        not_before=not_before,
        nonce=nonce,
        jti=jti,
        token_type=token_type,
        scope=" ".join(scopes),
        scopes=list(scopes),
        roles=roles,
        email=email,
        name=name,
        given_name=given_name,
        family_name=family_name,
        custom_claims=remaining_claims,  # Only truly custom claims remain
    )


def generate_jwt(
    subject: str,
    claims: dict[str, Any] | None = None,
    expires_in_seconds: int = 3600,
    issuer: str | None = None,
    audience: str | list[str] | None = None,
    algorithm: str = "HS256",
    include_jti: bool = True,
    secret: str | None = None,
    kid: str | None = None,
) -> str:
    """Generate a signed JWT token for API authentication using authlib.

    Args:
        subject: Subject (sub) claim - typically user ID
        claims: Additional claims to include in the token
        expires_in_seconds: Token lifetime in seconds (default: 1 hour)
        issuer: Issuer (iss) claim (defaults to config issuer)
        audience: Audience (aud) claim (defaults to config audiences)
        algorithm: Signing algorithm (default: HS256)
        include_jti: Whether to include a unique JWT ID claim (default: True)
        secret: Optional secret key for signing. If None, will use config secret.
        kid: Optional Key ID for JWT header (required for JWKS verification)

    Returns:
        Signed JWT token string

    Raises:
        HTTPException: If configuration is missing or invalid
    """
    from authlib.common.security import generate_token

    config: ConfigData = get_config()

    # Get signing secret

    if not secret:
        secret = config.app.session_jwt_secret

    if not secret:
        raise HTTPException(status_code=500, detail="JWT signing secret not configured")

    # Validate algorithm
    if algorithm not in config.jwt.allowed_algorithms:
        logger.debug(f"Attempted to use disallowed algorithm: {algorithm}, only {config.jwt.allowed_algorithms} are allowed")
        raise HTTPException(
            status_code=500, detail=f"Algorithm {algorithm} not allowed"
        )

    # Build payload with proper time handling
    now = int(time.time())
    payload = {
        "iss": issuer or f"api-{config.app.environment}",
        "sub": subject,
        "aud": audience or config.jwt.audiences or ["api"],
        "exp": now + expires_in_seconds,
        "iat": now,
        "nbf": now,
    }

    # Add unique JWT ID for token tracking/revocation if requested
    if include_jti:
        payload["jti"] = generate_token(16)  # Use authlib's secure token generator

    # Add custom claims (filter out standard JWT claims to avoid conflicts)
    if claims:
        filtered_claims = {
            k: v
            for k, v in claims.items()
            if k not in {"iss", "sub", "aud", "exp", "iat", "nbf", "jti"}
        }
        payload.update(filtered_claims)

    try:
        # Use authlib's JWT encoding with proper header
        header = {"alg": algorithm, "typ": "JWT"}

        # Add Key ID to header if provided (required for JWKS verification)
        if kid:
            header["kid"] = kid

        # Use string key for consistency with type hints
        secret_key = secret if isinstance(secret, str) else secret.decode()
        token = jwt.encode(header, payload, secret_key)

        # authlib returns bytes, decode to string
        return token.decode() if isinstance(token, bytes) else token

    except JoseError as e:
        raise HTTPException(
            status_code=500, detail=f"JWT encoding failed: {str(e)}"
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate JWT: {str(e)}"
        ) from e


def verify_generated_jwt(token: str) -> TokenClaims:
    """Verify a JWT token generated by this service.

    Convenience function that calls verify_jwt with the local secret key.
    This maintains backward compatibility while using the unified verification logic.

    Args:
        token: JWT token to verify

    Returns:
        Verified claims dictionary

    Raises:
        HTTPException: If verification fails
    """
    import asyncio

    config = get_config()
    secret = config.app.session_jwt_secret
    if not secret:
        raise HTTPException(status_code=500, detail="JWT signing secret not configured")

    # Use string key for consistency with type hints
    secret_key = secret if isinstance(secret, str) else secret.decode()

    # Call the unified verify_jwt function with the local secret
    return asyncio.run(verify_jwt(token, key=secret_key))


def generate_access_token(
    user_id: str,
    scopes: list[str] | None = None,
    roles: list[str] | None = None,
    expires_in_seconds: int = 3600,
    issuer: str | None = None,
    audience: str | list[str] | None = None,
    algorithm: str = "HS256",
    include_jti: bool = True,
    secret: str | None = None,
    kid: str | None = None,
    **extra_claims,
) -> str:
    """Generate an access token JWT for API authentication.

    Args:
        user_id: User identifier for the subject claim
        scopes: User scopes/permissions
        roles: User roles
        expires_in_seconds: Token lifetime in seconds (default: 1 hour)
        issuer: Issuer (iss) claim (defaults to config issuer)
        audience: Audience (aud) claim (defaults to config audiences)
        algorithm: Signing algorithm (default: HS256)
        include_jti: Whether to include a unique JWT ID claim (default: True)
        secret: Optional secret key for signing. If None, will use config secret.
        kid: Optional Key ID for JWT header (required for JWKS verification)
        **extra_claims: Additional claims to include

    Returns:
        Signed access token JWT

    Example:
        token = generate_access_token(
            user_id="user123",
            scopes=["read:posts", "write:comments"],
            roles=["user", "moderator"],
            issuer="my-api",
            audience=["api", "mobile-app"],
            algorithm="HS256",
            kid="key-1",
            email="user@example.com"
        )
    """
    claims = {}

    if scopes:
        claims["scope"] = " ".join(scopes)
        claims["scopes"] = scopes

    if roles:
        claims["roles"] = roles

    # Add any extra claims
    claims.update(extra_claims)

    return generate_jwt(
        subject=user_id,
        claims=claims,
        expires_in_seconds=expires_in_seconds,
        issuer=issuer,
        audience=audience,
        algorithm=algorithm,
        include_jti=include_jti,
        secret=secret,
        kid=kid,
    )


def generate_id_token(
    user_id: str,
    email: str | None = None,
    name: str | None = None,
    given_name: str | None = None,
    family_name: str | None = None,
    nonce: str | None = None,
    expires_in_seconds: int = 3600,
    issuer: str | None = None,
    audience: str | list[str] | None = None,
    algorithm: str = "HS256",
    include_jti: bool = True,
    secret: str | None = None,
    kid: str | None = None,
    **extra_claims,
) -> str:
    """Generate an ID token JWT for user identification.

    Args:
        user_id: User identifier for the subject claim
        email: User email
        name: Full name
        given_name: First name
        family_name: Last name
        nonce: OIDC nonce for replay protection
        expires_in_seconds: Token lifetime in seconds (default: 1 hour)
        issuer: Issuer (iss) claim (defaults to config issuer)
        audience: Audience (aud) claim (defaults to config audiences)
        algorithm: Signing algorithm (default: HS256)
        include_jti: Whether to include a unique JWT ID claim (default: True)
        secret: Optional secret key for signing. If None, will use config secret.
        kid: Optional Key ID for JWT header (required for JWKS verification)
        **extra_claims: Additional claims to include

    Returns:
        Signed ID token JWT

    Example:
        id_token = generate_id_token(
            user_id="user123",
            email="user@example.com",
            given_name="John",
            family_name="Doe",
            nonce="abc123",
            issuer="auth-server",
            audience="client-app",
            kid="key-1"
        )
    """
    claims = {}

    if email:
        claims["email"] = email
        claims["email_verified"] = True  # Assume verified if provided

    if name:
        claims["name"] = name

    if given_name:
        claims["given_name"] = given_name

    if family_name:
        claims["family_name"] = family_name

    if nonce:
        claims["nonce"] = nonce

    # Add any extra claims
    claims.update(extra_claims)

    return generate_jwt(
        subject=user_id,
        claims=claims,
        expires_in_seconds=expires_in_seconds,
        issuer=issuer,
        audience=audience,
        algorithm=algorithm,
        include_jti=include_jti,
        secret=secret,
        kid=kid,
    )


def generate_refresh_token(
    user_id: str,
    client_id: str | None = None,
    expires_in_seconds: int = 7 * 24 * 3600,  # 7 days
    issuer: str | None = None,
    audience: str | list[str] | None = None,
    algorithm: str = "HS256",
    include_jti: bool = True,
    secret: str | None = None,
    kid: str | None = None,
    **extra_claims,
) -> str:
    """Generate a refresh token JWT for token renewal.

    Args:
        user_id: User identifier for the subject claim
        client_id: Optional client identifier
        expires_in_seconds: Token lifetime in seconds (default: 7 days)
        issuer: Issuer (iss) claim (defaults to config issuer)
        audience: Audience (aud) claim (defaults to config audiences)
        algorithm: Signing algorithm (default: HS256)
        include_jti: Whether to include a unique JWT ID claim (default: True)
        secret: Optional secret key for signing. If None, will use config secret.
        kid: Optional Key ID for JWT header (required for JWKS verification)
        **extra_claims: Additional claims to include

    Returns:
        Signed refresh token JWT

    Example:
        refresh_token = generate_refresh_token(
            user_id="user123",
            client_id="webapp",
            issuer="auth-server",
            audience="refresh-service",
            kid="key-1",
            session_id="session456"
        )
    """
    claims = {"token_type": "refresh"}

    if client_id:
        claims["client_id"] = client_id

    # Add any extra claims
    claims.update(extra_claims)

    return generate_jwt(
        subject=user_id,
        claims=claims,
        expires_in_seconds=expires_in_seconds,
        issuer=issuer,
        audience=audience,
        algorithm=algorithm,
        include_jti=include_jti,
        secret=secret,
        kid=kid,
    )
