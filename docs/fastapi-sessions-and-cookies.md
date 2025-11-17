# FastAPI Sessions and Cookies

Learn how API Forge implements secure session management for FastAPI applications using HttpOnly cookies, CSRF protection, SameSite attributes, and client fingerprinting. This guide covers production-ready session security patterns for FastAPI authentication.

## Overview

API Forge uses **session-based authentication** instead of JWT tokens stored in localStorage. This approach provides:

- **HttpOnly cookies** - JavaScript cannot access session tokens
- **CSRF protection** - Double-submit cookie pattern with cryptographic verification
- **SameSite strict** - Cookies not sent on cross-site requests
- **Client fingerprinting** - Detect session theft
- **Session rotation** - Periodic session ID refresh
- **Secure flag** - Cookies only sent over HTTPS in production
- **Redis storage** - Fast, scalable session persistence

This architecture follows the **Backend for Frontend (BFF)** pattern, keeping authentication concerns on the server.

## Session Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Web Browser                         │
│                                                     │
│  Cookies (HttpOnly, Secure, SameSite=Strict):      │
│    • session_id=sess_abc123...                     │
│    • csrf_token=csrf_xyz789...                     │
│                                                     │
│  JavaScript cannot access session cookie!          │
└────────────────┬────────────────────────────────────┘
                 │
                 │ HTTPS (cookies sent automatically)
                 ↓
┌─────────────────────────────────────────────────────┐
│              FastAPI Application                    │
│                                                     │
│  1. Extract session_id from cookie                 │
│  2. Validate CSRF token                            │
│  3. Verify client fingerprint                      │
│  4. Load session from Redis                        │
└────────────────┬────────────────────────────────────┘
                 │
                 │ GET session:sess_abc123
                 ↓
┌─────────────────────────────────────────────────────┐
│                    Redis                            │
│                                                     │
│  session:sess_abc123 = {                            │
│    "user_id": 42,                                   │
│    "email": "user@example.com",                     │
│    "created_at": 1699564800,                        │
│    "fingerprint": "sha256hash...",                  │
│    "last_rotated_at": 1699566400                    │
│  }                                                  │
└─────────────────────────────────────────────────────┘
```

## Cookie Configuration

### Production Settings

```yaml
# config.yaml
app:
  session:
    signing_secret_file: /run/secrets/session_signing_secret
    domain: ${SESSION_DOMAIN:-.example.com}  # Subdomain sharing
    secure: true                              # HTTPS only
    http_only: true                           # No JavaScript access
    same_site: strict                         # Strict CSRF prevention
    max_age: 3600                             # 1 hour expiration
    rotation_interval: 1800                   # Rotate every 30 minutes
    
  csrf:
    signing_secret_file: /run/secrets/csrf_signing_secret
    token_name: csrf_token
    header_name: X-CSRF-Token
```

### Cookie Attributes Explained

**HttpOnly**:
- Cookie not accessible via `document.cookie`
- Prevents XSS attacks from stealing session tokens
- **Always enabled** in API Forge

**Secure**:
- Cookie only sent over HTTPS connections
- Prevents man-in-the-middle attacks
- **Enabled in production**, disabled in development

**SameSite=Strict**:
- Cookie not sent on cross-site requests
- Prevents CSRF attacks at the browser level
- Can use `lax` for limited cross-site navigation
- **Strict by default** in API Forge

**Domain**:
- `.example.com` - Cookie shared across subdomains
- `api.example.com` - Cookie only for API domain
- **Configure based on your architecture**

**Max-Age**:
- Cookie expiration in seconds
- Session expires client-side after this duration
- **1 hour default**, adjust based on security requirements

## Session Structure

### Session Data in Redis

```python
# Redis key: session:sess_abc123xyz
{
    "session_id": "sess_abc123xyz",
    "user_id": 42,
    "email": "user@example.com",
    "provider": "google",
    "created_at": 1699564800,
    "last_activity_at": 1699566400,
    "last_rotated_at": 1699566400,
    "fingerprint": "sha256:abcdef123456...",
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0 ...",
}
```

**Fields**:
- `session_id` - Unique session identifier (cryptographically random)
- `user_id` - User ID from database
- `email` - User email (cached for display)
- `provider` - OIDC provider used (google, microsoft, keycloak)
- `created_at` - Unix timestamp when session created
- `last_activity_at` - Last request time (for idle timeout)
- `last_rotated_at` - Last session ID rotation (security measure)
- `fingerprint` - Client fingerprint hash (browser/device identification)
- `ip_address` - Client IP address (for anomaly detection)
- `user_agent` - Client user agent string

### Session ID Format

```python
# Format: sess_{32_random_hex_chars}
session_id = f"sess_{secrets.token_hex(32)}"
# Example: sess_a1b2c3d4e5f6789012345678901234567890abcdef

