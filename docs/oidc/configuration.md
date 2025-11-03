# OIDC Configuration Guide

## Overview

This guide covers OIDC provider configuration for production and development environments.

## Provider Configuration

### config.yaml Structure

```yaml
oidc:
  providers:
    # Provider name (used in URLs: /auth/web/login?provider=google)
    google:
      enabled: true
      dev_only: false  # Can be used in production
      
      # Provider endpoints
      issuer: "https://accounts.google.com"
      
      # OAuth credentials (from provider console)
      client_id: "${GOOGLE_CLIENT_ID}"
      client_secret: "${GOOGLE_CLIENT_SECRET}"
      
      # OAuth scopes to request
      scopes:
        - openid      # Required for OIDC
        - profile     # User name, picture
        - email       # User email address
      
      # Your callback URL
      redirect_uri: "${OIDC_GOOGLE_REDIRECT_URI:-https://yourdomain.com/auth/web/callback}"
      
      # Optional: Override auto-discovered endpoints
      # authorization_endpoint: "..."
      # token_endpoint: "..."
      # userinfo_endpoint: "..."
      # jwks_uri: "..."
      # end_session_endpoint: "..."
  
  # Default provider for login page
  default_provider: "google"
```

## Production Providers

### Google

**Setup:**
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create project → APIs & Services → Credentials
3. Create OAuth 2.0 Client ID (Web application)
4. Add authorized redirect URI: `https://yourdomain.com/auth/web/callback`

**Configuration:**
```yaml
google:
  enabled: true
  issuer: "https://accounts.google.com"
  client_id: "${GOOGLE_CLIENT_ID}"
  client_secret: "${GOOGLE_CLIENT_SECRET}"
  scopes: [openid, profile, email]
  redirect_uri: "https://yourdomain.com/auth/web/callback"
```

**Environment Variables:**
```bash
GOOGLE_CLIENT_ID=123456789.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

### Microsoft / Azure AD

**Setup:**
1. Go to [Azure Portal](https://portal.azure.com)
2. Azure Active Directory → App registrations → New registration
3. Add redirect URI: `https://yourdomain.com/auth/web/callback`
4. Certificates & secrets → New client secret

**Configuration:**
```yaml
microsoft:
  enabled: true
  issuer: "https://login.microsoftonline.com/${AZURE_TENANT_ID}/v2.0"
  client_id: "${MICROSOFT_CLIENT_ID}"
  client_secret: "${MICROSOFT_CLIENT_SECRET}"
  scopes: [openid, profile, email]
  redirect_uri: "https://yourdomain.com/auth/web/callback"
```

**Environment Variables:**
```bash
AZURE_TENANT_ID=your-tenant-id
MICROSOFT_CLIENT_ID=your-application-id
MICROSOFT_CLIENT_SECRET=your-client-secret
```

### Auth0

