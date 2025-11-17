# FastAPI Clean Architecture Overview

Learn how API Forge implements Clean Architecture principles in FastAPI applications with clear separation between entities, repositories, services, and API layers. This guide explains the layered architecture pattern that makes your FastAPI codebase maintainable, testable, and scalable.

## Overview

API Forge follows Clean Architecture (also known as Hexagonal Architecture or Ports and Adapters) to organize your FastAPI application code. This architecture provides:

- **Clear separation of concerns** - Business logic independent of framework details
- **Testability** - Each layer can be tested in isolation
- **Flexibility** - Easy to swap implementations (database, external services)
- **Maintainability** - Changes in one layer don't cascade to others
- **Domain-driven design** - Business logic at the core
- **Dependency inversion** - High-level modules don't depend on low-level details

The architecture is organized in concentric layers, with business logic at the center and infrastructure at the edges.

## Architecture Layers

```
┌─────────────────────────────────────────────────────┐
│                   API Layer                         │
│  (FastAPI routes, dependencies, request/response)   │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│                 Service Layer                       │
│    (Business logic, orchestration, use cases)       │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│              Repository Layer                       │
│         (Data access, persistence)                  │
└────────────────┬────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────┐
│                Entity Layer                         │
│        (Domain models, business rules)              │
└─────────────────────────────────────────────────────┘
```

Dependencies flow **inward**: outer layers depend on inner layers, never the reverse.

## Directory Structure

```
src/
└── app/
    ├── entities/                  # Domain models
    │   └── user/
    │       ├── __init__.py
    │       ├── model.py           # SQLModel entities
    │       ├── repository.py      # Data access interface
    │       ├── service.py         # Business logic
    │       └── router.py          # FastAPI endpoints
    │
    ├── core/                      # Shared infrastructure
    │   ├── database.py            # Database connection
    │   ├── auth/                  # Authentication
    │   ├── services/              # Core services (OIDC, JWT, sessions)
    │   └── security.py            # Security utilities
    │
    ├── api/                       # HTTP layer
    │   └── http/
    │       ├── app.py             # FastAPI application
    │       ├── deps.py            # Dependency injection
    │       └── middleware.py      # HTTP middleware
    │
    └── runtime/                   # Application runtime
        ├── config/                # Configuration
        └── init_db.py             # Database initialization
```

## Entity Layer

### Purpose

The **Entity Layer** contains pure business logic and domain models. Entities are:
- Independent of frameworks and databases
- Contain business rules and validation
- Represent core domain concepts
- SQLModel models for ORM mapping

### Example: User Entity

```python
# src/app/entities/user/model.py
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel

class UserBase(SQLModel):
    """Base user model with common fields"""
    email: str = Field(unique=True, index=True, max_length=255)
    full_name: Optional[str] = Field(default=None, max_length=255)
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)

class User(UserBase, table=True):
    """Database user model"""
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def is_verified(self) -> bool:
        """Business rule: user verification check"""
        return self.is_active and self.email_verified
    
    def can_perform_action(self, action: str) -> bool:
        """Business rule: permission check"""
        if self.is_superuser:
            return True
        return action in self.permissions

class UserCreate(UserBase):
    """Schema for creating users"""
    password: str = Field(min_length=8)

class UserRead(UserBase):
    """Schema for reading users (no password)"""
    id: int
    created_at: datetime
    updated_at: datetime

class UserUpdate(SQLModel):
    """Schema for updating users"""
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
```

**Key Principles**:
- Separate schemas for create/read/update operations
- Business rules as methods on the entity
- No framework dependencies (except SQLModel for ORM)
- Validation at the model level

## Repository Layer

### Purpose

The **Repository Layer** handles data persistence and retrieval. Repositories:
- Abstract database operations
- Provide a clean interface for data access
- Hide implementation details (SQL, ORM)
- Can be easily mocked for testing

### Example: User Repository

