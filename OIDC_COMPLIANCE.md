# OIDC Relying Party Implementation

## Overview

This application server acts as an **OIDC Relying Party (Client)** that validates tokens from external identity providers and maintains domain-specific User objects. It supports a hybrid authentication architecture:

- **BFF Pattern**: For web SPAs using authorization code flow with PKCE and HttpOnly cookies
- **JWT Bearer Tokens**: For mobile apps and direct API access

It does **NOT** act as an identity provider itself.

## Architecture

```
External OIDC Provider (Auth0, Google, etc.)
    ↓ (authorization code flow for web / JWT tokens for mobile)
Your Application (OIDC Relying Party)
    ├── BFF Router: Web clients → Sessions + HttpOnly cookies  
    └── JWT Router: Mobile/API → Bearer token validation
    ↓ (provisions users & manages sessions)
Domain User Objects + Business Logic
```

## Hybrid Authentication Patterns

### Web Clients (BFF Pattern)
- **Authorization Code Flow** with PKCE
- **HttpOnly Cookies** for session management
- **CSRF Protection** with secure tokens
- **Server-side Sessions** with refresh token storage
- **True Logout** capability

### Mobile/API Clients (JWT Pattern)  
- **Bearer Token** authentication
- **JWT Validation** with JWKS
- **Stateless** operation
- **JIT User Provisioning** from claims

## OIDC Client Features

### 1. Token Validation (JWT Pattern)
- **JWT Verification**: Validates tokens from configured OIDC providers
- **JWKS Integration**: Fetches and caches public keys from provider JWKS endpoints
- **Multi-Provider Support**: Can validate tokens from multiple OIDC providers simultaneously
- **Algorithm Validation**: Only accepts tokens signed with configured algorithms

### 2. JIT User Provisioning
- **Automatic User Creation**: Creates domain User objects on first authentication
- **Identity Mapping**: Links external OIDC identities to internal User records
- **Claim Extraction**: Maps OIDC claims to User attributes (name, email, etc.)
- **Fallback Logic**: Handles missing name claims gracefully

### 3. Authorization System
- **Scope-based Authorization**: Extracts and validates scopes from JWT tokens
- **Role-based Authorization**: Maps identity provider roles to application permissions
- **Multi-format Support**: Handles various claim formats (Auth0, Keycloak, Google, etc.)

## Implementation Details

### Token Processing Flow
1. Client sends request with `Authorization: Bearer <token>` header
2. System validates JWT signature using provider's JWKS
3. Extracts claims (issuer, subject, email, scopes, roles)
4. Looks up existing identity mapping or creates new User via JIT provisioning
5. Attaches User object and claims to request context
6. Proceeds with business logic using domain User object

### Configuration

#### Required Settings
```python
# External OIDC Provider Configuration
issuer_jwks_map: dict[str, str] = {
    "https://your-domain.auth0.com/": "https://your-domain.auth0.com/.well-known/jwks.json",
    "https://accounts.google.com": "https://www.googleapis.com/oauth2/v3/certs"
}

# Token Validation
audiences: list[str] = ["your-api-audience"]
allowed_algorithms: list[str] = ["RS256", "ES256"] 
clock_skew: int = 60  # seconds

# Custom Claim Mapping (optional)
uid_claim: str | None = None  # Use custom UID claim if available
```

### Enhanced JWT Service

#### Multi-Provider Scope Extraction
Handles different scope claim formats from various providers:
- **Standard**: `scope` (space-separated string)
- **Auth0**: `scp` (string or array)
- **Custom**: `scopes` (array)

#### Multi-Provider Role Extraction  
Supports role claims from various identity providers:
- **Standard**: `roles`, `groups`, `authorities`
- **Auth0**: `app_metadata.roles`, custom namespace roles
- **Keycloak**: `realm_access.roles`
- **Format Handling**: Both space-separated strings and arrays

## Client Endpoints

### Authentication Status
- **URL**: `GET /auth/jit/me`
- **Purpose**: Returns current user's authentication state
- **Response**: Domain User object + JWT claims + extracted scopes/roles
- **Use Case**: Debugging, client-side user info display

### Authorization Examples
- **URL**: `GET /auth/jit/protected-scope`
- **Protection**: Requires `read:protected` scope
- **Purpose**: Demonstrates scope-based authorization

- **URL**: `GET /auth/jit/protected-role` 
- **Protection**: Requires `admin` role
- **Purpose**: Demonstrates role-based authorization

## Database Schema

### User Entity (Domain Object)
```python
class User:
    id: UUID                 # Internal domain ID
    first_name: str
    last_name: str  
    email: str | None
    # ... other domain-specific fields
```

### UserIdentity Entity (OIDC Mapping)
```python
class UserIdentity:
    id: UUID                 # Internal mapping ID
    issuer: str             # OIDC provider issuer URL
    subject: str            # OIDC subject claim
    uid_claim: str | None   # Custom UID if available
    user_id: UUID           # Foreign key to User
```

## Integration Examples

