# 🚀 FastAPI Production Template

A comprehensive, production-ready FastAPI template with built-in authentication, development tools, and modern Python architecture patterns.

## 📋 Overview

This template provides a complete foundation for building scalable FastAPI applications with:

- **🔐 Built-in OIDC Authentication** - Complete auth flow with session management
- **🏗️ Clean Architecture** - Organized entity/service layer with clear separation of concerns
- **⚡ Complete Development Environment** - Integrated Keycloak, PostgreSQL, Redis, and Temporal via Docker
- **🔄 Template Updates** - Automatic updates using Cruft
- **🗄️ Flexible Database Support** - PostgreSQL for production, SQLite for development/testing
- **🧪 Comprehensive Testing** - Unit, integration, and fixture-based testing
- **📊 Entity Modeling** - SQLModel for type-safe ORM with Pydantic integration
- **🛠️ Development CLI** - Rich command-line tools for development workflow

## 🎯 Key Features

### Authentication & Security
- **Backend-for-Frontend (BFF) Pattern** with secure session management
- **OpenID Connect (OIDC)** integration with multiple providers (Google, Microsoft, Keycloak)
- **PKCE + Nonce protection** for authorization code flow
- **CSRF protection** with token validation for state-changing operations
- **Origin validation** and secure cookie handling
- **JWT token validation** with JWKS caching and refresh mechanisms
- **Client fingerprinting** for session binding and security
- **Rate limiting** with Redis backend
- **CORS and security headers** configured for production

### Development Experience  
- **Complete development stack** with Docker Compose (Keycloak, PostgreSQL, Redis, Temporal)
- **Automatic service configuration** - Zero manual setup required
- **Keycloak integration** with pre-configured test realm and users
- **PostgreSQL** database with migration support
- **Redis** for caching and rate limiting
- **Temporal** for workflow orchestration and background tasks
- **Hot reload** development server with uvicorn
- **Rich CLI** with entity management and dev environment commands
- **Structured logging** with request tracing

### Architecture & Code Quality
- **Clean architecture** with entities, services, and API layers
- **Type safety** throughout with Pydantic and SQLModel
- **Dependency injection** patterns for testability  
- **Comprehensive testing** with pytest and fixtures
- **Code formatting** and linting with Ruff
- **Type checking** with MyPy

### Database & Storage
- **SQLModel ORM** for type-safe database operations
- **PostgreSQL** support for production environments
- **SQLite** for development and testing
- **Database migrations** and initialization scripts
- **Repository patterns** for data access abstraction

## 🛠️ Requirements

- **Python 3.13+**
- **Docker & Docker Compose** (for development environment)
- **uv** (recommended) or pip for package management

## 🚀 Quick Start

### 1. Create New Project from Template

Using Cruft (recommended for updates):

```bash
# Install cruft
pip install cruft

# Create project from template
cruft create https://github.com/piewared/api_project_template

# Follow the prompts to configure your project
```

Using Cookiecutter:

```bash
# Install cookiecutter  
pip install cookiecutter

# Create project from template
cookiecutter https://github.com/piewared/api_project_template
```

### 2. Set Up Development Environment

```bash
# Navigate to your new project
cd your-project-name

# Copy environment template
cp .env.example .env

# Edit .env with your configuration
nano .env

# Start development environment (Keycloak, PostgreSQL, Redis, Temporal)
uv run cli dev start-env

# Initialize database
uv run init-db

# Start development server
uv run cli dev start-server
```

Your API will be available at:
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (interactive documentation)
- **Keycloak Admin**: http://localhost:8080 (admin/admin)
- **Temporal UI**: http://localhost:8081 (workflow management)

### 3. Test Authentication

```bash
# Visit the login endpoint to start OIDC flow
curl -v http://localhost:8000/auth/web/login

# Or test with browser:
# 1. Go to http://localhost:8000/auth/web/login
# 2. Login with test credentials (if using Keycloak): testuser1 / password123
# 3. You'll be redirected back with secure session cookie
# 4. Check your auth state: http://localhost:8000/auth/web/me
```


## 💡 Building Your Service

Projects generated from this template are production-ready and fully deployable—except you haven't written any services yet!
To implement your service, you'll define entities, business logic, and API routes specific to your domain. To accelerate your development,
the generated project includes a complete development environment with self-hosted instances of PostgreSQL, Temporal.io, Redis, and Keycloak 
that mirror production conditions. This means you can build, test, and iterate on production-ready services from day one, with zero infrastructure setup.