```python
# src/app/entities/user/repository.py
from typing import Optional, List
from sqlmodel import Session, select
from .model import User, UserCreate, UserUpdate

class UserRepository:
    """Repository for user data access"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, user_data: UserCreate) -> User:
        """Create a new user"""
        from src.app.core.security import get_password_hash
        
        user = User(
            email=user_data.email,
            full_name=user_data.full_name,
            hashed_password=get_password_hash(user_data.password),
            is_active=user_data.is_active,
            is_superuser=user_data.is_superuser,
        )
        
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user
    
    def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return self.session.get(User, user_id)
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        statement = select(User).where(User.email == email)
        return self.session.exec(statement).first()
    
    def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None
    ) -> List[User]:
        """List users with filters"""
        statement = select(User)
        
        if is_active is not None:
            statement = statement.where(User.is_active == is_active)
        
        statement = statement.offset(skip).limit(limit)
        return list(self.session.exec(statement).all())
    
    def update(self, user: User, user_data: UserUpdate) -> User:
        """Update user"""
        from src.app.core.security import get_password_hash
        
        update_data = user_data.model_dump(exclude_unset=True)
        
        if "password" in update_data:
            hashed_password = get_password_hash(update_data.pop("password"))
            update_data["hashed_password"] = hashed_password
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user
    
    def delete(self, user: User) -> None:
        """Delete user"""
        self.session.delete(user)
        self.session.commit()
    
    def exists(self, email: str) -> bool:
        """Check if user exists by email"""
        statement = select(User.id).where(User.email == email)
        return self.session.exec(statement).first() is not None
```

**Key Principles**:
- All database operations go through repository
- Repository methods return domain models (User), not SQLModel query objects
- Clear method names describing intent
- Repository receives Session via dependency injection

## Service Layer

### Purpose

The **Service Layer** contains application business logic and orchestrates use cases. Services:
- Coordinate between repositories and external services
- Implement complex business workflows
- Handle transactions across multiple repositories
- Contain validation and business rules
- Raise domain-specific exceptions

### Example: User Service

```python
# src/app/entities/user/service.py
from typing import Optional, List
from fastapi import HTTPException, status
from .model import User, UserCreate, UserUpdate, UserRead
from .repository import UserRepository

class UserService:
    """Service for user business logic"""
    
    def __init__(self, repository: UserRepository):
        self.repository = repository
    
    def create_user(self, user_data: UserCreate) -> UserRead:
        """
        Create a new user with business validation
        """
        # Business rule: check if email already exists
        if self.repository.exists(user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Business rule: validate email domain (example)
        if not self._is_allowed_email_domain(user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email domain not allowed"
            )
        
        user = self.repository.create(user_data)
        
        # Additional business logic: send welcome email
        self._send_welcome_email(user)
        
        return UserRead.model_validate(user)
    
    def get_user(self, user_id: int) -> UserRead:
        """Get user by ID"""
        user = self.repository.get_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserRead.model_validate(user)
    
    def get_user_by_email(self, email: str) -> Optional[UserRead]:
        """Get user by email"""
        user = self.repository.get_by_email(email)
        return UserRead.model_validate(user) if user else None
    
    def list_users(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None
    ) -> List[UserRead]:
        """List users with pagination"""
        users = self.repository.list(skip=skip, limit=limit, is_active=is_active)
        return [UserRead.model_validate(user) for user in users]
    
    def update_user(self, user_id: int, user_data: UserUpdate) -> UserRead:
        """Update user with validation"""
        user = self.repository.get_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Business rule: prevent email change to existing email
        if user_data.email and user_data.email != user.email:
            if self.repository.exists(user_data.email):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use"
                )
        
        updated_user = self.repository.update(user, user_data)
        return UserRead.model_validate(updated_user)
    
    def delete_user(self, user_id: int) -> None:
        """Delete user"""
        user = self.repository.get_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Business rule: prevent deletion of superusers
        if user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete superuser"
            )
        
        self.repository.delete(user)
    
    def activate_user(self, user_id: int) -> UserRead:
        """Activate a user account"""
        user = self.repository.get_by_id(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if user.is_active:
            return UserRead.model_validate(user)
        
        user_data = UserUpdate(is_active=True)
        updated_user = self.repository.update(user, user_data)
        
        # Send activation email
        self._send_activation_email(updated_user)
        
        return UserRead.model_validate(updated_user)
    
    # Private helper methods
    def _is_allowed_email_domain(self, email: str) -> bool:
        """Check if email domain is allowed"""
        allowed_domains = ["example.com", "company.com"]
        domain = email.split("@")[-1]
        return domain in allowed_domains or not allowed_domains
    
    def _send_welcome_email(self, user: User) -> None:
        """Send welcome email to new user"""
        # Would integrate with email service
        pass
    
    def _send_activation_email(self, user: User) -> None:
        """Send activation confirmation email"""
        # Would integrate with email service
        pass
```

