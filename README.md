# FastAPI Hexagonal Architecture Template

A modern, production-ready [Cookiecutter](https://cookiecutter.readthedocs.io/) template for creating FastAPI applications with hexagonal (ports and adapters) architecture. Includes comprehensive authentication, authorization, rate limiting, and automated template updates via [Cruft](https://cruft.github.io/cruft/).

## ✨ Features

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
- **Testing Framework**: Comprehensive test suite with fixtures and utilities
- **Code Quality**: Pre-configured linting, formatting, and type checking
- **Environment Management**: Pydantic Settings with .env file support
- **Auto-Documentation**: OpenAPI/Swagger docs (development only)

### 🔄 Template Updates
- **Cruft Integration**: Track template versions and receive automated updates
- **GitHub Actions**: Automated weekly checks for template updates with PR creation
- **Migration Guides**: Detailed documentation for handling breaking changes
- **Version Tracking**: Semantic versioning with changelog and migration notes

## 🚀 Quick Start

### Prerequisites
- Python 3.10+ (3.13 recommended)
- [Cookiecutter](https://cookiecutter.readthedocs.io/en/latest/installation.html): `pip install cookiecutter`
- [Cruft](https://cruft.github.io/cruft/) (recommended for updates): `pip install cruft`

### 🎯 Create a New Project

#### Option 1: Using Cruft (Recommended)
Cruft enables automatic template updates in the future:

```bash
# Create a new project with update capabilities
cruft create https://github.com/piewared/api_template

# Follow the interactive prompts to configure your project
```

#### Option 2: Using Cookiecutter
Standard generation without update capabilities:

```bash
# Create a new project
cookiecutter https://github.com/piewared/api_template

# Or use the local template for development/testing
cookiecutter /path/to/this/template
```

#### Option 3: Non-Interactive Generation
For automation or CI/CD:

```bash
# Generate with specific options
cruft create https://github.com/piewared/api_template \
  --no-input \
  project_name="My Awesome API" \
  project_description="A FastAPI service for awesome things" \
  author_name="Your Name" \
  author_email="your.email@example.com" \
  use_redis=y \
  use_postgres=n
```

### ⚙️ Configuration Options

When generating a project, you'll be prompted for these options:

| Option | Description | Default | Examples |
|--------|-------------|---------|----------|
| `project_name` | Human-readable project name | "My API Project" | "User Management API", "Payment Service" |
| `project_slug` | URL/filesystem safe name | auto-generated | "user_management_api", "payment_service" |
| `package_name` | Python package name | same as slug | "user_management", "payment_svc" |
| `project_description` | Brief project description | "A FastAPI service..." | "RESTful API for user management" |
| `author_name` | Your name | "Your Name" | "Jane Smith" |
| `author_email` | Your email | "your.email@example.com" | "jane@company.com" |
| `version` | Initial version | "0.1.0" | "1.0.0", "0.0.1" |
| `python_version` | Minimum Python version | "3.13" | "3.10", "3.11", "3.12" |
| `use_redis` | Include Redis rate limiting | "y" | "y" (yes), "n" (no) |
| `use_postgres` | Include PostgreSQL examples | "n" | "y" (yes), "n" (no) |
| `include_example_routes` | Include example API routes | "y" | "y" (yes), "n" (no) |
| `license` | License type | "MIT" | "MIT", "Apache-2.0", "GPL-3.0", "None" |

### 🏃‍♂️ Get Started with Your New Project

After generation, your project will be automatically set up:

```bash
# Navigate to your new project
cd your-project-name

# The project is ready to use! Dependencies are installed, git is initialized
# Configure your environment
cp .env.example .env
# Edit .env with your specific settings

# Initialize the database
uv run init-db

# Start the development server
uvicorn main:app --reload
```

Your API will be available at:
- **Application**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs (development only)
- **ReDoc Documentation**: http://localhost:8000/redoc (development only)

## 🏗️ What You Get

Your generated project includes:

### 📁 **Complete Project Structure**
```
your-project/
├── .cruft.json                # Template version tracking
├── .env.example              # Environment configuration template
├── .github/workflows/        # CI/CD and automated template updates
├── main.py                   # Application entry point
├── pyproject.toml           # Project configuration & dependencies
├── your_package/            # Your application code
│   ├── api/http/           # FastAPI routes, middleware, schemas
│   ├── core/               # Domain entities, services, repositories
│   ├── application/        # Application layer implementations
│   └── runtime/            # Database, settings, initialization
└── tests/                  # Comprehensive test suite
```

### 🚀 **Ready-to-Run Features**
- ✅ **FastAPI Application** with hexagonal architecture
- ✅ **Authentication & Authorization** (JWT/OIDC, roles, scopes)
- ✅ **Database Integration** (SQLModel/SQLAlchemy with SQLite default)
- ✅ **Rate Limiting** (Redis or in-memory)
- ✅ **Security Middleware** (CORS, security headers, HSTS)
- ✅ **Environment Configuration** (Pydantic Settings)
- ✅ **Comprehensive Testing** (59 tests with fixtures)
- ✅ **Code Quality Tools** (Ruff, MyPy, pre-commit ready)
- ✅ **CI/CD Pipeline** (GitHub Actions)
- ✅ **Auto-Documentation** (OpenAPI/Swagger)
- ✅ **Template Updates** (Cruft integration)

### 🛠️ **Development Tools Included**
```bash
# Code quality
uv run ruff check .          # Linting
uv run ruff format .         # Code formatting  
uv run mypy your_package     # Type checking

# Testing
uv run pytest               # Run tests
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
- Redis configuration (rate limiting)
- CORS and security settings
- Development user configuration
- Logging levels

| Option | Description | Default |
|--------|-------------|---------|
| `project_name` | Human-readable project name | "My API Project" |
| `project_slug` | URL/filesystem safe project name | auto-generated |
| `package_name` | Python package name | auto-generated |
| `project_description` | Brief project description | "A FastAPI service..." |
| `author_name` | Your name | "Your Name" |
| `author_email` | Your email address | "your.email@example.com" |
| `version` | Initial version | "0.1.0" |
| `python_version` | Minimum Python version | "3.13" |
| `use_redis` | Include Redis rate limiting | "y" |
| `use_postgres` | Include PostgreSQL examples | "n" |
| `include_example_routes` | Include example API routes | "y" |
| `license` | License type | "MIT" |

### Project Setup

After generation, your project will be automatically set up with:

```bash
cd your-project-name

# Dependencies are already installed
# Git repository is initialized
# .cruft.json tracks template version

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Initialize database
uv run init-db

# Start development server
uvicorn main:app --reload
```

## 📂 Generated Project Structure

```
your-project/
├── .cruft.json                 # Template tracking (Cruft)
├── .env.example               # Environment template
├── .github/
│   └── workflows/
│       ├── ci.yml            # Continuous integration
│       └── template-update.yml # Auto-update from template
├── README.md                  # Generated project documentation  
├── database.db               # SQLite database (auto-created)
├── main.py                   # FastAPI app entry point
├── pyproject.toml           # Dependencies & project config
├── your_package/            # Main application package
│   ├── __init__.py
│   ├── api/                 # HTTP API layer
│   │   ├── http/
│   │   │   ├── app.py      # FastAPI application factory
│   │   │   ├── deps.py     # Dependency injection
│   │   │   ├── middleware/ # Security, CORS, rate limiting
│   │   │   ├── routers/    # API route handlers
│   │   │   └── schemas/    # Pydantic request/response models
│   ├── application/         # Application service layer
│   │   ├── entities/       # Application entities
│   │   ├── repositories/   # Repository interfaces
│   │   └── services/       # Application services
│   ├── core/               # Domain/core business logic
│   │   ├── entities/       # Domain entities (User, etc.)
│   │   ├── repositories/   # Core repository implementations
│   │   └── services/       # Core domain services
│   └── runtime/            # Infrastructure & configuration
│       ├── db.py          # Database setup
│       ├── init_db.py     # Database initialization
│       └── settings.py    # Application settings
└── tests/                  # Comprehensive test suite
    ├── conftest.py        # Pytest configuration & fixtures
    ├── fixtures/          # Test data factories
    ├── e2e/              # End-to-end tests
    ├── integration/      # Integration tests
    └── unit/             # Unit tests
```
    ```

## 🔄 Template Updates

This template is designed to evolve over time. Generated projects can easily receive updates:

### Automatic Updates (Recommended)

The generated project includes a GitHub Action that:
- Checks for template updates weekly
- Creates a pull request with changes
- Provides detailed migration notes

### Manual Updates

```bash
# Check for available updates
cruft check

# Apply updates interactively
cruft update
```
```

## 🔄 Template Updates

This template is designed to evolve over time. Generated projects can easily receive updates:

### Automatic Updates (Recommended)

The generated project includes a GitHub Action that:
- Checks for template updates weekly
- Creates a pull request with changes
- Provides detailed migration notes

### Manual Updates

```bash
# Check for available updates
cruft check

# Apply updates interactively
cruft update

# Review changes and test
git diff
pytest
```

### Linking Existing Projects

To link an existing project to this template:

```bash
# In your existing project directory
cruft link https://github.com/YOUR_ORG/fastapi-hexagonal-template
```

## 🏗️ Extending Your Project

### Adding New Features

1. **Define Domain Entity** (`core/entities/`):
   ```python
   from core.entities._base import Entity
   
   class Product(Entity):
       id: int
       name: str
       price: Decimal
   ```

2. **Create Repository Interface** (`core/repositories/`):
   ```python
   from abc import ABC, abstractmethod
   
   class ProductRepository(ABC):
       @abstractmethod
       def get(self, product_id: int) -> Optional[Product]:
           pass
   ```

3. **Implement Persistence** (`application/`):
   ```python
   # Database model
   class ProductRow(SQLModel, table=True): ...
   
   # Repository implementation
   class SqlProductRepository(ProductRepository): ...
   ```

4. **Add API Layer** (`api/http/`):
   ```python
   # Schemas
   class ProductCreate(BaseModel): ...
   class ProductRead(BaseModel): ...
   
   # Router
   @router.get("/products")
   async def list_products(): ...
   ```

### Configuration Management

Environment variables are managed through Pydantic Settings:

```python
# runtime/settings.py
class Settings(BaseSettings):
    new_feature_enabled: bool = False
    api_key: str = Field(..., env="MY_API_KEY")
```

### Testing Strategy

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **E2E Tests**: Test complete user workflows

## 📋 Development Commands

```bash
# Development server
uvicorn main:app --reload

# Testing
pytest                        # Run tests
pytest --cov=your_package    # With coverage
pytest -k "test_auth"        # Run specific tests

# Code quality
ruff check .                 # Linting
ruff format .               # Formatting
mypy your_package           # Type checking

# Database
uv run init-db              # Initialize database
```

## 🚀 Deployment

### Docker

Generate a Dockerfile with your project or add deployment configurations.

### Environment Variables

Key production settings:

```bash
ENVIRONMENT=production
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
JWT_ISSUER_JWKS_MAP={"https://...":"https://..."}
CORS_ORIGINS=https://yourdomain.com
```

## 🤝 Contributing to the Template

We welcome contributions to improve this template:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add/update tests
5. Update documentation
6. Submit a pull request

### Template Development

To test template changes:

```bash
# Test template generation
cruft create . --output-dir /tmp/test-project

# Test updates
cd existing-project
cruft update
```

## 📚 Architecture Documentation

### Hexagonal Architecture

This template implements hexagonal architecture (ports and adapters):

- **Core**: Pure domain logic, no external dependencies
- **Application**: Orchestrates domain logic, implements use cases  
- **Infrastructure**: External concerns (HTTP, database, etc.)

### Design Principles

- **Dependency Inversion**: Dependencies point inward toward the domain
- **Interface Segregation**: Small, focused interfaces
- **Single Responsibility**: Each layer has a clear purpose
- **Open/Closed**: Extend functionality without modifying existing code

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/YOUR_ORG/fastapi-hexagonal-template/issues)
- **Discussions**: [GitHub Discussions](https://github.com/YOUR_ORG/fastapi-hexagonal-template/discussions)
- **Documentation**: Check the generated project's README.md

## 📄 License

This template is released under the MIT License. Generated projects can use any license you specify during generation.

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Cookiecutter](https://cookiecutter.readthedocs.io/) - Project templating
- [Cruft](https://cruft.github.io/cruft/) - Template synchronization
- [SQLModel](https://sqlmodel.tiangolo.com/) - SQL database integration
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation

---

**Happy coding! 🚀**