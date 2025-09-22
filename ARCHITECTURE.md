# Architecture Documentation

## Clean Architecture with Hexagonal Principles

This template implements clean architecture with hexagonal principles for separation of concerns and dependency inversion:

- **Core**: Domain entities and business logic with minimal external dependencies
- **Application**: Application services that orchestrate domain logic and implement use cases  
- **Infrastructure**: External concerns (HTTP, database, frameworks)

**Important Note**: While inspired by hexagonal architecture, this template makes pragmatic compromises for development velocity. Domain entities inherit from SQLModel for convenience, which couples the domain to the ORM framework. This is a deliberate trade-off between architectural purity and practical development speed.

## Design Principles

- **Dependency Inversion**: Dependencies point inward toward the domain
- **Interface Segregation**: Small, focused interfaces
- **Single Responsibility**: Each layer has a clear purpose
- **Open/Closed**: Extend functionality without modifying existing code
- **Pragmatic Compromises**: Balance architectural principles with development velocity

## Generated Project Structure

```
your-project/
├── .cruft.json                 # Template tracking (Cruft)
├── .env.example               # Environment template
├── .github/workflows/          # CI/CD pipelines
├── main.py                    # FastAPI app entry point
├── pyproject.toml             # Dependencies & project config
├── your_package/              # Main application package
│   ├── api/http/              # HTTP API layer
│   │   ├── app.py            # FastAPI application factory
│   │   ├── deps.py           # Dependency injection
│   │   ├── middleware/       # Security, CORS, rate limiting
│   │   ├── routers/          # API route handlers
│   │   └── schemas/          # Pydantic request/response models
│   ├── application/          # Application service layer
│   ├── business/             # Business domain layer
│   ├── core/                 # Domain/core business logic
│   └── runtime/              # Infrastructure & configuration
└── tests/                    # Comprehensive test suite
```

## Extending Your Project

### Adding New Features

1. **Define Domain Entity** (`core/entities/`):
   ```python
   from core.entities._base import Entity
   
   class Product(Entity):
       id: int
       name: str
       price: Decimal
   ```
   
   *Note: Entities inherit from SQLModel for ORM integration - a pragmatic compromise.*

2. **Create Repository Interface** (`core/repositories/`):
   ```python
   from abc import ABC, abstractmethod
   
   class ProductRepository(ABC):
       @abstractmethod
       def get(self, product_id: int) -> Optional[Product]:
           pass
   ```

3. **Implement Persistence** (`core/rows/` and `core/repositories/`):
   ```python
   # Database model (in core/rows/)
   class ProductRow(SQLModel, table=True): ...
   
   # Repository implementation (in core/repositories/)
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

## Configuration Management

Environment variables are managed through Pydantic Settings:

```python
# runtime/settings.py
class Settings(BaseSettings):
    new_feature_enabled: bool = False
    api_key: str = Field(..., env="MY_API_KEY")
```

## Architectural Decisions & Trade-offs

### Pragmatic Compromises Made

1. **SQLModel Domain Entities**: Domain entities inherit from SQLModel instead of being pure POPOs (Plain Old Python Objects). This couples the domain to the ORM but significantly reduces boilerplate and mapping code.

2. **Repository Placement**: Repository implementations are in `core/repositories/` rather than a separate infrastructure layer. This simplifies the structure while maintaining separation of concerns.

3. **Mixed Layer Concerns**: The `core/` directory contains both pure domain concepts and infrastructure concerns (like `rows/` for database models).

### Benefits of These Compromises

- **Faster Development**: Less boilerplate code and mapping between layers
- **Type Safety**: Direct SQLModel integration provides better IDE support
- **Pragmatic Structure**: Easier to understand and navigate for most developers
- **Reduced Complexity**: Fewer abstraction layers mean simpler debugging

### When to Consider Pure Hexagonal

Consider moving to pure hexagonal architecture if you:
- Need to support multiple persistence technologies
- Have complex domain logic that changes frequently  
- Are building a large, long-term system with multiple teams
- Have strict requirements for technology independence

For most microservices and SaaS backends, this template's pragmatic approach provides the right balance of structure and velocity.

## Testing Strategy

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **E2E Tests**: Test complete user workflows