**Key Principles**:
- Services coordinate repositories, don't access database directly
- Business validation happens in services
- Services return schema objects (UserRead), not entities
- Complex workflows and orchestration live here
- Services are where cross-cutting concerns are handled

## API Layer (Router)

### Purpose

The **API Layer** exposes HTTP endpoints using FastAPI. Routers:
- Define HTTP routes and methods
- Handle request/response serialization
- Use dependency injection for services
- Implement API-specific concerns (authentication, rate limiting)
- Minimal business logic (delegated to services)

### Example: User Router

```python
# src/app/entities/user/router.py
from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from src.app.api.http.deps import get_db, get_current_active_user
from .model import User, UserCreate, UserRead, UserUpdate
from .repository import UserRepository
from .service import UserService

router = APIRouter(prefix="/users", tags=["users"])

def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """Dependency to get user service"""
    repository = UserRepository(db)
    return UserService(repository)

@router.post(
    "/",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    description="Register a new user account with email and password"
)
async def create_user(
    user_data: UserCreate,
    service: UserService = Depends(get_user_service)
) -> UserRead:
    """Create a new user"""
    return service.create_user(user_data)

@router.get(
    "/",
    response_model=List[UserRead],
    summary="List users",
    description="Get a paginated list of users"
)
async def list_users(
    skip: int = Query(0, ge=0, description="Number of users to skip"),
    limit: int = Query(100, ge=1, le=100, description="Max users to return"),
    is_active: bool = Query(None, description="Filter by active status"),
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_active_user)
) -> List[UserRead]:
    """List users (requires authentication)"""
    return service.list_users(skip=skip, limit=limit, is_active=is_active)

@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get user by ID",
    description="Retrieve a specific user by their ID"
)
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_active_user)
) -> UserRead:
    """Get a single user"""
    return service.get_user(user_id)

@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update user",
    description="Update user information"
)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_active_user)
) -> UserRead:
    """Update a user"""
    # Business rule: users can only update themselves unless superuser
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user"
        )
    
    return service.update_user(user_id, user_data)

@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description="Delete a user account"
)
async def delete_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_active_user)
) -> None:
    """Delete a user"""
    # Business rule: users can only delete themselves unless superuser
    if user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this user"
        )
    
    service.delete_user(user_id)

@router.post(
    "/{user_id}/activate",
    response_model=UserRead,
    summary="Activate user",
    description="Activate a user account (superuser only)"
)
async def activate_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_active_user)
) -> UserRead:
    """Activate a user (admin only)"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can activate users"
        )
    
    return service.activate_user(user_id)
```

**Key Principles**:
- Routers handle HTTP concerns only
- Business logic delegated to services
- Use dependency injection for services and authentication
- Clear OpenAPI documentation with summaries and descriptions
- Authorization checks in router (API concern)
- Validation at Pydantic schema level

## Dependency Injection

### Core Dependencies

```python
# src/app/api/http/deps.py
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlmodel import Session

from src.app.core.database import engine
from src.app.core.services.jwt_service import JWTService
from src.app.entities.user.model import User
from src.app.entities.user.repository import UserRepository

security = HTTPBearer()

def get_db() -> Generator[Session, None, None]:
    """Database session dependency"""
    with Session(engine) as session:
        yield session

def get_jwt_service() -> JWTService:
    """JWT service dependency"""
    from src.app.runtime.config import get_config
    config = get_config()
    return JWTService(config.jwt)

def get_current_user(
    token: str = Depends(security),
    db: Session = Depends(get_db),
    jwt_service: JWTService = Depends(get_jwt_service)
) -> User:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Decode JWT token
    payload = jwt_service.verify_token(token.credentials)
    if not payload:
        raise credentials_exception
    
    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception
    
    # Get user from database
    repository = UserRepository(db)
    user = repository.get_by_id(int(user_id))
    
    if user is None:
        raise credentials_exception
    
    return user

def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

def get_current_superuser(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current superuser"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough privileges"
        )
    return current_user
```

