"""FastAPI application factory and setup."""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.http.deps import get_current_user, require_role, require_scope
from src.api.http.middleware.limiter import close_rate_limiter, configure_rate_limiter
from src.core.entities.user import User as UserEntity
from src.core.services import jwt_service
from src.runtime.settings import settings

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Rate limiter dependencies ---
try:
    from fastapi_limiter import FastAPILimiter
    import redis.asyncio as redis_async
    from redis.asyncio import Redis as AsyncRedis
except ImportError:  # pragma: no cover - optional dependency missing
    FastAPILimiter = None
    redis_async = None
    AsyncRedis = None


def _activate_local_rate_limiter() -> None:
    limiter = getattr(app.state, "local_rate_limiter", None)
    if limiter is None:
        from src.api.http.middleware.limiter import DefaultLocalRateLimiter
        limiter = DefaultLocalRateLimiter()
        app.state.local_rate_limiter = limiter
        logger.warning("Falling back to in-memory rate limiter")
    configure_rate_limiter(use_external=False, local_factory=limiter.dependency)


# --- Security middleware ---
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=()")
        # HSTS only in prod
        if settings.environment == "production":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload",
            )
        return response


# --- FastAPI app setup ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Allow FastAPI to run startup/shutdown routines once per process
    await startup()
    try:
        yield
    finally:
        await shutdown()


app = FastAPI(
    lifespan=lifespan,
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None if settings.environment == "production" else "/redoc",
)

app.add_middleware(SecurityHeadersMiddleware)

# expose startup for tests
__all__ = ["app", "startup", "shutdown"]

# --- CORS configuration ---
if settings.environment == "production" and ("*" in settings.cors_origins):
    raise RuntimeError("CORS misconfigured: cannot use '*' with allow_credentials=True in production")

origins = settings.cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request logging middleware ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Ensure every request is tagged with an ID for debugging and metrics
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start = time.perf_counter()
    response = None
    try:
        # Delegate to downstream handlers while tracking execution time
        response = await call_next(request)
        return response
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        status_code = getattr(response, "status_code", "ERR")
        logger.info(
            "rid=%s %s %s -> %s in %.1fms",
            rid,
            request.method,
            request.url.path,
            status_code,
            duration_ms,
        )
        if response is not None:
            response.headers.setdefault("X-Request-ID", rid)


# --- Router registration ---
# Add your application-specific routers here
# Example:
# app.include_router(your_router, prefix="/api/v1", tags=["your_feature"])


# --- Rate limiter setup ---
async def _initialize_rate_limiter() -> None:
    # Skip initialization when Redis is not configured
    if settings.redis_url is None:
        logger.info("Redis URL not configured; skipping rate limiter initialization")
        _activate_local_rate_limiter()
        return None
    if FastAPILimiter is None or redis_async is None:
        logger.error("Rate limiter deps missing but REDIS_URL provided")
        if settings.environment == "production":
            raise RuntimeError("Rate limiter dependencies missing in production")
        _activate_local_rate_limiter()
        return

    try:
        client = redis_async.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
        await FastAPILimiter.init(client)
        app.state.redis = client
        logger.info("FastAPI limiter initialized with Redis: %s", settings.redis_url)
        configure_rate_limiter(use_external=True, local_factory=None)
        app.state.local_rate_limiter = None
        return
    except Exception:
        logger.exception("Failed to initialize FastAPI limiter with Redis")
        if settings.environment == "production":
            raise
        _activate_local_rate_limiter()
        return


# --- Lifecycle hooks ---
async def startup() -> None:
    # Validate configuration so we fail fast on misconfiguration
    settings.validate_runtime()
    logger.info("Configuration validated")

    # Verify JWKS endpoints so auth failures surface early
    if settings.issuer_jwks_map:
        issuers = list(settings.issuer_jwks_map.keys())
        results = await asyncio.gather(
            *(jwt_service.fetch_jwks(iss) for iss in issuers), return_exceptions=True
        )
        errors = [(iss, str(err)) for iss, err in zip(issuers, results) if isinstance(err, Exception)]
        for iss, err in errors:
            logger.exception("Failed to fetch JWKS for issuer %s: %s", iss, err)
        if errors and settings.environment == "production":
            raise RuntimeError(f"JWKS readiness check failed for issuers: {errors}")

    await _initialize_rate_limiter()


async def shutdown() -> None:
    logger.info("Shutting down application")
    await close_rate_limiter()


# --- Response models ---
class MeResponse(BaseModel):
    user_id: str
    email: str
    scopes: List[str]
    roles: List[str]
    claims: Dict[str, Any]


# --- Route handlers ---

@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/ready")
async def readiness() -> dict[str, str]:
    """Readiness check endpoint."""
    return {"status": "ready"}


@app.get("/me", response_model=MeResponse)
async def get_me(request: Request, user: UserEntity = Depends(get_current_user)) -> dict[str, Any]:
    # Mirror the authenticated user context for clients that need their claims
    return {
        "user_id": str(user.id),
        "email": user.email,
        "scopes": list(getattr(request.state, "scopes", [])),
        "roles": list(getattr(request.state, "roles", [])),
        "claims": getattr(request.state, "claims", {}),
    }


@app.get("/protected-scope")
async def protected_scope(
    user: UserEntity = Depends(get_current_user), dep: None = Depends(require_scope("read:protected"))
) -> dict[str, Any]:
    # Example endpoint that enforces a scope requirement
    return {"message": "You have the required scope!", "user_id": str(user.id)}


@app.get("/protected-role")
async def protected_role(
    user: UserEntity = Depends(get_current_user), dep: None = Depends(require_role("admin"))
) -> dict[str, Any]:
    # Example endpoint that enforces a role requirement
    return {"message": "You have the required role!", "user_id": str(user.id)}

