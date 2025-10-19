"""FastAPI application factory and setup."""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from src.app.api.http.app_data import ApplicationDependencies, DbSessionService
from src.app.api.http.middleware.limiter import (
    close_rate_limiter,
    configure_rate_limiter,
)
from src.app.api.http.routers.auth import router_jit
from src.app.api.http.routers.auth_bff_enhanced import router_bff
from src.app.core.services import (
    AuthSessionService,
    JWKSCacheInMemory,
    JwksService,
    JwtGeneratorService,
    JwtVerificationService,
    OidcClientService,
    UserSessionService,
)
from src.app.core.storage.session_storage import get_session_storage
from src.app.runtime.context import get_config

# main_config = get_config()

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Reduce SQLAlchemy logging verbosity
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)

# --- Rate limiter dependencies ---
try:
    import redis.asyncio as redis_async
    from fastapi_limiter import FastAPILimiter
    from redis.asyncio import Redis as AsyncRedis
except ImportError:  # pragma: no cover - optional dependency missing
    FastAPILimiter = None
    redis_async = None
    AsyncRedis = None


# --- Security middleware ---
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=()"
        )
        # HSTS only in prod
        if get_config().app.environment == "production":
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
    docs_url=None if get_config().app.environment == "production" else "/docs",
    redoc_url=None if get_config().app.environment == "production" else "/redoc",
)

app.add_middleware(SecurityHeadersMiddleware)

# expose startup for tests
__all__ = ["app", "startup", "shutdown"]

