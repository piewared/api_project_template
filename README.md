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
- Python {{cookiecutter.python_version}}+
- [Cookiecutter](https://cookiecutter.readthedocs.io/en/latest/installation.html)
- [Cruft](https://cruft.github.io/cruft/) (recommended for updates)

### Generate a New Project

```bash
# Using Cruft (recommended - enables updates)
cruft create https://github.com/YOUR_ORG/fastapi-hexagonal-template

# Or using Cookiecutter directly
cookiecutter https://github.com/YOUR_ORG/fastapi-hexagonal-template
```

### Template Options

When generating a project, you'll be prompted for:

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
│       └── template-update.yml # Automated template updates
├── main.py                    # Application entry point
├── pyproject.toml            # Project configuration
├── your_package/
│   ├── api/
│   │   └── http/
│   │       ├── app.py        # FastAPI application factory
│   │       ├── deps.py       # Dependency injection
│   │       ├── middleware/   # Custom middleware
│   │       ├── routers/      # API route handlers
│   │       └── schemas/      # Pydantic request/response models
│   ├── application/
│   │   ├── entities/         # Application domain models
│   │   ├── repositories/     # Repository implementations
│   │   ├── rows/            # Database persistence models
│   │   └── services/        # Application services
│   ├── core/
│   │   ├── entities/        # Core domain entities
│   │   ├── repositories/    # Abstract repository interfaces
│   │   ├── rows/           # Core database models
│   │   └── services/       # Domain services
│   └── runtime/
│       ├── db.py           # Database connection
│       ├── init_db.py      # Database initialization
│       └── settings.py     # Configuration management
└── tests/
    ├── unit/               # Unit tests by layer
    ├── integration/        # Integration tests
    └── fixtures/          # Test utilities and fixtures
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