# 🚀 FastAPI Production Template

A comprehensive, production-ready FastAPI template with built-in authentication, development tools, and modern Python architecture patterns.

## 📋 Overview

This template provides a complete foundation for building scalable FastAPI applications with:

- **🔐 Built-in OIDC Authentication** - Complete auth flow with session management
- **🏗️ Clean Architecture** - Organized entity/service layer with clear separation of concerns
- **⚡ Development Environment** - Integrated Keycloak and PostgreSQL via Docker
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
- **Integrated development environment** with Docker Compose
- **Keycloak** for local OIDC testing and user management
- **PostgreSQL** database with migration support
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

# Start development environment (Keycloak + PostgreSQL)
uv run your-project-dev start-dev-env

# Initialize database
uv run init-db

# Start development server
uv run your-project-dev start-server
```

Your API will be available at:
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (development only)
- **Keycloak Admin**: http://localhost:8080 (admin/admin)

## 🏗️ Architecture Overview

```
your-project/
├── your_package/
│   ├── app/                    # Application layer
│   │   ├── api/http/          # HTTP API (routes, middleware, schemas)  
│   │   ├── core/services/     # Core infrastructure services
│   │   ├── entities/          # Entity definitions
│   │   │   ├── core/         # Infrastructure entities (User, Auth)
│   │   │   └── service/      # Domain entities (your business models)
│   │   ├── service/          # Business service layer  
│   │   └── runtime/          # Infrastructure (DB, settings, init)
│   └── dev/                   # Development CLI tools
├── tests/                     # Comprehensive test suite
├── dev_env/                   # Development environment (Docker)
└── main.py                   # Application entry point
```

## 💡 Adding Business Logic

### 1. Define Domain Entity

Create a complete entity following the template's pattern. Add your domain entities in `your_package/app/entities/service/product/`:

**`your_package/app/entities/service/product/entity.py`:**
```python
"""Product domain entity."""

from typing import Optional
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from your_package.app.entities.core._base import Entity


class Product(Entity):
    """Product entity representing a sellable item.

    This is the domain model that contains business logic and validation.
    It inherits from Entity to get auto-generated UUID identifiers.
    """

    name: str = Field(description="Product name")
    price: Decimal = Field(description="Product price", ge=0)
    description: Optional[str] = Field(default=None, description="Product description")
    category: str = Field(description="Product category")
    stock_quantity: int = Field(default=0, ge=0, description="Available stock")
    is_active: bool = Field(default=True, description="Whether product is active")
    
    def is_in_stock(self) -> bool:
        """Check if product is in stock."""
        return self.stock_quantity > 0 and self.is_active
    
    def can_fulfill_order(self, quantity: int) -> bool:
        """Check if we can fulfill an order for the given quantity."""
        return self.is_active and self.stock_quantity >= quantity
```

**`your_package/app/entities/service/product/table.py`:**
```python
"""Product database table model."""

from typing import Optional
from decimal import Decimal
from sqlmodel import Field

from your_package.app.entities.core._base import EntityTable


class ProductTable(EntityTable, table=True):
    """Database persistence model for products.

    This represents how the Product entity is stored in the database.
    It's separate from the domain entity to maintain clean architecture.
    """

    name: str
    price: Decimal = Field(decimal_places=2)
    description: Optional[str] = None
    category: str
    stock_quantity: int = Field(default=0)
    is_active: bool = Field(default=True)
    
    # Additional database-specific fields
    sku: Optional[str] = Field(default=None, index=True, description="Stock keeping unit")
    barcode: Optional[str] = Field(default=None, index=True)
```

**`your_package/app/entities/service/product/repository.py`:**
```python
"""Product repository for data access."""

from typing import List, Optional
from sqlmodel import Session, select

from .entity import Product
from .table import ProductTable