**What you get out of the box:**
- 🔐 **Authentication ready** - OIDC flow with session management  
- 🗄️ **Database ready** - PostgreSQL with migrations and connection pooling
- ⚡ **Caching ready** - Redis for sessions, rate limiting, and application cache
- 🔄 **Workflows ready** - Temporal for background tasks and complex business processes
- 🛠️ **Development tools** - Rich CLI, hot reload, structured logging, and monitoring

### 1. Create Entities Using the CLI

The fastest way to create domain entities is using the built-in CLI tool. It automatically generates all necessary files with proper structure:

```bash
# Create a new entity with interactive field definition
uv run cli entity add Product

# The CLI will prompt you for each field:
# Field name (): name
# Type for 'name' [str/int/float/bool/datetime] (str): str
# Is 'name' optional? [y/n] (n): n
# Description for 'name' (Name): Product name
# Field name (): price
# Type for 'price' [str/int/float/bool/datetime] (str): float
# Is 'price' optional? [y/n] (n): n
# Description for 'price' (Price): Product price
# Field name (): (press Enter to finish)
```

**What gets generated automatically:**
- ✅ **Domain Entity** (`src/app/entities/service/product/entity.py`) - Business logic and validation
- ✅ **Database Table** (`src/app/entities/service/product/table.py`) - SQLModel table definition  
- ✅ **Repository** (`src/app/entities/service/product/repository.py`) - Data access layer with CRUD operations
- ✅ **Package Init** (`src/app/entities/service/product/__init__.py`) - Proper exports
- ✅ **API Router** (`src/app/api/http/routers/service/product.py`) - Complete CRUD endpoints
- ✅ **FastAPI Registration** - Automatically registered with the main FastAPI app

**Example generated entity structure:**
```python
# Generated entity.py
class Product(Entity):
    """Product entity representing a product in the system."""
    
    name: str = Field(description="Product name")
    price: float = Field(description="Product price")
    
    def __eq__(self, other: Any) -> bool:
        """Compare products by business attributes."""
        # Auto-generated comparison logic
    
    def __hash__(self) -> int:
        """Hash based on business attributes."""
        # Auto-generated hashing logic
```

**Generated API endpoints (automatically available):**
- `POST /api/v1/products/` - Create product
- `GET /api/v1/products/` - List all products  
- `GET /api/v1/products/{id}` - Get product by ID
- `PUT /api/v1/products/{id}` - Update product
- `DELETE /api/v1/products/{id}` - Delete product

### 2. Manage Entities

```bash
# List all entities in your project
uv run cli entity ls

# Remove an entity (with confirmation)
uv run cli entity rm Product

# Remove an entity without confirmation
uv run cli entity rm Product --force
```

### 3. Customize Generated Code

After generating entities with the CLI, you can customize the generated code for your specific business requirements:

**Add business logic to your entity:**
```python
# Edit src/app/entities/service/product/entity.py
class Product(Entity):
    name: str = Field(description="Product name")
    price: float = Field(description="Product price")
    stock_quantity: int = Field(default=0, description="Available stock")
    
    def is_in_stock(self) -> bool:
        """Custom business logic - check if product is in stock."""
        return self.stock_quantity > 0
    
    def can_fulfill_order(self, quantity: int) -> bool:
        """Custom business logic - check if we can fulfill an order."""
        return self.stock_quantity >= quantity
```

**Add custom repository methods:**
```python
# Edit src/app/entities/service/product/repository.py
class ProductRepository:
    # ... generated CRUD methods ...
    
    def find_by_category(self, category: str) -> list[Product]:
        """Custom query - find products by category."""
        statement = select(ProductTable).where(ProductTable.category == category)
        rows = self._session.exec(statement).all()
        return [Product.model_validate(row, from_attributes=True) for row in rows]
    
    def find_low_stock(self, threshold: int = 10) -> list[Product]:
        """Custom query - find products with low stock."""
        statement = select(ProductTable).where(ProductTable.stock_quantity < threshold)
        rows = self._session.exec(statement).all()
        return [Product.model_validate(row, from_attributes=True) for row in rows]
```

**Add custom API endpoints:**
```python
# Edit src/app/api/http/routers/service/product.py
# Add custom endpoints to the generated router

@router.get("/category/{category}", response_model=list[Product])
def get_products_by_category(
    category: str,
    session: Session = Depends(get_session),
) -> list[Product]:
    """Get products by category."""
    repository = ProductRepository(session)
    return repository.find_by_category(category)

@router.get("/low-stock", response_model=list[Product])  
def get_low_stock_products(
    threshold: int = 10,
    session: Session = Depends(get_session),
) -> list[Product]:
    """Get products with low stock."""
    repository = ProductRepository(session)
    return repository.find_low_stock(threshold)
```