**Setup:**
1. Go to [Auth0 Dashboard](https://manage.auth0.com)
2. Applications → Create Application → Regular Web Application
3. Add callback URL: `https://yourdomain.com/auth/web/callback`
4. Copy Domain, Client ID, Client Secret

**Configuration:**
```yaml
auth0:
  enabled: true
  issuer: "https://${AUTH0_DOMAIN}/"
  client_id: "${AUTH0_CLIENT_ID}"
  client_secret: "${AUTH0_CLIENT_SECRET}"
  scopes: [openid, profile, email]
  redirect_uri: "https://yourdomain.com/auth/web/callback"
```

**Environment Variables:**
```bash
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_CLIENT_ID=your-client-id
AUTH0_CLIENT_SECRET=your-client-secret
```

### Okta

**Setup:**
1. Go to [Okta Admin Console](https://your-domain.okta.com/admin)
2. Applications → Create App Integration → OIDC - Web Application
3. Add sign-in redirect URI: `https://yourdomain.com/auth/web/callback`
4. Copy Client ID and Client Secret

**Configuration:**
```yaml
okta:
  enabled: true
  issuer: "https://${OKTA_DOMAIN}/oauth2/default"
  client_id: "${OKTA_CLIENT_ID}"
  client_secret: "${OKTA_CLIENT_SECRET}"
  scopes: [openid, profile, email]
  redirect_uri: "https://yourdomain.com/auth/web/callback"
```

**Environment Variables:**
```bash
OKTA_DOMAIN=your-domain.okta.com
OKTA_CLIENT_ID=your-client-id
OKTA_CLIENT_SECRET=your-client-secret
```

## Development Provider

### Keycloak (Local Testing Only)

**Purpose:** Test OIDC flows locally without cloud provider credentials.

**Automatic Setup:**
```bash
uv run cli dev start-env  # Starts Keycloak + creates test realm/users
```

**Configuration:**
```yaml
keycloak:
  enabled: true
  dev_only: true  # ⚠️ Disabled automatically in production
  issuer: "http://localhost:8080/realms/test-realm"
  client_id: test-client
  client_secret: test-client-secret
  scopes: [openid, profile, email]
  redirect_uri: "http://localhost:8000/auth/web/callback"
```

**Pre-configured Resources:**
- **Admin Console:** http://localhost:8080/admin (admin/admin)
- **Test Users:** testuser1/password123, testuser2/password123
- **Client:** test-client with secret "test-client-secret"

**When to Use:**
- ✅ Local development without internet
- ✅ Testing OAuth flows
- ✅ Integration tests in CI/CD
- ❌ Never in production

## Environment Variables

### .env File

```bash
# Application
APP_ENVIRONMENT=production

# Google OIDC
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
OIDC_GOOGLE_REDIRECT_URI=https://yourdomain.com/auth/web/callback

# Microsoft OIDC
AZURE_TENANT_ID=your-tenant-id
MICROSOFT_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret

# Auth0 OIDC
AUTH0_DOMAIN=your-tenant.auth0.com
AUTH0_CLIENT_ID=your-auth0-client-id
AUTH0_CLIENT_SECRET=your-auth0-client-secret

# Okta OIDC
OKTA_DOMAIN=your-domain.okta.com
OKTA_CLIENT_ID=your-okta-client-id
OKTA_CLIENT_SECRET=your-okta-client-secret
```

### Docker Secrets (Production)

```yaml
# docker-compose.prod.yml
services:
  app:
    secrets:
      - google_client_secret
      - microsoft_client_secret

secrets:
  google_client_secret:
    file: ./secrets/google_client_secret.txt
  microsoft_client_secret:
    file: ./secrets/microsoft_client_secret.txt
```

## Multi-Provider Setup

### Enable Multiple Providers

```yaml
oidc:
  providers:
    google:
      enabled: true
      # ... config
    
    microsoft:
      enabled: true
      # ... config
    
    auth0:
      enabled: true
      # ... config
  
  # Users choose provider on login page
  default_provider: "google"
```

### Frontend Integration

```html
<!-- Login buttons for each provider -->
<a href="/auth/web/login?provider=google">Login with Google</a>
<a href="/auth/web/login?provider=microsoft">Login with Microsoft</a>
<a href="/auth/web/login?provider=auth0">Login with Auth0</a>
```

## Advanced Settings

### Custom Scopes

```yaml
google:
  scopes:
    - openid
    - profile
    - email
    - https://www.googleapis.com/auth/calendar.readonly  # Google Calendar access
```

### Manual Endpoint Configuration

If provider doesn't support OIDC discovery (`.well-known/openid-configuration`):

```yaml
custom_provider:
  enabled: true
  issuer: "https://provider.com"
  client_id: "${CUSTOM_CLIENT_ID}"
  client_secret: "${CUSTOM_CLIENT_SECRET}"
  
  # Manually specify endpoints
  authorization_endpoint: "https://provider.com/oauth/authorize"
  token_endpoint: "https://provider.com/oauth/token"
  userinfo_endpoint: "https://provider.com/oauth/userinfo"
  jwks_uri: "https://provider.com/oauth/keys"
  end_session_endpoint: "https://provider.com/oauth/logout"
```

### Provider-Specific Settings

**Microsoft with specific tenant:**
```yaml
microsoft:
  issuer: "https://login.microsoftonline.com/your-tenant-id/v2.0"
```

**Okta with custom authorization server:**
```yaml
okta:
  issuer: "https://your-domain.okta.com/oauth2/aus12345"
```

## Validation

### Test Provider Configuration

```bash
# Check OIDC discovery endpoint
curl https://accounts.google.com/.well-known/openid-configuration | jq

# Verify configuration is loaded
uv run cli dev start-server
# Check logs for: "Loaded OIDC provider: google"
```

### Common Configuration Errors

**"Provider not found"**
- Check provider name matches config.yaml
- Ensure `enabled: true`

**"Invalid issuer"**
- Verify issuer URL is correct (no trailing slash for some providers)
- Check network connectivity to issuer

**"Redirect URI mismatch"**
- Ensure redirect URI in config.yaml matches provider console exactly
- Include protocol (http/https) and no trailing slash

**"Invalid client credentials"**
- Verify CLIENT_ID and CLIENT_SECRET environment variables
- Check for whitespace in credentials
- Ensure secrets are not expired

## Related Documentation

- [Main Guide](./main.md) - OIDC overview and architecture
- [Usage Examples](./usage.md) - Authentication implementation
- [Security Guide](../security.md) - Security best practices
