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

Add your domain entities in `your_package/app/entities/service/__init__.py`:

```python
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class Product:
    """Product domain entity."""
    id: str
    name: str
    price: float
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    
@dataclass  
class Order:
    """Order domain entity."""
    id: str
    customer_id: str
    products: list[Product]
    total: float
    status: str = "pending"
```

### 2. Implement Business Service

Add business logic in `your_package/app/service/__init__.py`:

```python
from typing import List
from ..entities.service import Product, Order

class ProductService:
    """Business service for product operations."""
    
    def __init__(self, product_repo, inventory_service):
        self.product_repo = product_repo
        self.inventory_service = inventory_service
    
    async def create_product(self, name: str, price: float, description: str = None) -> Product:
        """Create a new product with business validation."""
        # Business rules
        if price <= 0:
            raise ValueError("Price must be positive")
        if len(name.strip()) < 2:
            raise ValueError("Product name too short")
            
        product = Product(
            id=self.generate_product_id(),
            name=name.strip(),
            price=price,
            description=description
        )
        
        # Save via repository
        return await self.product_repo.save(product)
    
    def generate_product_id(self) -> str:
        """Generate unique product ID."""
        import uuid
        return f"prod_{uuid.uuid4().hex[:8]}"

class OrderService:
    """Business service for order operations."""
    
    def __init__(self, product_service, order_repo):
        self.product_service = product_service  
        self.order_repo = order_repo
    
    async def create_order(self, customer_id: str, product_ids: List[str]) -> Order:
        """Create order with business logic."""
        # Fetch products
        products = []
        for pid in product_ids:
            product = await self.product_service.get_product(pid)
            if not product:
                raise ValueError(f"Product {pid} not found")
            products.append(product)
        
        # Calculate total
        total = sum(p.price for p in products)
        
        # Apply business rules
        if total < 0.01:
            raise ValueError("Order total too low")
            
        order = Order(
            id=self.generate_order_id(),
            customer_id=customer_id,
            products=products,
            total=total
        )
        
        return await self.order_repo.save(order)
    
    def generate_order_id(self) -> str:
        import uuid
        return f"order_{uuid.uuid4().hex[:8]}"
```

### 3. Create API Router

Add HTTP endpoints in `your_package/app/api/routers/business.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from your_package.app.entities.service import Product, Order
from your_package.app.service import ProductService, OrderService
from your_package.app.api.http.deps import get_current_user

router = APIRouter(prefix="/api/v1", tags=["business"])

# Dependency injection (implement these based on your needs)
def get_product_service() -> ProductService:
    # Return configured ProductService instance
    pass

def get_order_service() -> OrderService: 
    # Return configured OrderService instance
    pass

@router.post("/products", response_model=Product)
async def create_product(
    name: str,
    price: float,
    description: str = None,
    product_service: ProductService = Depends(get_product_service),
    current_user = Depends(get_current_user)
):
    """Create a new product."""
    try:
        return await product_service.create_product(name, price, description)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/orders", response_model=Order)  
async def create_order(
    customer_id: str,
    product_ids: List[str],
    order_service: OrderService = Depends(get_order_service),
    current_user = Depends(get_current_user)
):
    """Create a new order."""
    try:
        return await order_service.create_order(customer_id, product_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/products/{product_id}", response_model=Product)
async def get_product(
    product_id: str,
    product_service: ProductService = Depends(get_product_service),
    current_user = Depends(get_current_user)
):
    """Get product by ID."""
    product = await product_service.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
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