## 🏗️ Built-in Development Environment

The template includes a fully integrated development environment with Docker Compose, providing all necessary services for local development and testing.

### Services Included

- **🔐 Keycloak** - OIDC authentication server with pre-configured test realm
- **🗄️ PostgreSQL** - Production-grade database with development data
- **⚡ Redis** - Caching and rate limiting backend  
- **⏰ Temporal** - Workflow orchestration engine with UI
- **🔧 Development Tools** - Database initialization, health checks, and monitoring

### Quick Start

```bash
# Start all development services
uv run cli dev start-env

# Check service status
uv run cli dev status

# View service logs
uv run cli dev logs

# Start your API server
uv run cli dev start-server
```

### Service Details

#### Keycloak (Authentication) - Port 8080
- **Admin Console**: http://localhost:8080
- **Credentials**: admin/admin
- **Test Realm**: `test-realm` (auto-configured)
- **Test Users**: `testuser1` and `testuser2` (password: `password123`)
- **Client ID**: `test-client`
- **Client Secret**: `test-client-secret`

The Keycloak setup runs automatically when services start, creating:
- OIDC provider configuration
- Test client for your application
- Test users for development
- All necessary endpoints for authentication flows

#### PostgreSQL (Database) - Port 5432
- **Connection**: `postgresql://devuser:devpass@localhost:5432/app_db`
- **Admin User**: `devuser` / `devpass`
- **Database**: `app_db`
- **Persistent Data**: Stored in Docker volume

#### Redis (Cache/Sessions) - Port 6379
- **Connection**: `redis://localhost:6379`
- **Used For**: Rate limiting, session storage, caching
- **Persistent Data**: Stored in Docker volume

#### Temporal (Workflows) - Ports 7233, 8081
- **Server**: http://localhost:7233
- **Web UI**: http://localhost:8081
- **Used For**: Background tasks, workflow orchestration
- **Namespace**: `default`

### Environment Variables

Copy `.env.example` to `.env` and configure for your environment:

```bash
# Environment Configuration
ENVIRONMENT=development                    # development, production, test

# Database Configuration
DATABASE_URL=sqlite:///./database.db      # SQLite for development
# DATABASE_URL=postgresql://user:password@localhost:5432/your_db  # PostgreSQL for production

# Infrastructure URLs
REDIS_URL=redis://localhost:6379/0        # Redis for sessions and rate limiting
TEMPORAL_URL=localhost:7233                # Temporal workflow engine
BASE_URL=http://localhost:8000             # Your application's base URL

### OIDC Authentication Configuration ###

# Global OIDC redirect URI (used by all providers unless overridden)
OIDC_REDIRECT_URI=http://localhost:8000/auth/web/callback

# Google OIDC Provider (optional)
OIDC_GOOGLE_CLIENT_ID=your-google-client-id
OIDC_GOOGLE_CLIENT_SECRET=your-google-client-secret

# Microsoft OIDC Provider (optional)
OIDC_MICROSOFT_CLIENT_ID=your-microsoft-client-id
OIDC_MICROSOFT_CLIENT_SECRET=your-microsoft-client-secret

# Keycloak OIDC Provider (recommended for development)
OIDC_KEYCLOAK_CLIENT_ID=your-keycloak-client-id
OIDC_KEYCLOAK_CLIENT_SECRET=your-keycloak-client-secret
OIDC_KEYCLOAK_ISSUER=http://localhost:8080/realms/test-realm

### JWT & Session Configuration ###

# JWT token validation
JWT_AUDIENCE=api://default                 # Primary audience for JWT tokens
JWT_AUDIENCE_SECONDARY=http://localhost:8000  # Secondary audience (optional)

# Session management
SESSION_JWT_SECRET=your-session-jwt-secret-CHANGE_ME!  # HMAC secret for session tokens
SESSION_MAX_AGE=3600                       # Session duration in seconds (1 hour)

# CORS configuration
CLIENT_ORIGIN=http://localhost:3000        # Allowed origin for web clients

### JWT Claims Mapping (Optional) ###
# Customize how user data is extracted from JWT tokens
# JWT_CLAIM_USER_ID=sub                   # User ID claim (default: sub)
# JWT_CLAIM_EMAIL=email                   # Email claim (default: email)
# JWT_CLAIM_ROLES=roles                   # Roles claim (default: roles)
# JWT_CLAIM_GROUPS=groups                 # Groups claim (default: groups)
# JWT_CLAIM_SCOPE=scope                   # Scope claim (default: scope)
# JWT_CLAIM_NAME=name                     # Full name claim (default: name)
# JWT_CLAIM_USERNAME=preferred_username   # Username claim (default: preferred_username)
```

