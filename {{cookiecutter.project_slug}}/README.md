# {{cookiecutter.project_name}}

{{cookiecutter.project_description}}

## 🏗️ Architecture Overview

This template follows **hexagonal architecture** principles, providing a clean separation of concerns across three main layers:

### Core Layer (Domain)
- **Entities**: Pure domain models with business logic
- **Repositories**: Abstract interfaces for data access
- **Services**: Domain services and business rules
- Contains NO framework dependencies

### Application Layer
- **Entities**: Application-specific domain models
- **Repositories**: Concrete repository implementations
- **Policies**: Application-specific business rules
- Orchestrates core domain logic

### Infrastructure Layer
- **HTTP API**: FastAPI routers, schemas, middleware
- **Database**: SQLModel/SQLAlchemy persistence
- **External Services**: Third-party integrations
- **Configuration**: Settings and environment management

## 🚀 Features

### Authentication & Authorization
- **JWT/OIDC Integration**: Multi-issuer JWT validation with JWKS
- **Flexible Claims**: Configurable UID, scope, and role claims
- **Development Mode**: Built-in dev user for local development
- **Scope & Role Guards**: Decorative authorization dependencies

### Infrastructure
- **Rate Limiting**: Redis-backed or in-memory rate limiting
- **CORS Configuration**: Production-ready CORS settings
- **Security Headers**: Comprehensive security middleware
- **Database Management**: SQLModel with migration support
- **Logging**: Structured request/response logging

### Development Experience
- **Type Safety**: Full typing with Pydantic and SQLModel
- **Testing Framework**: Comprehensive test suite with fixtures
- **Environment Configuration**: Pydantic Settings with .env support
- **Documentation**: Auto-generated OpenAPI docs (dev only)

## 📦 Project Structure

```
{{cookiecutter.package_name}}/
├── api/
│   └── http/
│       ├── app.py              # FastAPI application factory
│       ├── deps.py             # Dependency injection
│       ├── middleware/         # Custom middleware
│       ├── routers/            # API route handlers
│       └── schemas/            # Pydantic request/response models
├── application/
│   ├── entities/               # Application domain models
│   ├── repositories/           # Repository implementations
│   ├── rows/                   # Database persistence models
│   └── services/               # Application services
├── core/
│   ├── entities/               # Core domain entities
│   │   ├── user.py            # User domain model
│   │   └── user_identity.py   # Identity mapping model
│   ├── repositories/           # Abstract repository interfaces
│   │   └── user_repo.py       # User repository interfaces
│   ├── rows/                   # Core database models
│   │   ├── user_row.py        # User persistence model
│   │   └── user_identity_row.py # Identity persistence model
│   └── services/               # Domain services
│       └── jwt_service.py     # JWT validation service
└── runtime/
    ├── db.py                   # Database connection
    ├── init_db.py             # Database initialization
    └── settings.py            # Configuration management

tests/
├── unit/
│   ├── core/                   # Core layer tests
│   └── infrastructure/        # Infrastructure tests
├── integration/               # Cross-layer integration tests
└── fixtures/                  # Test utilities and fixtures
```

## 🛠️ Getting Started

### Prerequisites
- Python 3.13+
- UV package manager (recommended) or pip

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url> {{cookiecutter.project_slug}}
   cd {{cookiecutter.project_slug}}
   ```

2. **Install dependencies**:
   ```bash
   # Using UV (recommended)
   uv sync
   
   # Or using pip
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Initialize database**:
   ```bash
   uv run init-db
   # Or: python -m {{cookiecutter.package_name}}.runtime.init_db
   ```

5. **Run the application**:
   ```bash
   uvicorn main:app --reload
   ```

The API will be available at `http://localhost:8000` with docs at `http://localhost:8000/docs`.

## ⚙️ Configuration

### Environment Variables

Key configuration options (see `.env` for complete list):

```bash
# Application
ENVIRONMENT=development          # development|production|test
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///./database.db

# CORS
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com

# JWT/OIDC
JWT_ISSUER_JWKS_MAP={"https://issuer.example.com":"https://issuer.example.com/.well-known/jwks.json"}
JWT_AUDIENCES=api://default
JWT_ALLOWED_ALGOS=RS256,RS512,ES256,ES384
JWT_UID_CLAIM=https://your.app/uid
JWT_ROLE_CLAIM=roles
JWT_SCOPE_CLAIM=scope

# Rate Limiting
REDIS_URL=redis://localhost:6379/0  # Optional: enables Redis-backed rate limiting
RATE_LIMIT_REQUESTS=5
RATE_LIMIT_WINDOW=60
```

### JWT Configuration

The template supports multiple JWT issuers and configurable claim extraction:

- **Issuer JWKS Map**: Maps issuer URLs to their JWKS endpoints
- **Audiences**: List of valid token audiences
- **Claims**: Configurable extraction of UID, roles, and scopes

## 🧱 Building Your Application

### 1. Define Your Domain

Create domain entities in `generator/core/entities/`:

```python
# generator/core/entities/product.py
from {{cookiecutter.package_name}}.core.entities._base import Entity

class Product(Entity):
    id: int
    name: str
    price: Decimal
    description: Optional[str] = None
```

### 2. Create Repository Interfaces

Define repository contracts in `generator/core/repositories/`:

