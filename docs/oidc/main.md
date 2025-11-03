# OIDC Authentication

## Overview

This application uses **OpenID Connect (OIDC)** for authentication, supporting multiple identity providers including Google, Microsoft, Auth0, Okta, and other enterprise providers.

OIDC is an identity layer built on top of OAuth 2.0 that provides:
- **Secure authentication** via industry-standard protocols
- **Single Sign-On (SSO)** across applications
- **Token-based authorization** with JWT
- **User profile information** from trusted identity providers
- **Multi-provider support** with unified integration

## Architecture

```
┌─────────────┐           ┌──────────────┐           ┌─────────────┐
│   Browser   │           │  FastAPI App │           │ OIDC Provider│
│             │           │    (BFF)     │           │(Auth0/Google)│
└─────────────┘           └──────────────┘           └─────────────┘
      │                           │                          │
      │ 1. /auth/web/login        │                          │
      ├──────────────────────────>│                          │
      │                           │                          │
      │                           │ 2. Redirect to provider  │
      │                           ├─────────────────────────>│
      │                           │                          │
      │ 3. Redirect to provider   │                          │
      │<──────────────────────────┤                          │
      │                                                      │
      │ 4. User authenticates                                │
      ├─────────────────────────────────────────────────────>│
      │                                                      │
      │ 5. Redirect with auth code                           │
      │<─────────────────────────────────────────────────────┤
      │                           │                          │
      │ 6. /auth/web/callback     │                          │
      ├──────────────────────────>│                          │
      │                           │ 7. Exchange code         │
      │                           ├─────────────────────────>│
      │                           │    for tokens            │
      │                           │<─────────────────────────┤
      │                           │ 8. Validate token (JWKS) │
      │                           │                          │
      │ 9. Set session cookie     │                          │
      │<──────────────────────────┤                          │
      │                           │                          │
```

### BFF Pattern (Backend for Frontend)

The application implements the **BFF pattern** where:
1. Browser never sees access tokens or ID tokens
2. All OAuth flows handled server-side
3. Session established using secure HttpOnly cookies
4. CSRF protection with double-submit cookies
5. Client fingerprinting for additional security

## Supported Providers

### Production Providers

**Google:**
```yaml
oidc:
  providers:
    google:
      enabled: true
      issuer: "https://accounts.google.com"
      client_id: "${GOOGLE_CLIENT_ID}"
      client_secret: "${GOOGLE_CLIENT_SECRET}"
      scopes: [openid, profile, email]
```

**Microsoft:**
```yaml
oidc:
  providers:
    microsoft:
      enabled: true
      issuer: "https://login.microsoftonline.com/${AZURE_TENANT_ID}/v2.0"
      client_id: "${MICROSOFT_CLIENT_ID}"
      client_secret: "${MICROSOFT_CLIENT_SECRET}"
      scopes: [openid, profile, email]
```

**Auth0:**
```yaml
oidc:
  providers:
    auth0:
      enabled: true
      issuer: "https://${AUTH0_DOMAIN}/"
      client_id: "${AUTH0_CLIENT_ID}"
      client_secret: "${AUTH0_CLIENT_SECRET}"
      scopes: [openid, profile, email]
```

**Okta:**
```yaml
oidc:
  providers:
    okta:
      enabled: true
      issuer: "https://${OKTA_DOMAIN}/oauth2/default"
      client_id: "${OKTA_CLIENT_ID}"
      client_secret: "${OKTA_CLIENT_SECRET}"
      scopes: [openid, profile, email]
```

See [configuration.md](./configuration.md) for complete setup instructions.

### Development Provider

**Keycloak (Development Only):**

For local development and testing, a Keycloak instance is included in the Docker Compose development environment:

```yaml
oidc:
  providers:
    keycloak:
      enabled: true
      dev_only: true  # Automatically disabled in production
      issuer: "http://localhost:8080/realms/test-realm"
      client_id: test-client
      client_secret: test-client-secret
      scopes: [openid, profile, email]
```

**Quick Start:**
```bash
# Start dev environment (includes Keycloak)
uv run cli dev start-env

# Keycloak is available at http://localhost:8080
# Pre-configured test users: testuser1/password123, testuser2/password123
```

> ⚠️ **Development Only**: Keycloak is provided as a convenience for testing OIDC flows locally. Production deployments must use a managed identity provider (Google, Auth0, Okta, etc.).