**Security Notes:**
- Change `SESSION_JWT_SECRET` to a strong, random value (minimum 32 characters)
- In production, use HTTPS URLs for `BASE_URL` and `OIDC_REDIRECT_URI`
- Configure `CLIENT_ORIGIN` to match your frontend application's URL
- Set `ENVIRONMENT=production` for production deployments

### Configuration File (config.yaml)

The application uses a YAML configuration file (`config.yaml`) for structured configuration management. This file defines all application settings with environment variable substitution support.

#### Configuration Structure

```yaml
config:
  # Rate limiting settings
  rate_limiter:
    requests: 10                    # Max requests per window
    window_ms: 5000                # Time window in milliseconds
    enabled: true                  # Enable/disable rate limiting
    per_endpoint: true            # Apply per endpoint
    per_method: true              # Apply per HTTP method

  # Database configuration
  database:
    url: "${DATABASE_URL:-postgresql+asyncpg://user:password@postgres:5432/app_db}"
    pool_size: 20                 # Connection pool size
    max_overflow: 10              # Pool overflow limit
    pool_timeout: 30              # Connection timeout
    pool_recycle: 1800            # Connection recycle time

  # Temporal workflow engine
  temporal:
    enabled: true
    url: "${TEMPORAL_ADDRESS:-temporal:7233}"
    namespace: "default"
    task_queue: "default"
    worker:
      enabled: true
      activities_per_second: 10
      max_concurrent_activities: 100

  # Redis cache/session store
  redis:
    enabled: true
    url: "${REDIS_URL:-redis://localhost:6379}"

  # OIDC Authentication providers
  oidc:
    providers:
      google:
        client_id: "${OIDC_GOOGLE_CLIENT_ID}"
        client_secret: "${OIDC_GOOGLE_CLIENT_SECRET}"
        issuer: "https://accounts.google.com"
        authorization_endpoint: "https://accounts.google.com/o/oauth2/v2/auth"
        token_endpoint: "https://oauth2.googleapis.com/token"
        userinfo_endpoint: "https://openidconnect.googleapis.com/v1/userinfo"
        end_session_endpoint: "https://accounts.google.com/logout"
        scopes: ["openid", "email", "profile"]
      microsoft:
        client_id: "${OIDC_MICROSOFT_CLIENT_ID}"
        client_secret: "${OIDC_MICROSOFT_CLIENT_SECRET}"
        issuer: "https://login.microsoftonline.com/common/v2.0"
        authorization_endpoint: "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
        token_endpoint: "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        userinfo_endpoint: "https://graph.microsoft.com/oidc/userinfo"
        end_session_endpoint: "https://login.microsoftonline.com/common/oauth2/v2.0/logout"
        scopes: ["openid", "email", "profile"]
      keycloak:
        client_id: "${OIDC_KEYCLOAK_CLIENT_ID}"
        client_secret: "${OIDC_KEYCLOAK_CLIENT_SECRET}"
        issuer: "${OIDC_KEYCLOAK_ISSUER:-http://localhost:8080/realms/test-realm}"
        # Endpoints auto-discovered from issuer/.well-known/openid_configuration
        scopes: ["openid", "email", "profile"]
    default_provider: "keycloak"
    global_redirect_uri: "${OIDC_REDIRECT_URI:-http://localhost:8000/auth/web/callback}"

  # JWT token validation
  jwt:
    allowed_algorithms: ["RS256", "RS512", "ES256", "ES384"]
    audiences: ["${JWT_AUDIENCE:-api://default}", "${JWT_AUDIENCE_SECONDARY}"]
    claims:
      user_id: "${JWT_CLAIM_USER_ID:-sub}"
      email: "${JWT_CLAIM_EMAIL:-email}"
      roles: "${JWT_CLAIM_ROLES:-roles}"
      groups: "${JWT_CLAIM_GROUPS:-groups}"
      scope: "${JWT_CLAIM_SCOPE:-scope}"
      name: "${JWT_CLAIM_NAME:-name}"
      username: "${JWT_CLAIM_USERNAME:-preferred_username}"

  # Application settings
  app:
    environment: "${APP_ENVIRONMENT:-development}"
    host: "${APP_HOST:-localhost}"
    port: "${APP_PORT:-8000}"
    base_url: "${BASE_URL:-http://localhost:8000}"
    session_max_age: ${SESSION_MAX_AGE:-3600}
    session_jwt_secret: "${SESSION_JWT_SECRET}"
    cors:
      origins: ["${CLIENT_ORIGIN:-http://localhost:3000}"]
    environment: "${APP_ENVIRONMENT:-development}"
    host: "${APP_HOST:-localhost}"
    port: "${APP_PORT:-8000}"
    session_max_age: ${SESSION_MAX_AGE:-3600}
    session_jwt_secret: "${SESSION_JWT_SECRET}"
```

