# OIDC Usage Guide

## Overview

Practical examples for implementing OIDC authentication in your application.

## Authentication Flow

### Initiate Login

```python
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

@app.get("/login")
async def login(provider: str = "google"):
    """Redirect user to OIDC provider for authentication."""
    return RedirectResponse(url=f"/auth/web/login?provider={provider}")
```

### Handle Callback

The application automatically handles the OAuth callback at `/auth/web/callback`. After successful authentication, a session cookie is set.

### Protected Routes

```python
from fastapi import Depends
from src.app.api.http.deps import get_authenticated_user

@app.get("/api/profile")
async def get_profile(user = Depends(get_authenticated_user)):
    """Protected endpoint requiring authentication."""
    return {
        "username": user.username,
        "email": user.email,
        "provider": user.provider
    }
```

### Check Auth Status

```python
@app.get("/api/auth/status")
async def auth_status(request: Request):
    """Check if user is authenticated."""
    # Session validation happens automatically via dependency
    try:
        user = await get_authenticated_user(request)
        return {
            "authenticated": True,
            "user": user.username
        }
    except:
        return {
            "authenticated": False
        }
```

### Logout

```python
from fastapi.responses import RedirectResponse

@app.post("/logout")
async def logout():
    """Logout user and clear session."""
    return RedirectResponse(
        url="/auth/web/logout",
        status_code=303
    )
```

## Frontend Integration

### React Example

```typescript
// Login component
function LoginButton({ provider }: { provider: string }) {
  const handleLogin = () => {
    window.location.href = `/auth/web/login?provider=${provider}`;
  };

  return (
    <button onClick={handleLogin}>
      Login with {provider}
    </button>
  );
}

// Check auth status
async function checkAuth() {
  const response = await fetch('/api/auth/status', {
    credentials: 'include'  // Include cookies
  });
  const data = await response.json();
  return data.authenticated;
}

// Protected API call
async function fetchUserData() {
  const response = await fetch('/api/profile', {
    credentials: 'include'  // Include session cookie
  });
  
  if (response.status === 401) {
    window.location.href = '/login';
    return;
  }
  
  return response.json();
}

// Logout
async function logout() {
  await fetch('/auth/web/logout', {
    method: 'POST',
    credentials: 'include'
  });
  window.location.href = '/';
}
```

### Vanilla JavaScript

```html
<!-- Login buttons -->
<button onclick="login('google')">Login with Google</button>
<button onclick="login('microsoft')">Login with Microsoft</button>

<script>
  function login(provider) {
    window.location.href = `/auth/web/login?provider=${provider}`;
  }

  async function fetchProtectedData() {
    try {
      const response = await fetch('/api/protected', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        console.log('User data:', data);
      } else if (response.status === 401) {
        login('google');
      }
    } catch (error) {
      console.error('Error:', error);
    }
  }
</script>
```

## Token Handling

### Accessing Token Claims

```python
from src.app.core.services.jwt.jwt_verify import JwtVerifier

@app.get("/api/user-info")
async def get_user_info(user = Depends(get_authenticated_user)):
    """Get detailed user information from token claims."""
    
    # User object contains validated token claims
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "email_verified": user.email_verified,
        "name": user.name,
        "provider": user.provider,
        "provider_user_id": user.provider_user_id
    }
```

### Custom User Lookup

```python
from src.app.entities.core.user.repository import UserRepository

@app.get("/api/user/profile")
async def get_user_profile(
    current_user = Depends(get_authenticated_user),
    db = Depends(get_db_session)
):
    """Get user profile from database."""
    
    # Look up user by identity
    user_repo = UserRepository(db)
    user = await user_repo.get_by_identity(
        provider=current_user.provider,
        provider_user_id=current_user.provider_user_id
    )
    
    if not user:
        # First time login - create user record
        user = await user_repo.create({
            "username": current_user.username,
            "email": current_user.email
        })
    
    return user
```

## Testing

### Integration Test

```python
import pytest
from fastapi.testclient import TestClient

def test_protected_endpoint_requires_auth(client: TestClient):
    """Test that protected endpoints require authentication."""
    
    response = client.get("/api/profile")
    assert response.status_code == 401

def test_protected_endpoint_with_valid_session(
    client: TestClient,
    authenticated_session
):
    """Test protected endpoint with valid session."""
    
    # authenticated_session fixture sets up session cookie
    response = client.get("/api/profile")
    assert response.status_code == 200
    assert "username" in response.json()
```

