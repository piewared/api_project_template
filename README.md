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
- **OpenID Connect (OIDC)** integration with configurable providers
- **Session-based authentication** with secure cookie handling  
- **JWT token validation** and refresh mechanisms
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
cruft create https://github.com/your-org/api-project-template

# Follow the prompts to configure your project
```

Using Cookiecutter:

```bash
# Install cookiecutter  
pip install cookiecutter

# Create project from template
cookiecutter https://github.com/your-org/api-project-template
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
# Visit the login endpoint
curl http://localhost:8000/auth/web/login

# Or test with browser:
# 1. Go to http://localhost:8000/auth/web/login
# 2. Login with: testuser1 / password123
# 3. You'll be redirected back to your app
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

Copy `.env.example` to `.env` and configure:

```bash
# Environment
ENVIRONMENT=development

# Database Configuration
DATABASE_URL=sqlite:///./database.db
# For PostgreSQL: DATABASE_URL=postgresql://user:password@localhost:5432/your_db

# Infrastructure URLs
REDIS_URL=redis://localhost:6379/0
TEMPORAL_URL=localhost:7233
BASE_URL=http://localhost:8000

# OIDC Configuration
OIDC_REDIRECT_URI=http://localhost:8000/auth/web/callback

# Provider-specific credentials (example for Keycloak)
OIDC_KEYCLOAK_CLIENT_ID=your-keycloak-client-id
OIDC_KEYCLOAK_CLIENT_SECRET=your-keycloak-client-secret

# JWT Configuration
JWT_AUDIENCE=api://default
SESSION_JWT_SECRET=your-session-jwt-secret-CHANGE_ME!
SESSION_MAX_AGE=3600
```

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
        # ... Google-specific endpoints
      microsoft:
        client_id: "${OIDC_MICROSOFT_CLIENT_ID}"
        client_secret: "${OIDC_MICROSOFT_CLIENT_SECRET}"
        # ... Microsoft-specific endpoints
      keycloak:
        client_id: "${OIDC_KEYCLOAK_CLIENT_ID}"
        client_secret: "${OIDC_KEYCLOAK_CLIENT_SECRET}"
        issuer: "${OIDC_KEYCLOAK_ISSUER:-http://localhost:8080/realms/master}"
        # ... Keycloak-specific endpoints
    default_provider: "keycloak"
    global_redirect_uri: "${OIDC_REDIRECT_URI:-http://localhost:8000/auth/callback}"

  # JWT token validation
  jwt:
    allowed_algorithms: ["RS256", "RS512", "ES256", "ES384"]
    audiences: ["${JWT_AUDIENCE:-api://default}"]
    claims:
      user_id: "${JWT_CLAIM_USER_ID:-sub}"
      email: "${JWT_CLAIM_EMAIL:-email}"
      roles: "${JWT_CLAIM_ROLES:-roles}"

  # Application settings
  app:
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

## 📁 Project Structure

```
your_project/
├── src/
│   └── your_package/
│       ├── app/
│       │   ├── entities/          # Domain entities
│       │   │   ├── core/          # Base classes
│       │   │   └── [entity]/      # Entity packages
│       │   ├── api/               # FastAPI routers
│       │   ├── core/              # Core functionality
│       │   │   ├── auth.py        # Authentication
│       │   │   ├── database.py    # Database setup
│       │   │   └── config.py      # Configuration
│       │   ├── runtime/           # Application runtime
│       │   └── service/           # Business services
│       └── dev/                   # Development tools
├── tests/                         # Test suites
├── dev_env/                       # Development environment
├── docs/                          # Documentation
└── scripts/                       # Utility scripts
```

### Data Persistence

Development data is persisted in Docker volumes:
- `dev_env/postgres-data/` - PostgreSQL data
- `dev_env/redis-data/` - Redis data  
- `dev_env/temporal-data/` - Temporal data
- `dev_env/keycloak-data/` - Keycloak configuration

## 🎯 Architecture & Design

This template follows **Domain-Driven Design** principles with **Clean Architecture**:

- **Entities**: Core business objects with SQLModel
- **Repositories**: Data access layer with type safety
- **Services**: Business logic and workflows
- **API Layer**: FastAPI routers and dependency injection
- **Infrastructure**: Database, auth, external services

### Key Patterns
- **Repository Pattern**: Standardized data access
- **Dependency Injection**: Clean separation of concerns
- **Event-Driven**: Temporal workflows for complex processes
- **Type Safety**: Full mypy compatibility with Pydantic/SQLModel

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- **Documentation**: Check the generated project's README for detailed usage
- **Issues**: Report bugs and feature requests on GitHub
- **Discussions**: Join our community discussions for help and ideas

---

**Ready to build something amazing?** 🚀

```bash
cruft create https://github.com/your-org/api-project-template
```