#### Environment Variable Substitution

The config.yaml file supports environment variable substitution using the `${VAR_NAME:-default_value}` syntax:

- **`${DATABASE_URL}`** - Uses the DATABASE_URL environment variable
- **`${DATABASE_URL:-default}`** - Uses DATABASE_URL or falls back to "default" if not set
- **Nested substitution** - Environment variables can be used throughout the configuration

#### Key Configuration Sections

**Rate Limiter**: Controls API request throttling per endpoint/method
**Database**: PostgreSQL connection settings with pooling configuration
**Temporal**: Workflow engine settings for background tasks
**Redis**: Cache and session storage configuration
**OIDC**: Multi-provider authentication setup (Google, Microsoft, Keycloak)
**JWT**: Token validation rules and claim mappings
**Logging**: Structured logging with file rotation
**CORS**: Cross-origin request settings for web frontends

#### Modifying Configuration

1. **Environment-specific values**: Set environment variables in `.env` file
2. **Structural changes**: Edit `config.yaml` directly for new settings
3. **Provider setup**: Add new OIDC providers in the `oidc.providers` section
4. **Development vs Production**: Use environment variables to override defaults

## 🚀 CLI Commands Reference

### Development Environment Commands

```bash
# Start all services (Keycloak, PostgreSQL, Redis, Temporal)
uv run cli dev start-env

# Start services with options
uv run cli dev start-env --force        # Force restart even if running
uv run cli dev start-env --no-wait      # Don't wait for services to be ready

# Check status of all services
uv run cli dev status

# Stop all development services
uv run cli dev stop

# View logs from all services
uv run cli dev logs
```

### Development Server Commands

```bash
# Start FastAPI development server
uv run cli dev start-server

# Start server with custom options
uv run cli dev start-server --host 0.0.0.0 --port 8080
uv run cli dev start-server --no-reload          # Disable auto-reload
uv run cli dev start-server --log-level debug    # Set log level
```

### Entity Management Commands

```bash
# Create a new entity (interactive field definition)
uv run cli entity add Product

# Remove an entity and all its files
uv run cli entity rm Product

# List all entities in the project
uv run cli entity ls
```

The entity commands will:
- Generate all necessary files (table, repository, router, __init__.py)
- Register routes automatically with your FastAPI app
- Follow the project's patterns and conventions
- Handle field types, relationships, and validation

## 🔐 Authentication API

The template provides a secure Backend-for-Frontend (BFF) authentication system with comprehensive security features including CSRF protection, origin validation, and secure session management.

### Authentication Endpoints

All authentication endpoints are under the `/auth/web` prefix and designed for web clients using session cookies.

#### `GET /auth/web/login`

Initiates the OIDC authentication flow with enhanced security.

**Query Parameters:**
- `provider` (optional): OIDC provider to use (default: configured default provider)
- `return_to` (optional): URL to redirect to after successful authentication

**Security Features:**
- PKCE (Proof Key for Code Exchange) for authorization code flow
- Cryptographic nonce for ID token binding
- State parameter for CSRF protection
- Client fingerprinting for session binding
- Secure temporary session cookie for auth flow

**Example:**
```bash
# Start login with default provider
curl -v http://localhost:8000/auth/web/login

# Start login with specific provider and return URL
curl -v "http://localhost:8000/auth/web/login?provider=google&return_to=/dashboard"
```

#### `GET /auth/web/callback`

Handles the OIDC provider callback with comprehensive security validation.

**Query Parameters:**
- `code`: Authorization code from OIDC provider
- `state`: State parameter for validation
- `error` (optional): Error from OIDC provider

**Security Validation:**
- State parameter validation (CSRF protection)
- Client fingerprint validation
- PKCE code verifier validation
- ID token signature and nonce verification
- Single-use auth session enforcement

