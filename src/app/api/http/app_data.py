from dataclasses import dataclass

from src.app.core.services.jwt import JwtGeneratorService, JwtVerificationService
from src.app.core.services.jwt.jwks import JWKSCacheInMemory, JwksService
from src.app.core.services.oidc_client_service import OidcClientService
from src.app.core.services.session.auth_session import AuthSessionService
from src.app.core.services.session.user_session import UserSessionService


@dataclass
class ApplicationDependencies:
    jwks_cache: JWKSCacheInMemory
    jwks_service: JwksService
    jwt_verify_service: JwtVerificationService
    jwt_generation_service: JwtGeneratorService
    oidc_client_service: OidcClientService
    user_session_service: UserSessionService
    auth_session_service: AuthSessionService