# Stored in Redis with prefix
redis_key = f"session:{session_id}"
```

**Security Properties**:
- 256 bits of entropy (cryptographically secure)
- Unpredictable (not sequential or guessable)
- Unique across all sessions
- Short enough for cookie storage

## Session Creation

### After OIDC Authentication

```python
# src/app/core/services/session_service.py
from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Optional

from fastapi import Request, Response
from redis import Redis

class SessionService:
    """Service for managing user sessions"""
    
    def __init__(self, redis: Redis, config: SessionConfig):
        self.redis = redis
        self.config = config
    
    def create_session(
        self,
        response: Response,
        user_id: int,
        email: str,
        provider: str,
        request: Request
    ) -> str:
        """
        Create new session after successful authentication
        
        Returns:
            session_id
        """
        # Generate session ID
        session_id = self._generate_session_id()
        
        # Generate client fingerprint
        fingerprint = self._generate_fingerprint(request)
        
        # Create session data
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "email": email,
            "provider": provider,
            "created_at": int(datetime.utcnow().timestamp()),
            "last_activity_at": int(datetime.utcnow().timestamp()),
            "last_rotated_at": int(datetime.utcnow().timestamp()),
            "fingerprint": fingerprint,
            "ip_address": request.client.host,
            "user_agent": request.headers.get("user-agent", ""),
        }
        
        # Store in Redis with expiration
        redis_key = f"session:{session_id}"
        self.redis.setex(
            redis_key,
            timedelta(seconds=self.config.max_age),
            json.dumps(session_data)
        )
        
        # Set session cookie
        response.set_cookie(
            key="session_id",
            value=session_id,
            max_age=self.config.max_age,
            httponly=True,
            secure=self.config.secure,
            samesite=self.config.same_site,
            domain=self.config.domain
        )
        
        # Set CSRF token cookie
        csrf_token = self._generate_csrf_token(session_id)
        response.set_cookie(
            key=self.config.csrf.token_name,
            value=csrf_token,
            max_age=self.config.max_age,
            httponly=False,  # JavaScript needs to read this!
            secure=self.config.secure,
            samesite=self.config.same_site,
            domain=self.config.domain
        )
        
        return session_id
    
    def _generate_session_id(self) -> str:
        """Generate cryptographically secure session ID"""
        return f"sess_{secrets.token_hex(32)}"
    
    def _generate_fingerprint(self, request: Request) -> str:
        """Generate client fingerprint from request"""
        # Combine multiple client characteristics
        components = [
            request.headers.get("user-agent", ""),
            request.headers.get("accept-language", ""),
            request.headers.get("accept-encoding", ""),
            # Don't use IP (can change with mobile networks)
        ]
        
        fingerprint_string = "|".join(components)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()
```

## Session Validation

### Middleware for All Requests

```python
# src/app/api/http/middleware.py
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