## Testing Each Layer

### Entity Tests (Unit Tests)

```python
# tests/unit/entities/user/test_model.py
from src.app.entities.user.model import User

def test_user_is_verified():
    user = User(email="test@example.com", is_active=True, email_verified=True)
    assert user.is_verified() is True
    
def test_user_not_verified_inactive():
    user = User(email="test@example.com", is_active=False, email_verified=True)
    assert user.is_verified() is False
```

### Repository Tests (Integration Tests)

```python
# tests/integration/entities/user/test_repository.py
import pytest
from sqlmodel import Session
from src.app.entities.user.model import UserCreate
from src.app.entities.user.repository import UserRepository

def test_create_user(db_session: Session):
    repository = UserRepository(db_session)
    user_data = UserCreate(email="test@example.com", password="password123")
    
    user = repository.create(user_data)
    
    assert user.id is not None
    assert user.email == "test@example.com"

def test_get_by_email(db_session: Session):
    repository = UserRepository(db_session)
    user_data = UserCreate(email="test@example.com", password="password123")
    
    created_user = repository.create(user_data)
    found_user = repository.get_by_email("test@example.com")
    
    assert found_user is not None
    assert found_user.id == created_user.id
```

### Service Tests (Unit Tests with Mocks)

```python
# tests/unit/entities/user/test_service.py
import pytest
from unittest.mock import Mock
from fastapi import HTTPException
from src.app.entities.user.model import UserCreate
from src.app.entities.user.service import UserService

def test_create_user_success():
    # Mock repository
    repository = Mock()
    repository.exists.return_value = False
    repository.create.return_value = Mock(id=1, email="test@example.com")
    
    service = UserService(repository)
    user_data = UserCreate(email="test@example.com", password="password123")
    
    result = service.create_user(user_data)
    
    assert result.email == "test@example.com"
    repository.create.assert_called_once()

def test_create_user_duplicate_email():
    # Mock repository
    repository = Mock()
    repository.exists.return_value = True
    
    service = UserService(repository)
    user_data = UserCreate(email="test@example.com", password="password123")
    
    with pytest.raises(HTTPException) as exc:
        service.create_user(user_data)
    
    assert exc.value.status_code == 400
    assert "already registered" in exc.value.detail
```

### Router Tests (Integration Tests)

```python
# tests/integration/api/test_user_router.py
from fastapi.testclient import TestClient

def test_create_user(client: TestClient):
    response = client.post(
        "/users/",
        json={"email": "test@example.com", "password": "password123"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data

def test_list_users_requires_auth(client: TestClient):
    response = client.get("/users/")
    assert response.status_code == 401
```

## Generating New Entities with CLI

API Forge includes a CLI tool to generate entity scaffolding:

```bash
# Generate a new entity (e.g., Product)
uv run api-forge-cli entity add Product

# CLI prompts for fields:
# Field name: name
# Field type: str
# Required? (y/n): y
# 
# Field name: price
# Field type: float
# Required? (y/n): y
# 
# Field name: description
# Field type: str
# Required? (y/n): n
# 
# Add another field? (y/n): n

# Generates:
# src/app/entities/product/
#   ├── __init__.py
#   ├── model.py       # Product, ProductCreate, ProductRead, ProductUpdate
#   ├── repository.py  # ProductRepository
#   ├── service.py     # ProductService
#   └── router.py      # Product API endpoints
```

The generated entity follows all Clean Architecture principles and is ready to use.

## Benefits of This Architecture

### 1. Testability