### Mock OIDC Provider

```python
import pytest
from unittest.mock import Mock, patch

@pytest.fixture
def mock_oidc_token():
    """Mock OIDC token for testing."""
    return {
        "access_token": "mock-access-token",
        "id_token": "mock-id-token",
        "refresh_token": "mock-refresh-token",
        "expires_in": 3600
    }

def test_login_flow(client: TestClient, mock_oidc_token):
    """Test login flow with mocked provider."""
    
    with patch('httpx.AsyncClient.post') as mock_post:
        mock_post.return_value.json.return_value = mock_oidc_token
        
        # Test callback handling
        response = client.get(
            "/auth/web/callback",
            params={
                "code": "mock-auth-code",
                "state": "mock-state"
            },
            follow_redirects=False
        )
        
        assert response.status_code == 303
        assert "session_id" in response.cookies
```

### Using Keycloak for Testing

```python
import httpx

async def get_test_token(username: str = "testuser1", password: str = "password123"):
    """Get real token from development Keycloak for testing."""
    
    token_url = "http://localhost:8080/realms/test-realm/protocol/openid-connect/token"
    
    data = {
        "grant_type": "password",
        "client_id": "test-client",
        "client_secret": "test-client-secret",
        "username": username,
        "password": password,
        "scope": "openid profile email"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, data=data)
        return response.json()

# Use in tests
@pytest.mark.integration
async def test_with_real_token(client: TestClient):
    """Test with real token from Keycloak."""
    
    tokens = await get_test_token()
    
    response = client.get(
        "/api/profile",
        headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    
    assert response.status_code == 200
```

## Session Management

### Session Lifetime

Sessions are automatically managed based on configuration:

```yaml
app:
  sessions:
    session_duration_secs: 86400        # 24 hours
    max_session_age_secs: 604800        # 7 days max
    inactive_timeout_secs: 3600         # 1 hour inactivity
    session_rotation_interval_secs: 1800 # Rotate every 30 min
```

### Manual Session Check

```python
from src.app.core.services.session_service import SessionService

@app.get("/api/session/info")
async def session_info(
    request: Request,
    session_service = Depends(get_session_service)
):
    """Get session information."""
    
    session = await session_service.get_session_from_request(request)
    
    if not session:
        return {"active": False}
    
    return {
        "active": True,
        "created_at": session.created_at,
        "last_active": session.last_active,
        "expires_at": session.expires_at
    }
```

## Error Handling

### Handle Authentication Errors

```python
from fastapi import HTTPException, status

@app.exception_handler(HTTPException)
async def handle_auth_errors(request: Request, exc: HTTPException):
    """Handle authentication errors gracefully."""
    
    if exc.status_code == 401:
        # Redirect to login for unauthenticated requests
        return RedirectResponse(url="/login")
    
    return exc
```

### Provider-Specific Errors

```python
@app.get("/auth/web/callback")
async def handle_callback(error: str = None, error_description: str = None):
    """Handle OAuth callback with error handling."""
    
    if error:
        # Provider returned error (e.g., user denied consent)
        logger.warning(f"OAuth error: {error} - {error_description}")
        return RedirectResponse(url=f"/login?error={error}")
    
    # Normal callback handling...
```

## Security Best Practices

### CSRF Protection

All state-changing endpoints automatically validate CSRF tokens:

```python
from fastapi import Request

@app.post("/api/update-profile")
async def update_profile(
    request: Request,
    user = Depends(get_authenticated_user)
):
    """CSRF token automatically validated by dependency."""
    # Safe to process state changes
    pass
```

### Rate Limiting

Authentication endpoints are rate-limited by default:

```yaml
rate_limiter:
  auth_endpoints:
    login: 10/minute
    callback: 20/minute
```

### Secure Cookies

Session cookies are automatically configured with security headers:
- `HttpOnly` - Not accessible via JavaScript
- `Secure` - HTTPS only (production)
- `SameSite=Lax` - CSRF protection

## Related Documentation

- [Main Guide](./main.md) - OIDC overview
- [Configuration](./configuration.md) - Provider setup
- [Security Guide](../security.md) - Security architecture