See [Development Setup](#development-setup) section below for Keycloak details.

## OAuth 2.0 Flows

### Authorization Code Flow (Recommended)

The standard, most secure OAuth flow:

1. User clicks "Login with Provider"
2. Redirected to provider's authorization endpoint
3. User authenticates and grants consent
4. Provider redirects back with authorization code
5. Backend exchanges code for tokens (server-to-server)
6. Backend validates tokens and creates session
7. User receives secure session cookie

**Endpoints:**
- **Login:** `GET /auth/web/login?provider=google`
- **Callback:** `GET /auth/web/callback?code=...&state=...`
- **Status:** `GET /auth/web/status`
- **Logout:** `POST /auth/web/logout`

### Client Credentials Flow (M2M)

For service-to-service authentication without user interaction:

```python
# Exchange client credentials for access token
data = {
    "grant_type": "client_credentials",
    "client_id": "service-client",
    "client_secret": "service-secret",
    "scope": "api.read api.write"
}
```

Used for backend services, cron jobs, and API integrations.

## Token Validation

### JWT Structure

**Access Token Claims:**
```json
{
  "iss": "https://accounts.google.com",
  "sub": "user-unique-id",
  "aud": "your-client-id",
  "exp": 1730570400,
  "iat": 1730570100,
  "email": "user@example.com",
  "email_verified": true,
  "name": "User Name"
}
```

### Validation Process

1. **Signature Verification:** Verify JWT signature using JWKS from provider
2. **Issuer Check:** Ensure `iss` matches configured provider
3. **Audience Check:** Ensure `aud` matches your client ID
4. **Expiration:** Ensure `exp` is in the future
5. **Claims Validation:** Verify required claims are present

**JWKS Caching:**
- Public keys cached for 1 hour (configurable)
- Automatic refresh on key rotation
- Fallback to direct fetch if cache miss

```python
# Automatic validation via dependency injection
from fastapi import Depends
from src.app.api.http.deps import get_authenticated_user

@app.get("/api/protected")
async def protected_route(user = Depends(get_authenticated_user)):
    return {"user": user.username}
```

## Session Management

### Session Creation

After successful OIDC authentication:

1. Generate secure session ID (UUID4)
2. Store session data in Redis:
   - User identity (email, name, provider)
   - Session metadata (created_at, last_active, ip, user_agent)
   - CSRF token
3. Return HttpOnly cookie with session ID
4. Client fingerprint stored for validation

### Session Cookie

```http
Set-Cookie: session_id=<encrypted-session-id>; 
            HttpOnly; 
            Secure; 
            SameSite=Lax; 
            Max-Age=86400
```

**Security Features:**
- **HttpOnly:** Not accessible via JavaScript
- **Secure:** HTTPS only (production)
- **SameSite:** CSRF protection
- **Signed:** Cookie integrity validation
- **Encrypted:** Session ID encrypted with AES-256

### Session Lifecycle

```python
# Configuration in config.yaml
app:
  sessions:
    session_duration_secs: 86400        # 24 hours
    max_session_age_secs: 604800        # 7 days (with refresh)
    inactive_timeout_secs: 3600         # 1 hour
    session_rotation_interval_secs: 1800 # 30 minutes
```

**Session states:**
- **Active:** Within duration and recently used
- **Expired:** Past max age or inactive timeout
- **Rotated:** Session ID refreshed for security

## Security Features

### CSRF Protection

**Double-Submit Cookie Pattern:**
```http
Set-Cookie: csrf_token=<token>; SameSite=Lax
X-CSRF-Token: <token>  # Required in request header
```

All state-changing requests (POST, PUT, DELETE) must include CSRF token.

### Client Fingerprinting

**Fingerprint Components:**
- User-Agent header
- IP address (with proxy detection)
- Accept-Language header

Fingerprint mismatch triggers re-authentication.

### Rate Limiting

```yaml
rate_limiter:
  auth_endpoints:
    login: 10/minute
    callback: 20/minute
    logout: 10/minute
```

Prevents brute force and denial of service attacks.

## Development Setup

### Keycloak (Local Testing)

The development environment includes a pre-configured Keycloak instance for testing OIDC flows without requiring production provider credentials.

**Automatic Setup:**
```bash
# Start development environment
uv run cli dev start-env

# Keycloak starts at http://localhost:8080
# Setup script automatically creates:
# - test-realm
# - test-client (with client_secret: test-client-secret)
# - testuser1/password123
# - testuser2/password123
```

**Test Authentication:**
```bash
# Navigate to login endpoint
curl http://localhost:8000/auth/web/login?provider=keycloak

# Or visit in browser to see full OAuth flow
```

**Admin Access:**
- **URL:** http://localhost:8080/admin
- **Credentials:** admin/admin
- **Realm:** test-realm

**What's Included:**
- Pre-configured realm and client
- Two test users ready to use
- Automatic OIDC endpoint discovery
- All standard OAuth flows enabled

**What's NOT Included (Production Required):**
- High availability / load balancing
- Automated backups
- Security hardening (TLS, rate limiting)
- Monitoring and alerting
- Compliance features (audit logs, MFA)
- Enterprise support

> 💡 **Tip:** Use Keycloak for rapid local development, then switch to Google/Auth0/Okta for staging and production by changing `default_provider` in config.yaml.

## Troubleshooting

### Common Issues

**"Invalid redirect URI"**
- Ensure callback URL matches provider configuration exactly
- Check for trailing slashes
- Verify protocol (http vs https)

**"Token validation failed"**
- Check system clock synchronization (JWT exp/iat validation)
- Verify JWKS endpoint is reachable
- Confirm issuer matches provider configuration

**"Session expired"**
- Check Redis connectivity
- Verify session duration settings
- Ensure cookies are being sent (check SameSite settings)

**"CSRF token mismatch"**
- Ensure CSRF token is included in request headers
- Check cookie settings (SameSite, Secure)
- Verify frontend is reading cookie correctly

### Debug Mode

Enable verbose OIDC logging:

```yaml
logging:
  level: DEBUG
  loggers:
    src.app.core.services.oidc_client_service: DEBUG
    src.app.core.services.session_service: DEBUG
```

## Related Documentation

- [Configuration Guide](./configuration.md) - Provider setup and settings
- [Usage Examples](./usage.md) - Code examples and integration
- [Security Guide](../security.md) - Authentication architecture
- [Development Environment](../dev_env/README.md) - Local setup