**Response:**
- Redirects to original `return_to` URL or `/`
- Sets secure `user_session_id` cookie
- Clears temporary auth session cookie

#### `POST /auth/web/logout`

Securely logs out the user with CSRF and origin protection.

**Security Requirements:**
- `X-CSRF-Token` header with valid CSRF token
- Origin header validation
- Valid session cookie

**Response:**
```json
{
  "message": "Logged out",
  "provider_logout_url": "https://provider.com/logout?..." // Optional
}
```

**Example:**
```bash
# Get CSRF token first
CSRF_TOKEN=$(curl -s -b cookies.txt http://localhost:8000/auth/web/me | jq -r '.csrf_token')

# Logout with CSRF protection
curl -X POST \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Origin: http://localhost:8000" \
  -b cookies.txt \
  http://localhost:8000/auth/web/logout
```

#### `GET /auth/web/me`

Returns current authentication state and CSRF token for authenticated users.

**Response (Authenticated):**
```json
{
  "authenticated": true,
  "user": {
    "id": "user-uuid",
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "csrf_token": "secure-csrf-token"
}
```

**Response (Unauthenticated):**
```json
{
  "authenticated": false
}
```

**Example:**
```bash
# Check auth state
curl -b cookies.txt http://localhost:8000/auth/web/me
```

#### `POST /auth/web/refresh`

Refreshes the user session with token rotation and CSRF protection.

**Security Requirements:**
- `X-CSRF-Token` header with valid CSRF token
- Origin header validation
- Valid session cookie
- Client fingerprint validation

**Response:**
```json
{
  "message": "Session refreshed",
  "csrf_token": "new-csrf-token"
}
```

**Features:**
- Session ID rotation for security
- CSRF token rotation
- Access token refresh via OIDC provider
- Client fingerprint re-validation

**Example:**
```bash
# Refresh session with CSRF protection
CSRF_TOKEN=$(curl -s -b cookies.txt http://localhost:8000/auth/web/me | jq -r '.csrf_token')

curl -X POST \
  -H "X-CSRF-Token: $CSRF_TOKEN" \
  -H "Origin: http://localhost:8000" \
  -b cookies.txt \
  http://localhost:8000/auth/web/refresh
```

### Security Features

#### CSRF Protection
All state-changing operations require CSRF tokens obtained from `/auth/web/me` and passed in the `X-CSRF-Token` header.

#### Origin Validation
POST/PUT/PATCH/DELETE requests validate the `Origin` header against configured allowed origins.

#### Session Security
- HttpOnly, Secure, SameSite=Lax cookies
- Client fingerprinting for session binding
- Automatic session expiration and cleanup
- Session ID rotation on refresh

#### OIDC Security
- PKCE for authorization code flow
- Nonce validation in ID tokens
- State parameter for CSRF protection
- Comprehensive token validation

## 📱 Client Integration Examples

### TypeScript/JavaScript Client