Each layer can be tested independently:
- **Entities**: Pure unit tests of business rules
- **Repositories**: Integration tests with real database
- **Services**: Unit tests with mocked repositories
- **Routers**: Integration tests with TestClient

### 2. Flexibility

Easy to swap implementations:
- Change from PostgreSQL to MongoDB (update repositories)
- Add Redis caching (update services)
- Switch from REST to GraphQL (new router layer)

### 3. Maintainability

Clear boundaries between layers:
- Business logic changes don't affect API
- Database changes don't affect services
- Each layer has single responsibility

### 4. Scalability

As application grows:
- Add new entities without affecting existing ones
- Services can be extracted to microservices
- Repositories can be distributed across databases

## Common Patterns

### Transaction Management

Handle transactions in services:

```python
def transfer_funds(self, from_user_id: int, to_user_id: int, amount: float):
    """Transfer funds between users (transactional)"""
    # Both operations happen in same transaction (same session)
    from_user = self.repository.get_by_id(from_user_id)
    to_user = self.repository.get_by_id(to_user_id)
    
    if from_user.balance < amount:
        raise HTTPException(400, "Insufficient funds")
    
    from_user.balance -= amount
    to_user.balance += amount
    
    self.repository.update(from_user, UserUpdate(balance=from_user.balance))
    self.repository.update(to_user, UserUpdate(balance=to_user.balance))
    
    # Both updates committed together
```

### Cross-Entity Operations

Services can coordinate multiple repositories:

```python
class OrderService:
    def __init__(self, order_repo: OrderRepository, product_repo: ProductRepository):
        self.order_repo = order_repo
        self.product_repo = product_repo
    
    def create_order(self, user_id: int, product_id: int):
        """Create order and update product inventory"""
        product = self.product_repo.get_by_id(product_id)
        
        if product.inventory < 1:
            raise HTTPException(400, "Product out of stock")
        
        order = self.order_repo.create(OrderCreate(user_id=user_id, product_id=product_id))
        
        product.inventory -= 1
        self.product_repo.update(product, ProductUpdate(inventory=product.inventory))
        
        return order
```

### Background Tasks

Use Temporal workflows for async operations:

```python
class UserService:
    def create_user(self, user_data: UserCreate) -> UserRead:
        user = self.repository.create(user_data)
        
        # Trigger background workflow
        from src.app.worker.workflows import SendWelcomeEmailWorkflow
        temporal_client.start_workflow(
            SendWelcomeEmailWorkflow.run,
            args=[user.id, user.email],
            id=f"welcome-email-{user.id}",
            task_queue="email"
        )
        
        return UserRead.model_validate(user)
```

## Anti-Patterns to Avoid

❌ **Accessing database directly from routers**:
```python
# BAD
@router.get("/users/{user_id}")
async def get_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)  # Don't do this!
    return user
```

✅ **Use services instead**:
```python
# GOOD
@router.get("/users/{user_id}")
async def get_user(user_id: int, service: UserService = Depends(get_user_service)):
    return service.get_user(user_id)
```

❌ **Business logic in routers**:
```python
# BAD
@router.post("/users/")
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(400, "Email exists")  # Business logic in router!
    ...
```

✅ **Business logic in services**:
```python
# GOOD - in service
def create_user(self, user_data: UserCreate):
    if self.repository.exists(user_data.email):
        raise HTTPException(400, "Email exists")  # Business logic in service
    ...
```

❌ **Services depending on outer layers**:
```python
# BAD
class UserService:
    def create_user(self, request: Request):  # Depends on FastAPI Request!
        ...
```

✅ **Services depend only on inner layers**:
```python
# GOOD
class UserService:
    def create_user(self, user_data: UserCreate):  # Depends on domain model
        ...
```

## Related Documentation

- [FastAPI Testing Strategy](./fastapi-testing-strategy.md) - Testing each architecture layer
- [FastAPI Temporal Workflows](./fastapi-temporal-workflows.md) - Async operations from services
- [Getting Started Guide](./index.md) - Overview and quick start

## Additional Resources

- [Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [Domain-Driven Design](https://martinfowler.com/bliki/DomainDrivenDesign.html)
- [FastAPI Bigger Applications Guide](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
