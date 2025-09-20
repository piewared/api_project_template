# Architecture Documentation

## Hexagonal Architecture

This template implements hexagonal architecture (ports and adapters) for clean separation of concerns:

- **Core**: Pure domain logic, no external dependencies
- **Application**: Orchestrates domain logic, implements use cases  
- **Infrastructure**: External concerns (HTTP, database, etc.)

## Design Principles

- **Dependency Inversion**: Dependencies point inward toward the domain
- **Interface Segregation**: Small, focused interfaces
- **Single Responsibility**: Each layer has a clear purpose
- **Open/Closed**: Extend functionality without modifying existing code

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

## Configuration Management

Environment variables are managed through Pydantic Settings:

```python
# runtime/settings.py
class Settings(BaseSettings):
    new_feature_enabled: bool = False
    api_key: str = Field(..., env="MY_API_KEY")
```

## Testing Strategy

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **E2E Tests**: Test complete user workflows