```typescript
class AuthClient {
  private csrfToken: string | null = null;
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  // Check authentication state and get CSRF token
  async checkAuthState(): Promise<{authenticated: boolean, user?: any}> {
    try {
      const response = await fetch(`${this.baseUrl}/auth/web/me`, {
        credentials: 'include', // Include session cookies
      });
      
      if (!response.ok) {
        throw new Error('Failed to check auth state');
      }
      
      const data = await response.json();
      
      // Store CSRF token for future requests
      if (data.csrf_token) {
        this.csrfToken = data.csrf_token;
      }
      
      return data;
    } catch (error) {
      console.error('Auth state check failed:', error);
      return { authenticated: false };
    }
  }

  // Initiate login flow
  async login(provider: string = 'default', returnTo?: string): Promise<void> {
    const params = new URLSearchParams();
    if (provider !== 'default') params.set('provider', provider);
    if (returnTo) params.set('return_to', returnTo);
    
    const queryString = params.toString();
    const loginUrl = `${this.baseUrl}/auth/web/login${queryString ? '?' + queryString : ''}`;
    
    // Redirect to login (browser will handle the flow)
    window.location.href = loginUrl;
  }

  // Make authenticated API request with CSRF protection
  async authenticatedRequest(url: string, options: RequestInit = {}): Promise<Response> {
    // Ensure we have a fresh CSRF token
    if (!this.csrfToken) {
      await this.checkAuthState();
    }
    
    const headers = new Headers(options.headers);
    
    // Add CSRF token for state-changing requests
    if (options.method && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method.toUpperCase())) {
      if (this.csrfToken) {
        headers.set('X-CSRF-Token', this.csrfToken);
      }
      // Add origin header for CSRF protection
      headers.set('Origin', window.location.origin);
    }
    
    const response = await fetch(url, {
      ...options,
      headers,
      credentials: 'include', // Include session cookies
    });
    
    // Handle CSRF token expiry
    if (response.status === 403 && response.headers.get('content-type')?.includes('json')) {
      const errorData = await response.clone().json();
      if (errorData.detail?.includes('CSRF')) {
        // Refresh CSRF token and retry
        await this.checkAuthState();
        headers.set('X-CSRF-Token', this.csrfToken!);
        return fetch(url, { ...options, headers, credentials: 'include' });
      }
    }
    
    return response;
  }

  // Refresh session
  async refreshSession(): Promise<boolean> {
    try {
      const response = await this.authenticatedRequest(`${this.baseUrl}/auth/web/refresh`, {
        method: 'POST',
      });
      
      if (response.ok) {
        const data = await response.json();
        this.csrfToken = data.csrf_token; // Update CSRF token
        return true;
      }
      return false;
    } catch (error) {
      console.error('Session refresh failed:', error);
      return false;
    }
  }

  // Logout
  async logout(): Promise<boolean> {
    try {
      const response = await this.authenticatedRequest(`${this.baseUrl}/auth/web/logout`, {
        method: 'POST',
      });
      
      if (response.ok) {
        this.csrfToken = null;
        const data = await response.json();
        
        // If provider logout URL is provided, redirect to it
        if (data.provider_logout_url) {
          window.location.href = data.provider_logout_url;
        }
        
        return true;
      }
      return false;
    } catch (error) {
      console.error('Logout failed:', error);
      return false;
    }
  }
}

// Usage example
const authClient = new AuthClient();

// Check if user is logged in
const authState = await authClient.checkAuthState();
if (authState.authenticated) {
  console.log('User is logged in:', authState.user);
  
  // Make authenticated API requests
  const response = await authClient.authenticatedRequest('/api/v1/some-protected-endpoint', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data: 'example' }),
  });
  
} else {
  // Start login flow
  await authClient.login('google', '/dashboard');
}
```

### Python Client

```python
import requests
from typing import Optional, Dict, Any
from urllib.parse import urlencode

class AuthClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()  # Maintains cookies automatically
        self.csrf_token: Optional[str] = None
    
    def check_auth_state(self) -> Dict[str, Any]:
        """Check authentication state and get CSRF token."""
        try:
            response = self.session.get(f"{self.base_url}/auth/web/me")
            response.raise_for_status()
            
            data = response.json()
            
            # Store CSRF token for future requests
            if data.get('csrf_token'):
                self.csrf_token = data['csrf_token']
            
            return data
        except requests.RequestException as e:
            print(f"Auth state check failed: {e}")
            return {"authenticated": False}
    
    def login_url(self, provider: str = "default", return_to: Optional[str] = None) -> str:
        """Generate login URL for manual redirection."""
        params = {}
        if provider != "default":
            params["provider"] = provider
        if return_to:
            params["return_to"] = return_to
        
        query_string = urlencode(params) if params else ""
        return f"{self.base_url}/auth/web/login{f'?{query_string}' if query_string else ''}"
    
    def authenticated_request(self, url: str, method: str = "GET", **kwargs) -> requests.Response:
        """Make authenticated request with CSRF protection."""
        # Ensure we have a fresh CSRF token
        if not self.csrf_token:
            self.check_auth_state()
        
        headers = kwargs.get('headers', {})
        
        # Add CSRF token for state-changing requests
        if method.upper() in ['POST', 'PUT', 'PATCH', 'DELETE']:
            if self.csrf_token:
                headers['X-CSRF-Token'] = self.csrf_token
            # Add origin header for CSRF protection
            headers['Origin'] = self.base_url
        
        kwargs['headers'] = headers
        
        response = self.session.request(method, url, **kwargs)
        
        # Handle CSRF token expiry
        if response.status_code == 403:
            try:
                error_data = response.json()
                if 'CSRF' in error_data.get('detail', ''):
                    # Refresh CSRF token and retry
                    self.check_auth_state()
                    headers['X-CSRF-Token'] = self.csrf_token
                    kwargs['headers'] = headers
                    response = self.session.request(method, url, **kwargs)
            except Exception:
                pass  # Not JSON response, continue with original response
        
        return response
    
    def refresh_session(self) -> bool:
        """Refresh session and get new CSRF token."""
        try:
            response = self.authenticated_request(
                f"{self.base_url}/auth/web/refresh", 
                method="POST"
            )
            
            if response.ok:
                data = response.json()
                self.csrf_token = data.get('csrf_token')  # Update CSRF token
                return True
            return False
        except requests.RequestException as e:
            print(f"Session refresh failed: {e}")
            return False
    
    def logout(self) -> bool:
        """Logout user and clear session."""
        try:
            response = self.authenticated_request(
                f"{self.base_url}/auth/web/logout", 
                method="POST"
            )
            
            if response.ok:
                self.csrf_token = None
                data = response.json()
                
                print(f"Logout successful: {data.get('message')}")
                if data.get('provider_logout_url'):
                    print(f"Complete logout at: {data['provider_logout_url']}")
                
                return True
            return False
        except requests.RequestException as e:
            print(f"Logout failed: {e}")
            return False

# Usage example
if __name__ == "__main__":
    client = AuthClient()
    
    # Check authentication state
    auth_state = client.check_auth_state()
    if auth_state["authenticated"]:
        print(f"User is logged in: {auth_state['user']}")
        
        # Make authenticated API requests
        response = client.authenticated_request(
            "http://localhost:8000/api/v1/some-protected-endpoint",
            method="POST",
            json={"data": "example"},
            headers={"Content-Type": "application/json"}
        )
        
        if response.ok:
            print("API request successful:", response.json())
        else:
            print(f"API request failed: {response.status_code}")
        
        # Refresh session
        if client.refresh_session():
            print("Session refreshed successfully")
        
        # Logout
        if client.logout():
            print("Logged out successfully")
    
    else:
        print("User not logged in")
        print(f"Login at: {client.login_url('google', '/dashboard')}")
```