class ProductRepository:
    """Data access layer for Product entities.

    This handles all database operations for Products while keeping
    the data access logic colocated with the Product entity.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, product_id: str) -> Optional[Product]:
        """Get a product by ID."""
        row = self._session.get(ProductTable, product_id)
        if row is None:
            return None
        return Product.model_validate(row, from_attributes=True)

    def save(self, product: Product) -> Product:
        """Save a product to the database."""
        # Convert domain entity to table row
        product_data = product.model_dump(exclude={'id', 'created_at', 'updated_at'})
        
        if product.id:
            # Update existing
            row = self._session.get(ProductTable, product.id)
            if row:
                for key, value in product_data.items():
                    setattr(row, key, value)
            else:
                raise ValueError(f"Product {product.id} not found")
        else:
            # Create new
            row = ProductTable(**product_data)
            self._session.add(row)
        
        self._session.commit()
        self._session.refresh(row)
        return Product.model_validate(row, from_attributes=True)

    def list_active_products(self) -> List[Product]:
        """Get all active products."""
        statement = select(ProductTable).where(ProductTable.is_active == True)
        rows = self._session.exec(statement).all()
        return [Product.model_validate(row, from_attributes=True) for row in rows]

    def find_by_category(self, category: str) -> List[Product]:
        """Find products by category."""
        statement = select(ProductTable).where(ProductTable.category == category)
        rows = self._session.exec(statement).all()
        return [Product.model_validate(row, from_attributes=True) for row in rows]

    def delete(self, product_id: str) -> bool:
        """Delete a product by ID."""
        row = self._session.get(ProductTable, product_id)
        if row:
            self._session.delete(row)
            self._session.commit()
            return True
        return False
```

**`your_package/app/entities/service/product/__init__.py`:**
```python
"""Product entity package."""

from .entity import Product
from .repository import ProductRepository
from .table import ProductTable

__all__ = ["Product", "ProductRepository", "ProductTable"]
```

### 2. Implement Business Service

Add business logic in `your_package/app/service/__init__.py`:

```python
from typing import List, Optional
from decimal import Decimal

from ..entities.service.product import Product, ProductRepository


class ProductService:
    """Business service for product operations."""
    
    def __init__(self, product_repo: ProductRepository):
        self.product_repo = product_repo
    
    async def create_product(
        self, 
        name: str, 
        price: Decimal, 
        category: str,
        description: Optional[str] = None,
        stock_quantity: int = 0
    ) -> Product:
        """Create a new product with business validation."""
        # Business rules validation
        if price <= 0:
            raise ValueError("Price must be positive")
        if len(name.strip()) < 2:
            raise ValueError("Product name must be at least 2 characters")
        if len(category.strip()) == 0:
            raise ValueError("Category is required")
            
        # Create domain entity
        product = Product(
            name=name.strip(),
            price=price,
            category=category.strip(),
            description=description.strip() if description else None,
            stock_quantity=stock_quantity
        )
        
        # Save via repository
        return self.product_repo.save(product)
    
    async def get_product(self, product_id: str) -> Optional[Product]:
        """Get a product by ID."""
        return self.product_repo.get(product_id)
    
    async def update_stock(self, product_id: str, new_quantity: int) -> Product:
        """Update product stock with business rules."""
        if new_quantity < 0:
            raise ValueError("Stock quantity cannot be negative")
            
        product = self.product_repo.get(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")
        
        # Apply business logic
        product.stock_quantity = new_quantity
        
        return self.product_repo.save(product)
    
    async def get_products_by_category(self, category: str) -> List[Product]:
        """Get all products in a category."""
        return self.product_repo.find_by_category(category)
    
    async def get_available_products(self) -> List[Product]:
        """Get all products that are active and in stock."""
        products = self.product_repo.list_active_products()
        return [p for p in products if p.is_in_stock()]


class OrderService:
    """Business service for order operations."""
    
    def __init__(self, product_service: ProductService):
        self.product_service = product_service
    
    async def validate_order_items(self, product_ids: List[str], quantities: List[int]) -> List[Product]:
        """Validate that all products exist and are available."""
        if len(product_ids) != len(quantities):
            raise ValueError("Product IDs and quantities must have same length")
            
        products = []
        for product_id, quantity in zip(product_ids, quantities):
            product = await self.product_service.get_product(product_id)
            if not product:
                raise ValueError(f"Product {product_id} not found")
            
            if not product.can_fulfill_order(quantity):
                raise ValueError(f"Insufficient stock for product {product.name}")
            
            products.append(product)
        
        return products
    
    async def calculate_total(self, products: List[Product], quantities: List[int]) -> Decimal:
        """Calculate order total with business rules."""
        total = Decimal('0.00')
        
        for product, quantity in zip(products, quantities):
            line_total = product.price * quantity
            total += line_total
        
        # Apply business rules (minimum order, etc.)
        if total < Decimal('0.01'):
            raise ValueError("Order total too low")
            
        return total
```

### 3. Create API Router

Add HTTP endpoints in `your_package/app/api/routers/business.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from decimal import Decimal

from your_package.app.entities.service.product import Product, ProductRepository
from your_package.app.service import ProductService, OrderService
from your_package.app.api.http.deps import get_current_user

router = APIRouter(prefix="/api/v1", tags=["business"])

# Dependency injection with repository pattern
def get_product_service() -> ProductService:
    """Get configured ProductService with repository."""
    product_repo = ProductRepository()
    return ProductService(product_repo)

def get_order_service() -> OrderService: 
    """Get configured OrderService with dependencies."""
    product_service = get_product_service()
    return OrderService(product_service)

@router.post("/products", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_product(
    name: str,
    price: Decimal,
    category: str,
    description: Optional[str] = None,
    stock_quantity: int = 0,
    product_service: ProductService = Depends(get_product_service),
    current_user = Depends(get_current_user)
):
    """Create a new product."""
    try:
        product = await product_service.create_product(
            name=name,
            price=price, 
            category=category,
            description=description,
            stock_quantity=stock_quantity
        )
        return {"id": product.id, "message": "Product created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/products/{product_id}", response_model=dict)
async def get_product(
    product_id: str,
    product_service: ProductService = Depends(get_product_service),
    current_user = Depends(get_current_user)
):
    """Get product by ID."""
    product = await product_service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return {
        "id": product.id,
        "name": product.name,
        "price": str(product.price),
        "category": product.category,
        "description": product.description,
        "stock_quantity": product.stock_quantity,
        "is_active": product.is_active,
        "created_at": product.created_at.isoformat(),
        "updated_at": product.updated_at.isoformat()
    }

@router.get("/products", response_model=List[dict])
async def list_products(
    category: Optional[str] = None,
    available_only: bool = False,
    product_service: ProductService = Depends(get_product_service),
    current_user = Depends(get_current_user)
):
    """List products with filtering."""
    try:
        if category:
            products = await product_service.get_products_by_category(category)
        elif available_only:
            products = await product_service.get_available_products()
        else:
            # Would need a list_all method in service
            products = []
        
        return [
            {
                "id": p.id,
                "name": p.name,
                "price": str(p.price),
                "category": p.category,
                "stock_quantity": p.stock_quantity,
                "is_active": p.is_active
            }
            for p in products
        ]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/products/{product_id}/stock", response_model=dict)
async def update_product_stock(
    product_id: str,
    new_quantity: int,
    product_service: ProductService = Depends(get_product_service),
    current_user = Depends(get_current_user)
):
    """Update product stock quantity."""
    try:
        product = await product_service.update_stock(product_id, new_quantity)
        return {
            "id": product.id,
            "name": product.name,
            "new_stock": product.stock_quantity,
            "message": "Stock updated successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

## 🔧 Development Commands

The template includes a rich CLI for development tasks:

```bash
# Entity management
uv run your-project-dev entity add Product    # Add new entity
uv run your-project-dev entity ls             # List entities  
uv run your-project-dev entity rm Product     # Remove entity

# Development environment
uv run your-project-dev dev start-dev-env     # Start Keycloak + PostgreSQL
uv run your-project-dev dev start-server      # Start API server
uv run your-project-dev dev --help            # Show all dev commands

# Database operations
uv run init-db                                 # Initialize database

# Testing
pytest                                         # Run test suite
pytest -v tests/unit/                         # Run unit tests only
pytest --cov                                  # Run with coverage

# Code quality  
ruff check .                                   # Lint code
ruff format .                                  # Format code
mypy .                                        # Type checking
```

## 🔐 Authentication Integration

The template provides a complete authentication system with a Backend-for-Frontend (BFF) pattern.

### Using the Auth BFF Endpoint

Your frontend applications can authenticate users through the `/auth/web/` endpoints:

```javascript
// 1. Redirect user to start OIDC login flow
window.location.href = '/auth/web/login';

// 2. After successful login, user is redirected back to your app
// Check authentication status
const response = await fetch('/auth/web/me', {
  credentials: 'include'  // Important: include session cookies
});

if (response.ok) {
  const user = await response.json();
  console.log('Authenticated user:', user);
  // User object contains: id, email, name, roles, etc.
} else {
  console.log('User not authenticated');
}

// 3. Make authenticated API calls
const apiResponse = await fetch('/api/v1/products', {
  credentials: 'include'  // Session cookie automatically included
});

// 4. Logout
await fetch('/auth/web/logout', { 
  method: 'POST',
  credentials: 'include' 
});
```

### Available Auth Endpoints

- `GET /auth/web/login` - Initiate OIDC authentication flow
- `GET /auth/web/callback` - Handle OIDC callback (automatic redirect)  
- `GET /auth/web/me` - Get current user information
- `POST /auth/web/logout` - End user session
- `POST /auth/web/refresh` - Refresh authentication tokens

### Frontend Integration Examples

**React/Next.js:**
```typescript
// hooks/useAuth.ts
export function useAuth() {
  const [user, setUser] = useState(null);
  
  useEffect(() => {
    fetch('/auth/web/me', { credentials: 'include' })
      .then(res => res.ok ? res.json() : null)
      .then(setUser);
  }, []);
  
  const login = () => window.location.href = '/auth/web/login';
  const logout = () => fetch('/auth/web/logout', { method: 'POST', credentials: 'include' });
  
  return { user, login, logout };
}
```

**Vue.js:**
```javascript  
// composables/useAuth.js
export function useAuth() {
  const user = ref(null);
  
  const checkAuth = async () => {
    try {
      const response = await $fetch('/auth/web/me', { credentials: 'include' });
      user.value = response;
    } catch {
      user.value = null;
    }
  };
  
  const login = () => window.location.href = '/auth/web/login';
  const logout = async () => {
    await $fetch('/auth/web/logout', { method: 'POST', credentials: 'include' });
    user.value = null;
  };
  
  return { user: readonly(user), checkAuth, login, logout };
}
```

## 🔄 Template Updates

Keep your project up-to-date with template improvements using Cruft:

```bash
# Check for template updates
cruft check

# Apply template updates  
cruft update

# View differences before updating
cruft diff
```

## 🧪 Testing

The template includes comprehensive testing infrastructure:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=your_package --cov-report=html

# Run specific test categories
pytest tests/unit/           # Unit tests
pytest tests/integration/    # Integration tests  
pytest tests/e2e/           # End-to-end tests

# Run tests matching pattern
pytest -k "test_auth"       # Only auth-related tests

# Verbose output
pytest -v -s               # Show print statements
```

## 📝 Configuration

Key configuration files:

- `.env` - Environment variables (database, auth, etc.)
- `pyproject.toml` - Python project configuration
- `dev_env/docker-compose.yml` - Development services
- `dev_env/keycloak-data/` - Keycloak configuration

### Essential Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/dbname
# or for development:  
DATABASE_URL=sqlite:///./database.db

# Authentication
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret  
OIDC_DISCOVERY_URL=http://localhost:8080/realms/master/.well-known/openid_configuration

# Session Security
SESSION_SECRET_KEY=your-secret-key-here
SESSION_COOKIE_DOMAIN=localhost

# Redis (optional, for rate limiting)
REDIS_URL=redis://localhost:6379

# Environment
ENVIRONMENT=development  # development|production|test
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`  
3. Make your changes with tests
4. Run the full test suite: `pytest`
5. Submit a pull request

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