### Frontend Integration
```javascript
// 1. User authenticates with external OIDC provider (Auth0, Google, etc.)
const token = await authenticateWithProvider();

// 2. Use token to call your API
const response = await fetch('/api/your-endpoint', {
    headers: {
        'Authorization': `Bearer ${token}`
    }
});

// 3. API validates token and provides domain-specific functionality
const data = await response.json();
```

### Provider Configuration Examples

#### Auth0
```python
issuer_jwks_map = {
    "https://your-domain.auth0.com/": "https://your-domain.auth0.com/.well-known/jwks.json"
}
audiences = ["your-auth0-api-identifier"]
```

#### Google
```python  
issuer_jwks_map = {
    "https://accounts.google.com": "https://www.googleapis.com/oauth2/v3/certs"
}
audiences = ["your-google-client-id.apps.googleusercontent.com"]
```

#### Azure AD
```python
issuer_jwks_map = {
    "https://login.microsoftonline.com/{tenant}/v2.0": "https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"
}
audiences = ["your-azure-app-id"]
```

## Security Features

### Token Validation
- ✅ **Signature Verification**: Uses provider public keys
- ✅ **Timing Validation**: Checks `exp`, `nbf`, `iat` claims with clock skew tolerance
- ✅ **Audience Validation**: Ensures token is intended for this API
- ✅ **Issuer Validation**: Only accepts tokens from configured providers

### Identity Security  
- ✅ **Identity Isolation**: External identities mapped to internal User IDs
- ✅ **JIT Provisioning**: Secure user creation with claim validation
- ✅ **Multi-Provider Support**: Users can authenticate via different providers
- ✅ **Claim Extraction**: Safe handling of provider-specific claim formats

## Testing

### Unit Tests
- JWT validation logic
- Claim extraction from different providers
- JIT user provisioning scenarios  
- Authorization dependency testing

### Integration Tests
- End-to-end authentication flow
- Multi-provider token validation
- User creation and identity mapping
- Authorization enforcement

## Standards Compliance

### OpenID Connect 1.0 (Client Side)
- ✅ **JWT Token Validation**: Proper signature and claim validation
- ✅ **JWKS Integration**: Fetches provider public keys
- ✅ **Multi-Provider Support**: Can integrate with any OIDC-compliant provider
- ✅ **Claim Processing**: Handles standard OIDC claims appropriately

### Security Best Practices
- ✅ **Algorithm Allowlist**: Only accepts configured signing algorithms
- ✅ **Audience Validation**: Prevents token misuse across services
- ✅ **Clock Skew Tolerance**: Handles reasonable time differences
- ✅ **Error Handling**: Secure failure modes for invalid tokens

## API Endpoints

### BFF Pattern Endpoints (Web Clients)

#### `GET /auth/web/login`
Initiates OIDC authorization code flow with PKCE:
- Generates PKCE challenge and state parameter
- Creates temporary auth session
- Redirects to OIDC provider authorization endpoint

#### `GET /auth/web/callback`
Handles OIDC authorization callback:
- Validates state parameter (CSRF protection)
- Exchanges authorization code for tokens using PKCE verifier
- Provisions user from claims (JIT)
- Creates persistent session with HttpOnly cookie

#### `POST /auth/web/logout`
Terminates user session:
- Validates CSRF token
- Clears session and HttpOnly cookie
- Optional: initiates logout with OIDC provider

#### `GET /auth/web/me`
Returns current user authentication state:
- Session-based authentication via HttpOnly cookie
- Returns user info and authentication status

### JWT Pattern Endpoints (Mobile/API Clients)

#### `GET /auth/me`
Returns authenticated user information:
- Requires `Authorization: Bearer <jwt_token>` header
- Validates JWT signature and claims
- Performs JIT user provisioning if needed

#### `GET /auth/protected-scope`
Example scope-protected endpoint:
- Requires specific scope in JWT token
- Demonstrates scope-based authorization

#### `GET /auth/protected-role`
Example role-protected endpoint:
- Requires specific role in JWT token
- Demonstrates role-based authorization

## Future Enhancements

### Potential Additions
1. **Token Refresh Handling**: Support for refresh token flows
2. **Provider Metadata Discovery**: Auto-configure from `.well-known/openid-configuration`
3. **Advanced Claim Mapping**: Configurable claim-to-attribute mapping
4. **Multi-Tenant Support**: Provider configuration per tenant
5. **Audit Logging**: Track authentication and authorization events

### Operational Considerations
1. **JWKS Caching**: Implement proper cache invalidation strategies
2. **Provider Monitoring**: Health checks for external identity providers
3. **Performance Optimization**: Cache user lookups and identity mappings
4. **Backup Authentication**: Fallback mechanisms for provider outages
5. **Compliance Reporting**: User access and data processing logs

## Usage Summary

This application server:
- ✅ **Validates tokens** from external OIDC providers (Auth0, Google, Azure, etc.)
- ✅ **Creates domain User objects** with JIT provisioning
- ✅ **Maps external identities** to internal user records
- ✅ **Enforces authorization** using scopes and roles from identity providers
- ✅ **Maintains separation** between external identity and domain logic

It does **NOT**:
- ❌ Issue its own tokens (not an identity provider)
- ❌ Provide OIDC discovery endpoints  
- ❌ Handle user registration/login flows
- ❌ Store user credentials