## 🧪 Testing

The template includes comprehensive testing setup:

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=your_package

# Run specific test types
uv run pytest tests/unit/           # Unit tests only
uv run pytest tests/integration/    # Integration tests only
uv run pytest tests/e2e/           # End-to-end tests only
```

### Test Structure
- **Unit Tests**: Fast, isolated tests for business logic
- **Integration Tests**: Test database operations and external service integration
- **E2E Tests**: Full application workflow tests with authentication
- **Fixtures**: Shared test data and setup in `tests/fixtures/`

## 🛠️ Development Workflow

### Local Development
1. **Start Environment**: `uv run cli dev start-env`
2. **Verify Services**: `uv run cli dev status`
3. **Start Server**: `uv run cli dev start-server`
4. **Access Services**:
   - **API**: http://localhost:8000
   - **API Docs**: http://localhost:8000/docs
   - **Keycloak Admin**: http://localhost:8080
   - **Temporal UI**: http://localhost:8081

### Adding New Features
1. **Create Entity**: `uv run cli entity add EntityName`
2. **Implement Business Logic**: Add methods to repository
3. **Write Tests**: Create unit and integration tests
4. **Update Documentation**: Document new endpoints

### Debugging
```bash
# Check service logs
uv run cli dev logs

# Database inspection
uv run cli dev logs postgres

# Keycloak issues
uv run cli dev logs keycloak
```

## 🔧 Troubleshooting

### Common Issues

#### Port Conflicts
```bash
# Check what's using ports
sudo netstat -tlnp | grep :8080
sudo netstat -tlnp | grep :5432

# Stop conflicting services
sudo systemctl stop postgresql  # If system PostgreSQL is running
```

#### Database Connection Issues
```bash
# Reset database
uv run cli dev stop
docker volume rm dev_env_postgres_data  # Warning: destroys data
uv run cli dev start-env
```

#### Keycloak Authentication Issues
```bash
# Verify Keycloak is configured
curl http://localhost:8080/realms/test-realm/.well-known/openid_configuration

# Check Keycloak logs
uv run cli dev logs keycloak

# Reconfigure Keycloak (if needed)
python src/dev/setup_keycloak.py
```

#### Clean Start
```bash
# Complete environment reset
uv run cli dev stop
docker-compose -f dev_env/docker-compose.yml down -v  # Removes volumes
uv run cli dev start-env
```

### Getting Help

- **Service Status**: `uv run cli dev status`
- **Logs**: `uv run cli dev logs [service_name]`
- **Health Checks**: All services include health check endpoints
- **Documentation**: Check service-specific READMEs in `dev_env/`

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: Check the generated project's README for detailed usage
- **Issues**: Report bugs and feature requests on GitHub
- **Discussions**: Join our community discussions for help and ideas

---

**Ready to build something amazing?** 🚀

```bash
cruft create https://github.com/piewared/api_project_template
```