class SessionMiddleware(BaseHTTPMiddleware):
    """Validate session on every request"""
    
    async def dispatch(self, request: Request, call_next):
        # Skip validation for public endpoints
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)
        
        # Extract session ID from cookie
        session_id = request.cookies.get("session_id")
        
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No session cookie"
            )
        
        # Load session from Redis
        session_service = request.app.state.session_service
        session = session_service.get_session(session_id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session"
            )
        
        # Verify client fingerprint
        current_fingerprint = session_service._generate_fingerprint(request)
        if current_fingerprint != session["fingerprint"]:
            # Possible session theft!
            session_service.delete_session(session_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session fingerprint mismatch"
            )
        
        # Check for session rotation
        if session_service._should_rotate(session):
            new_session_id = session_service.rotate_session(session_id)
            # New cookie will be set in response
        
        # Update last activity
        session_service.update_activity(session_id)
        
        # Attach session to request state
        request.state.session = session
        
        response = await call_next(request)
        return response
    
    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint requires authentication"""
        public_paths = ["/health", "/auth/web/login", "/auth/web/callback", "/docs"]
        return any(path.startswith(p) for p in public_paths)
```

### Dependency Injection

```python
# src/app/api/http/deps.py
from fastapi import Depends, HTTPException, Request, status

def get_current_session(request: Request) -> dict:
    """Get current session from request state"""
    if not hasattr(request.state, "session"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid session"
        )
    
    return request.state.session

def get_current_user_id(session: dict = Depends(get_current_session)) -> int:
    """Get current user ID from session"""
    return session["user_id"]

def get_current_user_email(session: dict = Depends(get_current_session)) -> str:
    """Get current user email from session"""
    return session["email"]
```

## CSRF Protection

### Double-Submit Cookie Pattern

API Forge uses the **double-submit cookie pattern** with cryptographic signing:

1. **Session Creation**: Generate CSRF token, derive from session ID, set as cookie
2. **Frontend**: Include CSRF token in request header
3. **Backend**: Verify header token matches cookie token

### CSRF Token Generation

```python
def _generate_csrf_token(self, session_id: str) -> str:
    """
    Generate CSRF token bound to session
    
    Token format: {session_id_prefix}.{signature}
    """
    # Read signing secret
    with open(self.config.csrf.signing_secret_file) as f:
        secret = f.read().strip()
    
    # Create signature
    message = f"{session_id}"
    signature = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    # Return token: sess_abc123.signature
    return f"{session_id}.{signature}"

def verify_csrf_token(self, session_id: str, csrf_token: str) -> bool:
    """
    Verify CSRF token matches session
    
    Returns:
        True if valid, False otherwise
    """
    try:
        # Parse token
        token_session_id, signature = csrf_token.split(".", 1)
        
        # Verify session ID matches
        if token_session_id != session_id:
            return False
        
        # Regenerate signature
        expected_token = self._generate_csrf_token(session_id)
        
        # Constant-time comparison
        return hmac.compare_digest(csrf_token, expected_token)
    
    except (ValueError, AttributeError):
        return False
```

### CSRF Validation Middleware

```python
class CSRFMiddleware(BaseHTTPMiddleware):
    """Validate CSRF token on state-changing requests"""
    
    async def dispatch(self, request: Request, call_next):
        # Only check for POST, PUT, PATCH, DELETE
        if request.method in ["GET", "HEAD", "OPTIONS"]:
            return await call_next(request)
        
        # Skip for public endpoints
        if self._is_public_endpoint(request.url.path):
            return await call_next(request)
        
        # Extract CSRF token from header
        csrf_header = request.headers.get("X-CSRF-Token")
        
        if not csrf_header:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing CSRF token"
            )
        
        # Extract CSRF token from cookie
        csrf_cookie = request.cookies.get("csrf_token")
        
        if not csrf_cookie:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing CSRF cookie"
            )
        
        # Verify tokens match
        if not hmac.compare_digest(csrf_header, csrf_cookie):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token mismatch"
            )
        
        # Extract session ID and verify CSRF is bound to session
        session_id = request.cookies.get("session_id")
        session_service = request.app.state.session_service
        
        if not session_service.verify_csrf_token(session_id, csrf_cookie):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF token"
            )
        
        response = await call_next(request)
        return response
```

### Frontend CSRF Usage

```javascript
// React example
async function createOrder(orderData) {
  // Get CSRF token from cookie
  const csrfToken = getCookie('csrf_token');
  
  const response = await fetch('/api/orders', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrfToken,  // Include CSRF token
    },
    body: JSON.stringify(orderData),
    credentials: 'include',  // Send cookies
  });
  
  return response.json();
}

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}
```

## Session Rotation

### Why Rotate Sessions?

Session rotation changes the session ID periodically while keeping session data:

- **Mitigate session fixation** - Attacker can't fix session ID
- **Limit session theft window** - Stolen session expires faster
- **Defense in depth** - Additional security layer

### Rotation Logic

```python
def _should_rotate(self, session: dict) -> bool:
    """Check if session should be rotated"""
    last_rotated = session.get("last_rotated_at", 0)
    rotation_interval = self.config.rotation_interval  # 30 minutes
    
    time_since_rotation = datetime.utcnow().timestamp() - last_rotated
    return time_since_rotation > rotation_interval

def rotate_session(self, old_session_id: str) -> str:
    """
    Rotate session ID while keeping session data
    
    Returns:
        new_session_id
    """
    # Load old session
    session = self.get_session(old_session_id)
    
    if not session:
        raise ValueError("Session not found")
    
    # Generate new session ID
    new_session_id = self._generate_session_id()
    
    # Update session data
    session["session_id"] = new_session_id
    session["last_rotated_at"] = int(datetime.utcnow().timestamp())
    
    # Store under new key
    new_redis_key = f"session:{new_session_id}"
    self.redis.setex(
        new_redis_key,
        timedelta(seconds=self.config.max_age),
        json.dumps(session)
    )
    
    # Delete old session
    old_redis_key = f"session:{old_session_id}"
    self.redis.delete(old_redis_key)
    
    return new_session_id
```

## Session Termination

### Logout Endpoint

```python
# src/app/api/http/routers/auth.py
@router.post("/auth/web/logout")
async def logout(
    response: Response,
    request: Request,
    session_service: SessionService = Depends(get_session_service)
):
    """Logout user and clear session"""
    session_id = request.cookies.get("session_id")
    
    if session_id:
        # Delete session from Redis
        session_service.delete_session(session_id)
    
    # Clear cookies
    response.delete_cookie("session_id", domain=session_service.config.domain)
    response.delete_cookie("csrf_token", domain=session_service.config.domain)
    
    return {"status": "logged_out"}
```

### Timeout Handling

```python
def check_session_timeout(self, session: dict) -> bool:
    """Check if session has timed out due to inactivity"""
    idle_timeout = self.config.idle_timeout  # e.g., 15 minutes
    last_activity = session.get("last_activity_at", 0)
    
    time_since_activity = datetime.utcnow().timestamp() - last_activity
    return time_since_activity > idle_timeout

def update_activity(self, session_id: str):
    """Update last activity timestamp"""
    redis_key = f"session:{session_id}"
    
    # Get current session
    session_json = self.redis.get(redis_key)
    if not session_json:
        return
    
    session = json.loads(session_json)
    session["last_activity_at"] = int(datetime.utcnow().timestamp())
    
    # Update in Redis
    self.redis.setex(
        redis_key,
        timedelta(seconds=self.config.max_age),
        json.dumps(session)
    )
```

## Client Fingerprinting

### Fingerprint Generation

```python
def _generate_fingerprint(self, request: Request) -> str:
    """
    Generate client fingerprint from request headers
    
    Used to detect session theft
    """
    components = [
        # Browser identification
        request.headers.get("user-agent", ""),
        request.headers.get("accept-language", ""),
        request.headers.get("accept-encoding", ""),
        
        # Don't include IP - mobile clients change IPs frequently
        # Don't include cookies - they're what we're protecting
    ]
    
    fingerprint_string = "|".join(components)
    return hashlib.sha256(fingerprint_string.encode()).hexdigest()
```

**Trade-offs**:
- **More components** = More accurate, but breaks on browser updates
- **Fewer components** = More lenient, but less secure
- **Best practice**: Use stable headers (user-agent, accept-language)

### Handling Fingerprint Mismatches

```python
# In session validation middleware
if current_fingerprint != session["fingerprint"]:
    # Log security event
    logger.warning(
        f"Session fingerprint mismatch for session {session_id}: "
        f"expected {session['fingerprint']}, got {current_fingerprint}"
    )
    
    # Option 1: Strict - always reject
    session_service.delete_session(session_id)
    raise HTTPException(401, "Session fingerprint mismatch")
    
    # Option 2: Lenient - allow but require re-authentication for sensitive ops
    request.state.session_suspicious = True
```

## Security Best Practices

### 1. Secret Management

```bash
# Generate strong secrets
python -c "import secrets; print(secrets.token_hex(64))" > session_signing_secret
python -c "import secrets; print(secrets.token_hex(64))" > csrf_signing_secret

# Proper permissions
chmod 400 session_signing_secret csrf_signing_secret
```

### 2. Cookie Domain Configuration

```yaml
# Same domain (most secure)
domain: api.example.com

# Subdomain sharing (less secure, more flexible)
domain: .example.com  # Note the leading dot

# No domain (current host only)
domain: null
```

### 3. Session Expiration Strategy

```yaml
# Short-lived sessions (high security)
max_age: 900           # 15 minutes
rotation_interval: 450  # Rotate every 7.5 minutes

# Standard sessions (balanced)
max_age: 3600          # 1 hour
rotation_interval: 1800 # Rotate every 30 minutes

# Long-lived sessions (convenience)
max_age: 86400         # 24 hours
rotation_interval: 3600 # Rotate every 1 hour
```

### 4. Multi-Device Support

```python
# Allow multiple concurrent sessions per user
def create_session(self, user_id: int, ...):
    # Each device gets its own session_id
    # Store mapping in Redis: user:{user_id}:sessions
    
    user_sessions_key = f"user:{user_id}:sessions"
    self.redis.sadd(user_sessions_key, session_id)
    
def logout_all_devices(self, user_id: int):
    """Logout user from all devices"""
    user_sessions_key = f"user:{user_id}:sessions"
    session_ids = self.redis.smembers(user_sessions_key)
    
    for session_id in session_ids:
        self.delete_session(session_id)
    
    self.redis.delete(user_sessions_key)
```

## Troubleshooting

### Session Not Found

**Symptom**: "Invalid or expired session" errors

**Causes**:
1. Redis down or unreachable
2. Session expired (max_age exceeded)
3. Session manually deleted
4. Redis data loss

**Solutions**:
```bash
# Check Redis connection
docker exec -it api-forge-redis-prod redis-cli --tls PING

# Check session exists
docker exec -it api-forge-redis-prod redis-cli --tls GET "session:sess_abc123"

# Check session TTL
docker exec -it api-forge-redis-prod redis-cli --tls TTL "session:sess_abc123"
```

### CSRF Token Mismatch

**Symptom**: "CSRF token mismatch" or "Missing CSRF token"

**Causes**:
1. Frontend not including CSRF header
2. Cookie domain mismatch
3. SameSite blocking cookie
4. CORS not configured

**Solutions**:
```javascript
// Verify CSRF cookie exists
console.log(document.cookie);

// Check fetch includes credentials
fetch('/api/endpoint', {
  credentials: 'include',  // Required!
  headers: {
    'X-CSRF-Token': getCookie('csrf_token'),
  },
});
```

### Fingerprint Mismatch

**Symptom**: Session invalidated after browser update

**Causes**:
1. Browser updated (user-agent changed)
2. Language settings changed
3. Too strict fingerprinting

**Solutions**:
- Use fewer components in fingerprint
- Make fingerprinting optional (log but don't reject)
- Implement "trusted device" list

## Related Documentation

- [FastAPI Authentication with OIDC](./fastapi-auth-oidc-bff.md) - Full authentication flow
- [FastAPI Production Deployment](./fastapi-production-deployment-docker-compose.md) - Production cookie security
- [FastAPI Testing Strategy](./fastapi-testing-strategy.md) - Testing session functionality

## Additional Resources

- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [MDN Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie)
- [RFC 6265: HTTP State Management (Cookies)](https://tools.ietf.org/html/rfc6265)
- [SameSite Cookie Attribute](https://web.dev/samesite-cookies-explained/)
