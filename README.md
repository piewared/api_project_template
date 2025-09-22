# FastAPI Clean Architecture Template

⚠️ **Alpha Release**: This project is currently in alpha. While functional and tested, APIs and structure may change. Use in production at your own discretion and expect potential breaking changes.

A modern, production-ready [Cookiecutter](https://cookiecutter.readthedocs.io/) template for creating FastAPI applications with clean architecture and hexagonal principles. Build scalable REST APIs with built-in authentication, authorization, rate limiting, and automated template updates with [Cruft](https://python-basics-tutorial.readthedocs.io/en/latest/packs/templating/cruft.html).

## 🎯 Motivation

This project exists to **accelerate the development of production-enabled microservices and SaaS APIs** by providing all the necessary primitives, components, and architectural templates that adhere to industry best practices.

### Intended Use Cases

This template is specifically designed for:

✅ **User-to-Service Microservices** - Backend APIs that serve client applications (web, mobile, desktop)  
✅ **SaaS Backend Development** - Multi-tenant service APIs with authentication and rate limiting  
✅ **REST API Services** - Standalone API services that integrate with existing systems  
✅ **Microservice Architecture** - Individual services within a larger distributed system  
✅ **Backend-as-a-Service** - APIs that provide core functionality to frontend applications  

### ❌ What This Template Is NOT

This template is **not intended** for:

❌ **Full-Stack Applications** - Does not include frontend frameworks, UI components, or client-side code  
❌ **Monolithic Web Applications** - Not designed for traditional server-rendered web apps  
❌ **Turnkey Complete Solutions** - Requires integration with your chosen frontend and infrastructure  
❌ **All-in-One Platforms** - Focuses purely on API development, not complete application stacks  

**Focus**: This template excels at creating the **backend API layer** that powers modern applications, leaving frontend technology choices and infrastructure decisions to you.

### The Problem This Template Solves

Building production-ready APIs from scratch involves solving the same challenges repeatedly:
- **Authentication & Authorization**: JWT handling, role-based access control, security middleware
- **Architectural Decisions**: Clean separation of concerns, testable code structure
- **Infrastructure Integration**: Database connections, caching, rate limiting, health checks
- **Developer Experience**: Type safety, testing frameworks, documentation generation
- **Operational Readiness**: Monitoring, logging, error handling, graceful degradation

### The Solution Provided

Instead of rebuilding these foundational elements for every project, this template provides:

✅ **Complete API Primitives** - Authentication, rate limiting, database integration, and security middleware  
✅ **Clean Architecture** - Layered design with dependency inversion and separation of concerns  
✅ **Production Components** - Health checks, error handling, logging, and monitoring hooks  
✅ **Best Practices** - Type safety, comprehensive testing, documentation, and CI/CD pipelines  
✅ **Developer Velocity** - Skip the boilerplate and focus on your unique business logic  

**Result**: Transform weeks of setup and architectural decisions into minutes of configuration, allowing you to focus on building features that matter to your users.

## 🎯 Why Use This Template?

Create enterprise-grade FastAPI applications in minutes with:
- **Production-ready architecture** with clean separation of concerns
- **Complete authentication system** with JWT/OIDC support
- **Comprehensive testing** (62 tests) with CI/CD pipeline
- **Auto-updating template** to keep projects current
- **Type-safe codebase** with full Pydantic integration

Perfect for building microservices, REST APIs, and backend services that need to scale.

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+** (3.13 recommended)
- **[Cookiecutter](https://cookiecutter.readthedocs.io/en/latest/installation.html)**: `pip install cookiecutter`
- **[Cruft](https://cruft.github.io/cruft/)** (recommended): `pip install cruft`

### Create Your Project

#### Option 1: With Auto-Updates (Recommended)
```bash
# Create with update capabilities
cruft create https://github.com/piewared/api_template

# Follow interactive prompts
```

#### Option 2: Standard Generation
```bash
# One-time generation
cookiecutter https://github.com/piewared/api_template
```

#### Option 3: Non-Interactive
```bash
# Automated generation
cruft create https://github.com/piewared/api_template \
  --no-input \
  project_name="My API" \
  project_description="A FastAPI service" \
  author_name="Your Name" \
  author_email="you@example.com"
```

### Get Started with Your New Project

```bash
# Navigate to your project
cd your-project-name

# Project is ready! Dependencies installed, git initialized
# Configure environment
cp .env.example .env

# Initialize database
uv run init-db

# Start development server
uvicorn main:app --reload
```

Your API is ready at:
- **Application**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### Adding Your First Business Entity & API

Once your project is running, here's how to add your own business logic using the hybrid entity-centric structure:

#### 1. Create Entity Package Structure

```bash
# Create a new product entity package
mkdir -p your_package/entities/product
touch your_package/entities/product/__init__.py
touch your_package/entities/product/entity.py
touch your_package/entities/product/table.py
touch your_package/entities/product/repository.py
```

#### 2. Create Domain Entity

```python
# your_package/entities/product/entity.py
from decimal import Decimal
from pydantic import Field
from your_package.core.entities._base import Entity

class Product(Entity):
    """Product entity representing an item for sale.
    
    This is the domain model that contains business logic and validation.
    It inherits from Entity to get auto-generated UUID identifiers.
    """
    
    name: str = Field(description="Product name")
    price: Decimal = Field(description="Product price")
    description: str | None = Field(default=None, description="Product description")
    in_stock: bool = Field(default=True, description="Whether product is in stock")
```

#### 3. Create Database Table Model

```python
# your_package/entities/product/table.py
from decimal import Decimal
from sqlmodel import SQLModel, Field

class ProductTable(SQLModel, table=True):
    """Database persistence model for products.
    
    This represents how the Product entity is stored in the database.
    It's separate from the domain entity to maintain clean architecture
    while keeping related code together.
    """
    
    __tablename__ = "products"
    
    id: str = Field(primary_key=True)
    name: str = Field(max_length=255)
    price: Decimal = Field(decimal_places=2)
    description: str | None = Field(default=None, max_length=1000)
    in_stock: bool = Field(default=True)
```

#### 4. Create Repository

```python
# your_package/entities/product/repository.py
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

    def get(self, product_id: str) -> Product | None:
        """Get a product by ID."""
        row = self._session.get(ProductTable, product_id)
        if row is None:
            return None
        return Product.model_validate(row, from_attributes=True)

    def create(self, product: Product) -> Product:
        """Create a new product and return it. ID is auto-generated by the entity."""
        row = ProductTable.model_validate(product, from_attributes=True)
        self._session.add(row)
        return product  # No need for flush/refresh - entity already has its ID!

    def list(self, in_stock_only: bool = False) -> list[Product]:
        """List all products, optionally filtering by stock status."""
        query = select(ProductTable)
        if in_stock_only:
            query = query.where(ProductTable.in_stock == True)
        
        rows = self._session.exec(query).all()
        return [Product.model_validate(row, from_attributes=True) for row in rows]
```

#### 5. Create Package Exports

```python
# your_package/entities/product/__init__.py
"""Product entity module.

This module contains all Product-related classes organized by responsibility:
- Product: Domain entity with business logic
- ProductTable: Database persistence model  
- ProductRepository: Data access layer

This structure keeps all Product-related code together while maintaining
separation of concerns within the module.
"""

from .entity import Product
from .repository import ProductRepository
from .table import ProductTable

__all__ = ["Product", "ProductTable", "ProductRepository"]
```

#### 6. Create API Router

```python
# your_package/api/http/routers/products.py
from fastapi import APIRouter, Depends
from sqlmodel import Session

from your_package.entities.product import Product, ProductRepository
from your_package.runtime.db import get_session

router = APIRouter(prefix="/products", tags=["products"])

@router.get("/{product_id}")
def get_product(
    product_id: str,
    session: Session = Depends(get_session)
) -> Product:
    """Get a product by ID."""
    repo = ProductRepository(session)
    product = repo.get(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@router.post("/")
def create_product(
    product_data: dict,  # In real apps, use Pydantic models for input validation
    session: Session = Depends(get_session)
) -> Product:
    """Create a new product."""
    repo = ProductRepository(session)
    product = Product(**product_data)  # Auto-generates UUID
    return repo.create(product)

```

This clean structure keeps everything organized while being easy to use and test.

## ⚙️ Configuration Options
```

#### 4. Create API Schemas

```python
# your_package/api/http/schemas/product.py
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict

class ProductCreate(BaseModel):
    name: str
    price: Decimal
    description: Optional[str] = None
    in_stock: bool = True

class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    price: Decimal
    description: Optional[str]
    in_stock: bool

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[Decimal] = None
    description: Optional[str] = None
    in_stock: Optional[bool] = None
```

#### 5. Create API Router

```python
# your_package/api/http/routers/products.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from your_package.api.http.deps import get_session, get_current_user
from your_package.api.http.schemas.product import ProductCreate, ProductRead, ProductUpdate
from your_package.core.repositories.product_repo import ProductRepository
from your_package.core.entities.user import User

router = APIRouter()

def get_product_repo(db: Session = Depends(get_session)) -> ProductRepository:
    return ProductRepository(db)

@router.get("/", response_model=List[ProductRead])
async def list_products(
    in_stock_only: bool = False,
    repo: ProductRepository = Depends(get_product_repo)
):
    """List all products, optionally filtering to in-stock items only."""
    return repo.list(in_stock_only=in_stock_only)

@router.post("/", response_model=ProductRead)
async def create_product(
    product_data: ProductCreate,
    repo: ProductRepository = Depends(get_product_repo),
    current_user: User = Depends(get_current_user)
):
    """Create a new product (requires authentication)."""
    product = Product(**product_data.model_dump())
    return repo.create(product)

@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: int,
    repo: ProductRepository = Depends(get_product_repo)
):
    """Get a specific product by ID."""
    product = repo.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
```

#### 6. Register the Router

```python
# Add to your_package/api/http/app.py (in the router registration section)
from your_package.api.http.routers import products

app.include_router(products.router, prefix="/api/products", tags=["products"])
```

#### 7. Update Database Schema

```bash
# Add the new table to your database
# Update your_package/runtime/init_db.py to include ProductRow
python -m your_package.runtime.init_db
```

#### 8. Test Your API

```bash
# List products
curl http://localhost:8000/api/products/

# Create a product (requires authentication in production)
curl -X POST http://localhost:8000/api/products/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Sample Product", "price": "29.99", "description": "A great product"}'

# Get product by ID
curl http://localhost:8000/api/products/1
```

**🎉 You now have a complete CRUD API following clean architecture principles!**

## ⚙️ Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `project_name` | Human-readable project name | "My API Project" |
| `project_slug` | URL/filesystem safe name | auto-generated |
| `project_description` | Brief project description | "A FastAPI service..." |
| `author_name` | Your name | "Your Name" |
| `author_email` | Your email | "you@example.com" |
| `version` | Initial version | "0.1.0" |
| `python_version` | Minimum Python version | "3.13" |
| `use_redis` | Include Redis rate limiting | "y" |
| `use_postgres` | Include PostgreSQL examples | "n" |
| `license` | License type | "MIT" |

## 🏗️ What's Included

Your generated project includes:

### Core Features
- ✅ **FastAPI application** with clean architecture and layered design
- ✅ **JWT/OIDC authentication** with role-based access control
- ✅ **SQLModel database** integration (SQLite default, PostgreSQL ready)
- ✅ **Redis rate limiting** with in-memory fallback
- ✅ **Security middleware** (CORS, HSTS, security headers)
- ✅ **Comprehensive testing** with 3 example tests ready to extend
- ✅ **GitHub Actions CI/CD** pipeline
- ✅ **Auto-documentation** with OpenAPI/Swagger

### Developer Tools
- 🔧 **Code quality**: Ruff (linting & formatting), MyPy (type checking)
- 🧪 **Testing**: pytest with async support and coverage
- 📦 **Dependencies**: uv for fast package management
- 🔄 **Template updates**: Cruft integration for staying current
- ⚙️ **Environment**: Pydantic Settings with .env support

### Project Structure
```
your-project/
├── main.py                    # FastAPI app entry point
├── your_package/
│   ├── api/http/             # HTTP layer (routes, middleware, schemas)
│   ├── core/                 # Domain logic (entities, services)
│   ├── application/          # Application services
│   ├── business/             # Business logic
│   └── runtime/              # Infrastructure (database, settings)
├── tests/                    # Test suite
├── .github/workflows/        # CI/CD
└── .env.example             # Environment template
```

## �️ Roadmap & Planned Features

We're continuously improving this template to provide the most comprehensive FastAPI development experience. Here's what's coming:

### 🔐 Enhanced Security & Authentication
- [ ] **Multi-Factor Authentication (MFA)** - TOTP and SMS-based 2FA support
- [ ] **OAuth2 Provider Templates** - Ready-to-use integration with Google, GitHub, Microsoft
- [ ] **API Key Management** - Built-in API key generation, rotation, and scoping
- [ ] **Advanced RBAC** - Fine-grained permissions with resource-based access control
- [ ] **Security Audit Logging** - Comprehensive audit trails for compliance requirements
- [ ] **Rate Limiting Strategies** - Multiple rate limiting algorithms (sliding window, token bucket)

### 📊 Observability & Monitoring
- [ ] **OpenTelemetry Integration** - Distributed tracing with Jaeger/Zipkin support
- [ ] **Prometheus Metrics** - Built-in application and business metrics collection
- [ ] **Health Check Dashboard** - Advanced health monitoring with dependency checks
- [ ] **Error Tracking** - Integration with Sentry, Rollbar, or Bugsnag
- [ ] **Performance Profiling** - Built-in APM with request profiling capabilities
- [ ] **Custom Alerting** - Configurable alerts for critical application events

### 🗄️ Database & Storage Enhancements
- [ ] **Database Migrations** - Alembic integration with automated migration workflows
- [ ] **Connection Pooling** - Advanced connection pool management and monitoring
- [ ] **Read/Write Splitting** - Automatic routing for read replicas and write masters
- [ ] **Caching Strategies** - Redis caching patterns with cache-aside, write-through
- [ ] **Event Sourcing Support** - Event store integration for audit and replay capabilities

### 🚀 Performance & Scalability
- [ ] **Async Task Processing** - Celery/RQ integration for background job processing
- [ ] **WebSocket Templates** - Real-time communication patterns and connection management
- [ ] **API Gateway Integration** - Kong, Ambassador, or Istio service mesh templates
- [ ] **Auto-scaling Configs** - Kubernetes HPA and Docker Swarm scaling configurations
- [ ] **Circuit Breaker Pattern** - Resilient external service integration

### 🧪 Testing & Quality Assurance
- [ ] **Contract Testing** - Pact-based consumer-driven contract testing
- [ ] **Load Testing Templates** - Locust and Artillery test scenarios
- [ ] **Mutation Testing** - Code quality validation with mutation testing tools
- [ ] **Security Testing** - OWASP ZAP integration for automated security scanning
- [ ] **Property-Based Testing** - Hypothesis integration for robust test generation
- [ ] **Visual Regression Testing** - Automated UI testing for API documentation

### 🏗️ Development Experience
- [ ] **IDE Integration** - VS Code/PyCharm project templates and debugging configs
- [ ] **Hot Reloading** - Advanced development server with instant API updates
- [ ] **API Versioning** - Built-in versioning strategies (header, URL, content negotiation)
- [ ] **Documentation Generation** - Enhanced OpenAPI docs with examples and tutorials
- [ ] **CLI Tools** - Project-specific CLI for common development tasks
- [ ] **Template Customization** - Plugin system for extending template functionality

### ☁️ Cloud & Deployment
- [ ] **Cloud Provider Templates** - AWS, GCP, Azure deployment configurations
- [ ] **Serverless Support** - AWS Lambda, Google Cloud Functions deployment options
- [ ] **Container Orchestration** - Advanced Kubernetes manifests with Helm charts
- [ ] **Infrastructure as Code** - Terraform/Pulumi modules for complete stack deployment
- [ ] **CI/CD Pipelines** - GitHub Actions, GitLab CI, Jenkins templates
- [ ] **Blue-Green Deployments** - Zero-downtime deployment strategies

### 🔌 Integration & Ecosystem
- [ ] **Message Queue Integration** - RabbitMQ, Apache Kafka, AWS SQS templates
- [ ] **External API Clients** - Type-safe client generation for common APIs
- [ ] **Webhook Handlers** - Secure webhook processing with signature validation
- [ ] **File Upload/Storage** - S3, MinIO, local storage with image processing
- [ ] **Email Service Integration** - SendGrid, Mailgun, AWS SES template configurations
- [ ] **Search Integration** - Elasticsearch, Solr, or Algolia search capabilities

### 🎯 Specialized Templates
- [ ] **E-commerce APIs** - Product catalog, cart, payment processing templates
- [ ] **Content Management** - CMS APIs with media handling and content workflows
- [ ] **IoT Data Processing** - Time-series data ingestion and processing patterns
- [ ] **Financial Services** - Payment processing, compliance, and audit-ready templates
- [ ] **Healthcare APIs** - HIPAA-compliant templates with data privacy features
- [ ] **Real-time Analytics** - Stream processing and dashboard APIs


## 🤝 Contributing to the Roadmap

Community input on the roadmap is welcome! Here's how you can contribute:

- **🗳️ Vote on Features**: Comment on [GitHub Issues](https://github.com/piewared/api_template/issues) with 👍 for features you want
- **💡 Suggest Features**: Open a feature request with detailed use cases
- **🔧 Submit PRs**: Help implement roadmap items or propose new ones
- **📖 Documentation**: Help improve docs and examples for new features
- **🧪 Beta Testing**: Test pre-release features and provide feedback

### Priority Levels
- **🔥 High Priority**: Core functionality improvements (Security, Performance, Testing)
- **⭐ Medium Priority**: Developer experience enhancements (IDE, CLI, Documentation)
- **💡 Future Exploration**: Advanced features (Specialized templates, BI features)

## �📚 Documentation

- **[Features](FEATURES.md)** - Complete feature list and capabilities
- **[Architecture](ARCHITECTURE.md)** - Hexagonal architecture details and design patterns
- **[Development](DEVELOPMENT.md)** - Contributing, template development, and deployment guide

## 🔄 Staying Updated

Generated projects automatically receive template updates:
- Weekly GitHub Action checks for updates
- Pull requests created with migration notes
- Manual updates: `cruft update`


## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/piewared/api_template/issues)
- **Discussions**: [GitHub Discussions](https://github.com/piewared/api_template/discussions)

## 📄 License

MIT License. Generated projects can use any license you specify.

---

**⭐ Star this repo** if it helped you build better APIs!