```python
# generator/core/repositories/product_repo.py
from abc import ABC, abstractmethod
from typing import List, Optional
from {{cookiecutter.package_name}}.core.entities.product import Product

class ProductRepository(ABC):
    @abstractmethod
    def get(self, product_id: int) -> Optional[Product]:
        pass
    
    @abstractmethod
    def list(self) -> List[Product]:
        pass
```

### 3. Implement Persistence

Create database models in `generator/application/rows/`:

```python
# generator/application/rows/product_row.py
from decimal import Decimal
from typing import Optional
from sqlmodel import SQLModel, Field

class ProductRow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    price: Decimal
    description: Optional[str] = None
```

Implement repositories in `generator/application/repositories/`:

```python
# generator/application/repositories/product_repo.py
from typing import List, Optional
from sqlmodel import Session, select
from {{cookiecutter.package_name}}.core.repositories.product_repo import ProductRepository
from {{cookiecutter.package_name}}.core.entities.product import Product
from {{cookiecutter.package_name}}.application.rows.product_row import ProductRow

class SqlProductRepository(ProductRepository):
    def __init__(self, session: Session):
        self.session = session
    
    def get(self, product_id: int) -> Optional[Product]:
        row = self.session.get(ProductRow, product_id)
        return Product.model_validate(row) if row else None
```

### 4. Create API Layer

Define schemas in `generator/api/http/schemas/`:

```python
# generator/api/http/schemas/product.py
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict

class ProductCreate(BaseModel):
    name: str
    price: Decimal
    description: Optional[str] = None

class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    price: Decimal
    description: Optional[str]
```

Create routers in `generator/api/http/routers/`:

```python
# generator/api/http/routers/products.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from {{cookiecutter.package_name}}.api.http.schemas.product import ProductCreate, ProductRead
from {{cookiecutter.package_name}}.application.repositories.product_repo import SqlProductRepository
from {{cookiecutter.package_name}}.api.http.deps import get_session, require_scope
from {{cookiecutter.package_name}}.api.http.middleware.limiter import rate_limit

router = APIRouter()

def get_product_repo(db: Session = Depends(get_session)) -> SqlProductRepository:
    return SqlProductRepository(db)

@router.get("/", response_model=List[ProductRead])
async def list_products(
    _: None = Depends(rate_limit(10, 60)),
    _: None = Depends(require_scope("read:products")),
    repo: SqlProductRepository = Depends(get_product_repo)
):
    return repo.list()
```

### 5. Register Your Routes

Add your router to `generator/api/http/app.py`:

```python
from {{cookiecutter.package_name}}.api.http.routers import products

app.include_router(products.router, prefix="/products", tags=["products"])
```

## 🧪 Testing

The template includes a comprehensive test suite organized by architectural layers:

```bash
# Run all tests
pytest

# Run specific test layers
pytest tests/unit/core/          # Domain logic tests
pytest tests/unit/application/   # Application layer tests
pytest tests/unit/infrastructure/ # Infrastructure tests
pytest tests/integration/       # Cross-layer integration tests

# Run with coverage
pytest --cov=generator
```

### Test Structure

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **Fixtures**: Reusable test utilities and data

Example test:

```python
# tests/unit/core/test_product.py
from {{cookiecutter.package_name}}.core.entities.product import Product

class TestProductEntity:
    def test_create_product(self):
        product = Product(
            id=1,
            name="Test Product",
            price=Decimal("19.99")
        )
        assert product.name == "Test Product"
        assert product.price == Decimal("19.99")
```

## 🔒 Security Considerations

### Production Deployment

1. **Environment Configuration**:
   - Set `ENVIRONMENT=production`
   - Configure proper JWT issuer JWKS endpoints
   - Use strong database credentials
   - Enable Redis for rate limiting

2. **Security Headers**:
   - HSTS enabled automatically in production
   - Content security headers configured
   - CORS properly restricted

3. **Rate Limiting**:
   - Redis-backed rate limiting for distributed deployments
   - Configurable per-endpoint limits

### Authentication Flow

1. Client sends request with `Authorization: Bearer <jwt>`
2. JWT validated against configured JWKS endpoints
3. Claims extracted for UID, scopes, and roles
4. User identity resolved from database
5. Request state populated with user context

## 📚 Additional Resources

### Key Dependencies

- **FastAPI**: Modern Python web framework
- **SQLModel**: SQL databases with Python type hints
- **Pydantic**: Data validation using Python type annotations
- **Authlib**: OAuth and OIDC library
- **FastAPI-Limiter**: Rate limiting for FastAPI

### Useful Commands

```bash
# Database operations
uv run init-db                    # Initialize database
python -m {{cookiecutter.package_name}}.runtime.init_db  # Alternative initialization

# Development
uvicorn main:app --reload         # Run with auto-reload
pytest --watch                   # Run tests with file watching

# Production
uvicorn main:app --workers 4     # Run with multiple workers
gunicorn -w 4 -k uvicorn.workers.UnicornWorker main:app  # Alternative ASGI server
```

## 🤝 Contributing

This template is designed to be a starting point for your projects. Key principles:

1. **Maintain Architectural Boundaries**: Keep domain logic in core, application logic in application layer
2. **Dependency Direction**: Dependencies should flow inward (infrastructure → application → core)
3. **Test Coverage**: Maintain comprehensive tests across all layers
4. **Type Safety**: Use typing throughout for better development experience

## 📄 License

This template is provided as-is for use as a foundation for your FastAPI projects. Modify as needed for your specific requirements.