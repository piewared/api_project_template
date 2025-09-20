# Features

## ✨ Complete Feature Set

### 🏗️ Architecture
- **Hexagonal Architecture**: Clean separation of concerns with domain, application, and infrastructure layers
- **Dependency Injection**: Built-in dependency management with FastAPI's DI system
- **Repository Pattern**: Abstract repository interfaces with concrete implementations
- **Domain-Driven Design**: Core domain logic isolated from infrastructure concerns

### 🔐 Security & Authentication  
- **JWT/OIDC Integration**: Multi-issuer JWT validation with JWKS endpoint support
- **Flexible Claims**: Configurable UID, scope, and role extraction from JWT tokens
- **Development Mode**: Built-in development user for local testing
- **Authorization Guards**: Decorator-based scope and role requirements

### 🚀 Production Ready
- **Rate Limiting**: Redis-backed or in-memory rate limiting with configurable rules
- **Security Headers**: Comprehensive security middleware (HSTS, CSP, etc.)
- **CORS Configuration**: Production-ready CORS with credential support
- **Health Checks**: Built-in health and readiness endpoints
- **Structured Logging**: Request correlation IDs and structured JSON logging

### 🧪 Developer Experience
- **Type Safety**: Full typing with Pydantic and SQLModel throughout
- **Testing Framework**: Comprehensive test suite with 62 tests, fixtures and utilities
- **Code Quality**: Pre-configured linting, formatting, and type checking
- **Environment Management**: Pydantic Settings with .env file support
- **Auto-Documentation**: OpenAPI/Swagger docs (development only)
- **Unified Development**: Single test directory with infrastructure and template tests

### 🔄 Template Updates
- **Cruft Integration**: Track template versions and receive automated updates
- **GitHub Actions**: Automated weekly checks for template updates with PR creation
- **Migration Guides**: Detailed documentation for handling breaking changes
- **Version Tracking**: Semantic versioning with changelog and migration notes

## What You Get

### 🚀 **Ready-to-Run Features**
- ✅ **FastAPI Application** with hexagonal architecture
- ✅ **Authentication & Authorization** (JWT/OIDC, roles, scopes)
- ✅ **Database Integration** (SQLModel/SQLAlchemy with SQLite default)
- ✅ **Rate Limiting** (Redis or in-memory)
- ✅ **Security Middleware** (CORS, security headers, HSTS)
- ✅ **Environment Configuration** (Pydantic Settings)
- ✅ **Comprehensive Testing** (62 tests with fixtures)
- ✅ **Code Quality Tools** (Ruff, MyPy, pre-commit ready)
- ✅ **CI/CD Pipeline** (GitHub Actions)
- ✅ **Auto-Documentation** (OpenAPI/Swagger)
- ✅ **Template Updates** (Cruft integration)
- ✅ **Template Validation** (Verified working template generation)

### 🛠️ **Development Tools Included**
```bash
# Code quality
uv run ruff check .          # Linting
uv run ruff format .         # Code formatting  
uv run mypy your_package     # Type checking

# Testing
uv run pytest               # Run tests (3 example tests)
uv run pytest --cov        # With coverage

# Database
uv run init-db              # Initialize database

# Development server
uvicorn main:app --reload   # Hot reload server
```

### ⚙️ **Environment Configuration**
Your `.env.example` includes settings for:
- Database connections (SQLite/PostgreSQL)
- JWT/OIDC authentication (multiple issuers)
- Redis configuration (rate limiting, optional)
- CORS and security settings
- Logging levels

**Note**: The template generates a clean `.env.example` without development user settings to avoid validation conflicts during startup. Configure authentication settings based on your specific JWT/OIDC provider.