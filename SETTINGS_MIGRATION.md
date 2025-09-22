# Settings Refactoring - Migration Guide

## Overview

The settings system has been refactored to separate concerns between:
- **Environment Settings**: Sensitive values that must be configured via environment variables
- **Application Config**: Complex objects and business logic configuration that belong in code

## What Changed

### Before (Old Structure)
```python
from src.runtime.settings import settings

# Everything was in one Settings class
settings.allowed_algorithms  # From environment variable
settings.cors_origins        # From environment variable  
settings.rate_limit_requests # From environment variable
settings.oidc_providers      # Complex parsing from JSON string
```

### After (New Structure)
```python
from src.runtime.settings import settings

# Same interface, but cleaner implementation
settings.allowed_algorithms  # From ApplicationConfig (code)
settings.cors_origins        # From ApplicationConfig (code)
settings.rate_limit_requests # From ApplicationConfig (code)
settings.oidc_providers      # Smart merging of defaults + env credentials
```

## File Structure

### `/src/runtime/config.py` (NEW)
- **ApplicationConfig**: Business logic settings that don't belong in environment variables
- **Default OIDC Providers**: Pre-configured providers (Google, Microsoft)
- **Environment-specific overrides**: Different settings for dev/test/prod

### `/src/runtime/settings.py` (REFACTORED)
- **EnvironmentSettings**: Only sensitive values from environment variables
- **Unified Settings Interface**: Backward-compatible API

## Migration Required

### Environment Variables

**REMOVED** (now in code):
```bash
# These are no longer needed in .env - they're in ApplicationConfig
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
JWT_AUDIENCES=api://default
JWT_ALLOWED_ALGOS=RS256,RS512,ES256,ES384
```

**NEW** (simplified OIDC config):
```bash
# Instead of complex JSON, use simple key-value pairs
OIDC_GOOGLE_CLIENT_ID=your-google-client-id
OIDC_GOOGLE_CLIENT_SECRET=your-google-client-secret
OIDC_MICROSOFT_CLIENT_ID=your-microsoft-client-id
OIDC_MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret
```

**REQUIRED** (new):
```bash
BASE_URL=http://localhost:8000  # Used for OIDC redirect URIs
```

## Benefits

### 1. **Cleaner Environment Variables**
- Only sensitive values in .env
- No more complex JSON parsing from environment variables
- Clear separation between secrets and configuration

### 2. **Better OIDC Configuration**
- Built-in provider defaults (Google, Microsoft)
- Simple credential configuration via environment variables
- Automatic redirect URI generation

### 3. **Environment-Specific Configuration**
```python
# Different settings per environment
if env == "production":
    config.session.secure_cookies = True
    config.cors.origins = []  # Must be explicitly configured

elif env == "development": 
    config.rate_limit.enabled = False
```

### 4. **Type Safety**
- Proper Pydantic models for complex configuration
- Validation at application startup
- Better IDE support and documentation

## Code Changes Required

### None for Basic Usage
```python
# This still works exactly the same
from src.runtime.settings import settings

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
)
```

### For Advanced Configuration
```python
# Access the new config objects if needed
from src.runtime.config import app_config
from src.runtime.settings import env_settings

# Customize application config
app_config.rate_limit.requests = 200
app_config.cors.origins.append("https://mydomain.com")

# Access environment settings directly
database_url = env_settings.database_url
```

## Testing

### Before
```python
from src.runtime.settings import Settings
settings = Settings()
```

### After  
```python
from src.runtime.settings import EnvironmentSettings
env_settings = EnvironmentSettings()
```

## Deployment Guide

### Development
```bash
# Minimal .env file
ENVIRONMENT=development
SECRET_KEY=dev-secret-key
OIDC_GOOGLE_CLIENT_ID=your-dev-google-client-id
```

### Production
```bash
# Production .env file
ENVIRONMENT=production
DATABASE_URL=postgresql://user:pass@prod-db:5432/app
REDIS_URL=rediss://prod-redis:6379/0
BASE_URL=https://api.yourdomain.com
SECRET_KEY=your-256-bit-production-secret
JWT_SECRET=your-jwt-secret
JWT_ISSUER_JWKS_MAP={"https://your-auth.com/":"https://your-auth.com/.well-known/jwks.json"}
OIDC_GOOGLE_CLIENT_ID=your-prod-google-client-id
OIDC_GOOGLE_CLIENT_SECRET=your-prod-google-client-secret
```

## Rollback Plan

If issues arise, you can temporarily restore the old behavior by:

1. Keeping both config files
2. Updating imports to use the old Settings class directly
3. Reverting the .env file structure

The refactoring maintains backward compatibility at the API level, so existing code should continue to work.