# --- CORS configuration ---
if get_config().app.environment == "production" and (
    "*" in get_config().app.cors.origins
):
    raise RuntimeError(
        "CORS misconfigured: cannot use '*' with allow_credentials=True in production"
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_config().app.cors.origins,
    allow_credentials=get_config().app.cors.allow_credentials,
    allow_methods=get_config().app.cors.allow_methods,
    allow_headers=get_config().app.cors.allow_headers,
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
# OIDC compliant authentication endpoints
app.include_router(router_jit, prefix="/auth")

# BFF authentication endpoints for web clients
app.include_router(router_bff, prefix="/auth")

# Add your application-specific routers here
# Example:
# app.include_router(your_router, prefix="/api/v1", tags=["your_feature"])


def _activate_local_rate_limiter() -> None:
    from src.app.api.http.middleware.limiter import DefaultLocalRateLimiter

    logger.warning("Falling back to in-memory rate limiter")
    configure_rate_limiter(limiter_factory=DefaultLocalRateLimiter)


# --- Rate limiter setup ---
async def _initialize_rate_limiter() -> None:
    # Skip initialization when Redis is not configured
    config = get_config()
    if config.redis.url is None:
        logger.info("Redis URL not configured; skipping rate limiter initialization")
        _activate_local_rate_limiter()
        return None
    if FastAPILimiter is None or redis_async is None:
        logger.error("Rate limiter deps missing but REDIS_URL provided")
        if config.app.environment == "production":
            raise RuntimeError("Rate limiter dependencies missing in production")
        _activate_local_rate_limiter()
        return

    try:
        logger.info("Initializing FastAPI limiter with Redis: %s", config.redis.url)
        client = redis_async.from_url(
            config.redis.connection_string, encoding="utf-8", decode_responses=config.redis.decode_responses
        )
        await FastAPILimiter.init(client)
        app.state.redis = client
        logger.info(
            "FastAPI limiter initialized with Redis: %s", config.redis.connection_string
        )
        configure_rate_limiter()  # use default redis-based limiter
        app.state.local_rate_limiter = None
        return
    except Exception:
        logger.exception("Failed to initialize FastAPI limiter with Redis")
        if config.app.environment == "production":
            raise
        _activate_local_rate_limiter()
        return


# --- Lifecycle hooks ---
async def startup() -> None:
    # Initialize application-wide dependencies here
    # e.g. database connections, caches, etc.

    # DEBUG: Log environment variables from secrets
    import os

    logger.info("=== DEBUG: Environment Variables from Secrets ===")
    secret_vars = []
    for key, value in os.environ.items():
        if any(
            secret in key
            for secret in ["POSTGRES", "REDIS", "CSRF", "SESSION", "BACKUP", "OIDC"]
        ):
            if "PASSWORD" in key or "SECRET" in key:
                if key.endswith("_FILE"):
                    secret_vars.append(f"{key}: {value}")
                else:
                    secret_vars.append(
                        f"{key}: [PRESENT - length {len(value)}] - first 5: '{value[:5]}...'"
                    )
            else:
                secret_vars.append(f"{key}: {value}")

    if secret_vars:
        #logger.info("Found secret environment variables:")
        for var in sorted(secret_vars):
            logger.info("  %s", var)
    else:
        logger.warning("No secret environment variables found!")

    # Compare environment variables with their corresponding files
    logger.info("=== Comparing ENV vars with FILE contents ===")
    for key, value in os.environ.items():
        if key.endswith("_FILE") and any(
            secret in key
            for secret in ["POSTGRES", "REDIS", "CSRF", "SESSION", "BACKUP", "OIDC"]
        ):
            base_name = key[:-5]  # Remove '_FILE' suffix
            env_value = os.getenv(base_name, "")
            if env_value and os.path.exists(value):
                try:
                    with open(value) as f:
                        file_content = f.read()
                    matches = env_value == file_content
                    logger.info(
                        "%s: ENV='%s...' FILE='%s...' MATCH=%s",
                        base_name,
                        env_value[:5],
                        file_content[:5],
                        matches,
                    )
                except Exception as e:
                    logger.error("Failed to read %s: %s", value, e)

    # Specifically check for key passwords
    postgres_password = os.getenv("POSTGRES_PASSWORD", "")
    redis_password = os.getenv("REDIS_PASSWORD", "")
    logger.info("POSTGRES_PASSWORD available: %s", "YES" if postgres_password else "NO")
    logger.info("REDIS_PASSWORD available: %s", "YES" if redis_password else "NO")
    logger.info("=== END DEBUG ===")

    jwks_cache = JWKSCacheInMemory()
    jwks_service = JwksService(jwks_cache)
    jwt_verify_service = JwtVerificationService(jwks_service)
    jwt_generation_service = JwtGeneratorService()

    session_storage = await get_session_storage()
    oidc_client_service = OidcClientService(jwt_verify_service)
    user_session_service = UserSessionService(session_storage)
    auth_session_service = AuthSessionService(session_storage)
    database_service = DbSessionService()

    deps = ApplicationDependencies(
        jwks_cache=jwks_cache,
        jwks_service=jwks_service,
        jwt_verify_service=jwt_verify_service,
        jwt_generation_service=jwt_generation_service,
        oidc_client_service=oidc_client_service,
        user_session_service=user_session_service,
        auth_session_service=auth_session_service,
        database_service=database_service,
    )
    app.state.app_dependencies = deps

    config = get_config()
    logger.info("Starting up application in %s environment", config.app.environment)
    # Validate configuration so we fail fast on misconfiguration

    # Verify JWKS endpoints so auth failures surface early
    if config.oidc.providers:
        jwks_service: JwksService = app.state.app_dependencies.jwks_service
        # issuers = list(main_config.oidc_providers.keys())
        issuers = list(config.oidc.providers.values())
        results = await asyncio.gather(
            *(jwks_service.fetch_jwks(iss) for iss in issuers), return_exceptions=True
        )
        errors = [
            (iss, str(err))
            for iss, err in zip(issuers, results, strict=True)
            if isinstance(err, Exception)
        ]
        for iss, err in errors:
            logger.exception("Failed to fetch JWKS for issuer %s: %s", iss, err)
        if errors and config.app.environment == "production":
            raise RuntimeError(f"JWKS readiness check failed for issuers: {errors}")

    await _initialize_rate_limiter()


async def shutdown() -> None:
    logger.info("Shutting down application")
    await close_rate_limiter()
    app_dependencies: ApplicationDependencies = app.state.app_dependencies
    # Clean up application-wide dependencies here
    await app_dependencies.auth_session_service.purge_expired()
    await app_dependencies.user_session_service.purge_expired()


# --- Route handlers ---


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/ready")
async def readiness() -> dict[str, str]:
    """Readiness check endpoint."""
    return {"status": "ready"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
    """Readiness check endpoint."""
