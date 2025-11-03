# PostgreSQL Usage Guide

## Overview

This guide provides practical code examples for working with PostgreSQL in this application, covering entity models, repositories, session management, and common database operations.

## Table of Contents

1. [Basic Setup](#basic-setup)
2. [Entity Models](#entity-models)
3. [Repository Pattern](#repository-pattern)
4. [Session Management](#session-management)
5. [CRUD Operations](#crud-operations)
6. [Query Patterns](#query-patterns)
7. [Transactions](#transactions)
8. [Dependency Injection](#dependency-injection)
9. [Testing](#testing)
10. [Advanced Patterns](#advanced-patterns)

## Basic Setup

### Importing Database Services

```python
from sqlmodel import Session, select
from src.app.core.services.database.db_session import DbSessionService
from src.app.core.services.database.db_manage import DbManageService

# Get singleton service instance
db_service = DbSessionService()

# Get database management service
db_manage = DbManageService()
```

### Creating Database Tables

```python
from src.app.runtime.init_db import init_db

# Initialize database (creates all tables)
init_db()
```

### Health Check

```python
from src.app.core.services.database.db_session import DbSessionService

db_service = DbSessionService()

# Check database connectivity
if db_service.health_check():
    print("Database is healthy")
else:
    print("Database connection failed")

# Get pool metrics
pool_status = db_service.get_pool_status()
print(f"Available connections: {pool_status['checked_in']}")
print(f"In-use connections: {pool_status['checked_out']}")
```

## Entity Models

### Base Entity and Table Classes

All entities inherit from base classes that provide common fields:

```python
# src/app/entities/core/_base.py
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Field, SQLModel
import uuid
from datetime import datetime, UTC

class Entity(BaseModel):
    """Domain model base class."""
    
    id: str = PydanticField(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier"
    )
    created_at: datetime = PydanticField(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = PydanticField(default_factory=lambda: datetime.now(UTC))

class EntityTable(SQLModel, table=False):
    """Database table base class."""
    
    id: str = Field(
        primary_key=True,
        default_factory=lambda: str(uuid.uuid4())
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column_kwargs={
            "onupdate": lambda: datetime.now(UTC)  # Auto-update on modification
        }
    )
```

### Defining an Entity

Create three files for each entity:

**1. Domain Entity (`entity.py`):**
```python
# src/app/entities/core/user/entity.py
from pydantic import EmailStr, Field
from src.app.entities.core._base import Entity

class User(Entity):
    """User domain model.
    
    This represents the business logic view of a user.
    Validation rules and business constraints go here.
    """
    
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    address: str | None = Field(None, max_length=500)
    
    @property
    def full_name(self) -> str:
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}"
```

**2. Database Table (`table.py`):**
```python
# src/app/entities/core/user/table.py
from src.app.entities.core._base import EntityTable

class UserTable(EntityTable, table=True):
    """User database table model.
    
    This represents how the user entity is stored in the database.
    """
    
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None
```

**3. Repository (`repository.py`):**
```python
# src/app/entities/core/user/repository.py
from sqlmodel import Session, select
from .entity import User
from .table import UserTable

class UserRepository:
    """Data access layer for User entities."""
    
    def __init__(self, session: Session) -> None:
        self._session = session
    
    def get(self, user_id: str) -> User | None:
        """Get a user by ID."""
        row = self._session.get(UserTable, user_id)
        if row is None:
            return None
        return User.model_validate(row, from_attributes=True)
    
    def list(self, offset: int = 0, limit: int = 100) -> list[User]:
        """List users with pagination."""
        statement = select(UserTable).offset(offset).limit(limit)
        rows = self._session.exec(statement).all()
        return [User.model_validate(row, from_attributes=True) for row in rows]
    
    def create(self, user: User) -> User:
        """Create a new user."""
        row = UserTable.model_validate(user, from_attributes=True)
        self._session.add(row)
        return user
    
    def update(self, user: User) -> User:
        """Update an existing user."""
        row = self._session.get(UserTable, user.id)
        if row is None:
            raise ValueError(f"User with ID {user.id} not found")
        
        for field, value in user.model_dump().items():
            setattr(row, field, value)
        
        return user
    
    def delete(self, user_id: str) -> bool:
        """Delete a user by ID."""
        row = self._session.get(UserTable, user_id)
        if row is None:
            return False
        
        self._session.delete(row)
        return True
```

### Entity with Relationships

```python
# src/app/entities/core/user_identity/table.py
from sqlmodel import Field, Relationship
from src.app.entities.core._base import EntityTable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.app.entities.core.user import UserTable

class UserIdentityTable(EntityTable, table=True):
    """Links OIDC providers to application users."""
    
    # Foreign key to User
    user_id: str = Field(foreign_key="usertable.id", index=True)
    
    # OIDC provider details
    provider: str = Field(max_length=50, index=True)
    provider_user_id: str = Field(max_length=255, index=True)
    
    # Relationship to User (optional, for joins)
    user: "UserTable" = Relationship()
```

## Repository Pattern

### Creating a Repository

```python
from sqlmodel import Session
from src.app.entities.core.user import UserRepository, User

# Get a database session
with db_service.session_scope() as session:
    # Create repository
    user_repo = UserRepository(session)
    
    # Use repository methods
    user = user_repo.get("user-123")
    if user:
        print(f"Found user: {user.full_name}")
```

### Repository Base Class (Optional)

For common repository operations:

```python
from typing import Generic, TypeVar, Type
from sqlmodel import Session, select, SQLModel
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
TableT = TypeVar("TableT", bound=SQLModel)

class BaseRepository(Generic[T, TableT]):
    """Generic repository base class."""
    
    def __init__(
        self,
        session: Session,
        entity_class: Type[T],
        table_class: Type[TableT]
    ):
        self._session = session
        self._entity_class = entity_class
        self._table_class = table_class
    
    def get(self, entity_id: str) -> T | None:
        """Get entity by ID."""
        row = self._session.get(self._table_class, entity_id)
        if row is None:
            return None
        return self._entity_class.model_validate(row, from_attributes=True)
    
    def list(self, offset: int = 0, limit: int = 100) -> list[T]:
        """List entities with pagination."""
        statement = select(self._table_class).offset(offset).limit(limit)
        rows = self._session.exec(statement).all()
        return [
            self._entity_class.model_validate(row, from_attributes=True)
            for row in rows
        ]
    
    def create(self, entity: T) -> T:
        """Create new entity."""
        row = self._table_class.model_validate(entity, from_attributes=True)
        self._session.add(row)
        return entity
    
    def update(self, entity: T) -> T:
        """Update existing entity."""
        row = self._session.get(self._table_class, entity.id)
        if row is None:
            raise ValueError(f"Entity with ID {entity.id} not found")
        
        for field, value in entity.model_dump().items():
            setattr(row, field, value)
        
        return entity
    
    def delete(self, entity_id: str) -> bool:
        """Delete entity by ID."""
        row = self._session.get(self._table_class, entity_id)
        if row is None:
            return False
        
        self._session.delete(row)
        return True

# Usage:
class UserRepository(BaseRepository[User, UserTable]):
    def __init__(self, session: Session):
        super().__init__(session, User, UserTable)
    
    # Add custom methods
    def find_by_email(self, email: str) -> User | None:
        statement = select(UserTable).where(UserTable.email == email)
        row = self._session.exec(statement).first()
        if row is None:
            return None
        return User.model_validate(row, from_attributes=True)
```

## Session Management

### Context Manager Pattern (Recommended)

```python
from src.app.core.services.database.db_session import DbSessionService

db_service = DbSessionService()

# Automatic commit on success, rollback on error
with db_service.session_scope() as session:
    user_repo = UserRepository(session)
    
    # Create user
    new_user = User(
        first_name="John",
        last_name="Doe",
        email="john@example.com"
    )
    user_repo.create(new_user)
    
    # Changes are automatically committed when context exits
    # If an exception occurs, changes are rolled back
```

### Manual Session Management

```python
# Get session
session = db_service.get_session()

try:
    user_repo = UserRepository(session)
    user = user_repo.get("user-123")
    
    # Modify user
    user.email = "newemail@example.com"
    user_repo.update(user)
    
    # Commit changes
    session.commit()
except Exception as e:
    # Rollback on error
    session.rollback()
    raise
finally:
    # Always close session
    session.close()
```

### Session in FastAPI Dependencies

```python
from fastapi import Depends
from sqlmodel import Session
from src.app.core.services.database.db_session import DbSessionService

db_service = DbSessionService()

def get_session() -> Session:
    """FastAPI dependency for database sessions."""
    session = db_service.get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# Use in route handlers
@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    session: Session = Depends(get_session)
):
    user_repo = UserRepository(session)
    user = user_repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

## CRUD Operations

### Create (INSERT)

```python
from src.app.entities.core.user import User, UserRepository

with db_service.session_scope() as session:
    user_repo = UserRepository(session)
    
    # Create single user
    new_user = User(
        first_name="Jane",
        last_name="Smith",
        email="jane@example.com",
        phone="+1234567890"
    )
    user_repo.create(new_user)
    print(f"Created user with ID: {new_user.id}")
    
    # Create multiple users
    users = [
        User(first_name="Alice", last_name="Johnson", email="alice@example.com"),
        User(first_name="Bob", last_name="Williams", email="bob@example.com"),
    ]
    for user in users:
        user_repo.create(user)
```

### Read (SELECT)

```python
with db_service.session_scope() as session:
    user_repo = UserRepository(session)
    
    # Get by ID
    user = user_repo.get("user-123")
    if user:
        print(f"User: {user.full_name}")
    
    # List with pagination
    users = user_repo.list(offset=0, limit=10)
    for user in users:
        print(f"- {user.full_name} ({user.email})")
    
    # Count total users
    from sqlmodel import select, func
    statement = select(func.count()).select_from(UserTable)
    total = session.exec(statement).one()
    print(f"Total users: {total}")
```

### Update

```python
with db_service.session_scope() as session:
    user_repo = UserRepository(session)
    
    # Get existing user
    user = user_repo.get("user-123")
    if user is None:
        raise ValueError("User not found")
    
    # Modify fields
    user.email = "newemail@example.com"
    user.address = "123 Main St, City, Country"
    
    # Save changes
    user_repo.update(user)
    print(f"Updated user: {user.id}")
```

### Delete

```python
with db_service.session_scope() as session:
    user_repo = UserRepository(session)
    
    # Delete by ID
    deleted = user_repo.delete("user-123")
    if deleted:
        print("User deleted successfully")
    else:
        print("User not found")
    
    # Soft delete (optional implementation)
    user = user_repo.get("user-456")
    if user:
        user.is_deleted = True
        user.deleted_at = datetime.now(UTC)
        user_repo.update(user)
```

## Query Patterns

### Simple Queries

```python
from sqlmodel import select
from src.app.entities.core.user import UserTable

with db_service.session_scope() as session:
    # Select all users
    statement = select(UserTable)
    users = session.exec(statement).all()
    
    # Select with filter
    statement = select(UserTable).where(UserTable.email == "john@example.com")
    user = session.exec(statement).first()
    
    # Select specific columns
    statement = select(UserTable.id, UserTable.email)
    results = session.exec(statement).all()
```

### Advanced Filtering

```python
from sqlmodel import select, and_, or_, not_

with db_service.session_scope() as session:
    # AND conditions
    statement = select(UserTable).where(
        and_(
            UserTable.first_name == "John",
            UserTable.last_name == "Doe"
        )
    )
    
    # OR conditions
    statement = select(UserTable).where(
        or_(
            UserTable.email == "john@example.com",
            UserTable.email == "jane@example.com"
        )
    )
    
    # NOT condition
    statement = select(UserTable).where(
        not_(UserTable.email.is_(None))
    )
    
    # LIKE pattern
    statement = select(UserTable).where(
        UserTable.email.like("%@example.com")
    )
    
    # IN clause
    emails = ["john@example.com", "jane@example.com"]
    statement = select(UserTable).where(UserTable.email.in_(emails))
    
    users = session.exec(statement).all()
```

### Ordering and Pagination

```python
from sqlmodel import select

with db_service.session_scope() as session:
    # Order by single column
    statement = select(UserTable).order_by(UserTable.created_at.desc())
    users = session.exec(statement).all()
    
    # Order by multiple columns
    statement = select(UserTable).order_by(
        UserTable.last_name.asc(),
        UserTable.first_name.asc()
    )
    users = session.exec(statement).all()
    
    # Pagination
    page = 2
    page_size = 10
    offset = (page - 1) * page_size
    
    statement = select(UserTable).offset(offset).limit(page_size)
    users = session.exec(statement).all()
```

### Joins and Relationships

```python
from sqlmodel import select
from src.app.entities.core.user import UserTable
from src.app.entities.core.user_identity import UserIdentityTable

with db_service.session_scope() as session:
    # Join tables
    statement = select(UserTable, UserIdentityTable).join(
        UserIdentityTable,
        UserTable.id == UserIdentityTable.user_id
    )
    results = session.exec(statement).all()
    
    for user, identity in results:
        print(f"User: {user.full_name}, Provider: {identity.provider}")
    
    # Left outer join
    statement = select(UserTable, UserIdentityTable).outerjoin(
        UserIdentityTable,
        UserTable.id == UserIdentityTable.user_id
    )
    results = session.exec(statement).all()
```

### Aggregations

```python
from sqlmodel import select, func

with db_service.session_scope() as session:
    # Count
    statement = select(func.count()).select_from(UserTable)
    total = session.exec(statement).one()
    
    # Count with filter
    statement = select(func.count()).select_from(UserTable).where(
        UserTable.email.is_not(None)
    )
    users_with_email = session.exec(statement).one()
    
    # Group by
    statement = select(
        func.date(UserTable.created_at).label("date"),
        func.count().label("count")
    ).group_by(func.date(UserTable.created_at))
    
    results = session.exec(statement).all()
    for date, count in results:
        print(f"{date}: {count} users")
```

## Transactions

### Explicit Transaction Control

```python
from sqlmodel import Session
from sqlalchemy.exc import IntegrityError

with db_service.session_scope() as session:
    try:
        # Multiple operations in single transaction
        user1 = User(first_name="User", last_name="One", email="user1@example.com")
        user2 = User(first_name="User", last_name="Two", email="user2@example.com")
        
        user_repo = UserRepository(session)
        user_repo.create(user1)
        user_repo.create(user2)
        
        # Both users are created atomically
        # Commit happens automatically when context exits
        
    except IntegrityError as e:
        # Rollback happens automatically on exception
        print(f"Transaction failed: {e}")
        raise
```

### Savepoints (Nested Transactions)

```python
with db_service.session_scope() as session:
    user_repo = UserRepository(session)
    
    # Create first user
    user1 = User(first_name="User", last_name="One", email="user1@example.com")
    user_repo.create(user1)
    
    # Create savepoint
    savepoint = session.begin_nested()
    
    try:
        # Try to create second user
        user2 = User(first_name="User", last_name="Two", email="duplicate@example.com")
        user_repo.create(user2)
        
    except IntegrityError:
        # Rollback to savepoint (user1 is still saved)
        savepoint.rollback()
        print("User2 creation failed, but user1 is still saved")
    else:
        # Commit savepoint
        savepoint.commit()
```

### Transaction Isolation Levels

```python
from sqlalchemy import create_engine

# Set isolation level at engine creation
engine = create_engine(
    database_url,
    isolation_level="REPEATABLE READ"  # or "READ COMMITTED", "SERIALIZABLE"
)

# Or per-session
with db_service.session_scope() as session:
    # Set isolation level for this session
    session.connection().execution_options(
        isolation_level="SERIALIZABLE"
    )
    
    # Perform operations
    user_repo = UserRepository(session)
    user = user_repo.get("user-123")
```

## Dependency Injection

### FastAPI Dependencies

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from src.app.core.services.database.db_session import DbSessionService
from src.app.entities.core.user import User, UserRepository

router = APIRouter(prefix="/users", tags=["users"])

db_service = DbSessionService()

def get_session() -> Session:
    """Database session dependency."""
    session = db_service.get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get_user_repo(session: Session = Depends(get_session)) -> UserRepository:
    """User repository dependency."""
    return UserRepository(session)

@router.get("/{user_id}", response_model=User)
async def get_user(
    user_id: str,
    user_repo: UserRepository = Depends(get_user_repo)
):
    """Get user by ID."""
    user = user_repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/", response_model=User, status_code=201)
async def create_user(
    user: User,
    user_repo: UserRepository = Depends(get_user_repo)
):
    """Create new user."""
    user_repo.create(user)
    return user
```

### Centralized Dependency Provider

```python
# src/app/api/http/deps.py
from fastapi import Depends
from sqlmodel import Session
from src.app.core.services.database.db_session import DbSessionService
from src.app.entities.core.user import UserRepository

db_service = DbSessionService()

def get_session() -> Session:
    """Provide database session."""
    session = db_service.get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get_user_repository(
    session: Session = Depends(get_session)
) -> UserRepository:
    """Provide user repository."""
    return UserRepository(session)

# Usage in routes:
from src.app.api.http.deps import get_user_repository

@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    user_repo: UserRepository = Depends(get_user_repository)
):
    return user_repo.get(user_id)
```

## Testing

### Test Fixtures

```python
import pytest
from sqlmodel import Session, create_engine
from sqlmodel.pool import StaticPool
from src.app.entities.core._base import EntityTable

@pytest.fixture(name="db_engine")
def db_engine_fixture():
    """Create in-memory SQLite engine for tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Reuse same connection
    )
    
    # Create all tables
    EntityTable.metadata.create_all(engine)
    
    return engine

@pytest.fixture(name="db_session")
def db_session_fixture(db_engine):
    """Provide database session for tests."""
    with Session(db_engine) as session:
        yield session
        session.rollback()  # Rollback after each test

@pytest.fixture(name="user_repo")
def user_repo_fixture(db_session):
    """Provide user repository for tests."""
    from src.app.entities.core.user import UserRepository
    return UserRepository(db_session)
```

### Unit Tests

```python
import pytest
from src.app.entities.core.user import User

def test_create_user(user_repo):
    """Test creating a user."""
    user = User(
        first_name="John",
        last_name="Doe",
        email="john@example.com"
    )
    
    created_user = user_repo.create(user)
    
    assert created_user.id is not None
    assert created_user.first_name == "John"
    assert created_user.last_name == "Doe"
    assert created_user.email == "john@example.com"

def test_get_user(user_repo):
    """Test getting a user by ID."""
    # Create user
    user = User(first_name="Jane", last_name="Smith", email="jane@example.com")
    created_user = user_repo.create(user)
    
    # Retrieve user
    retrieved_user = user_repo.get(created_user.id)
    
    assert retrieved_user is not None
    assert retrieved_user.id == created_user.id
    assert retrieved_user.full_name == "Jane Smith"

def test_update_user(user_repo):
    """Test updating a user."""
    # Create user
    user = User(first_name="Bob", last_name="Johnson", email="bob@example.com")
    created_user = user_repo.create(user)
    
    # Update user
    created_user.email = "bob.johnson@example.com"
    updated_user = user_repo.update(created_user)
    
    # Verify update
    retrieved_user = user_repo.get(created_user.id)
    assert retrieved_user.email == "bob.johnson@example.com"

def test_delete_user(user_repo):
    """Test deleting a user."""
    # Create user
    user = User(first_name="Alice", last_name="Williams", email="alice@example.com")
    created_user = user_repo.create(user)
    
    # Delete user
    deleted = user_repo.delete(created_user.id)
    assert deleted is True
    
    # Verify deletion
    retrieved_user = user_repo.get(created_user.id)
    assert retrieved_user is None
```

### Integration Tests

```python
import pytest
from src.app.core.services.database.db_session import DbSessionService

@pytest.mark.integration
def test_database_health_check():
    """Test database connectivity."""
    db_service = DbSessionService()
    assert db_service.health_check() is True

@pytest.mark.integration
def test_connection_pool():
    """Test connection pool functionality."""
    db_service = DbSessionService()
    
    # Get pool status
    status = db_service.get_pool_status()
    
    assert status["size"] >= 0
    assert status["checked_in"] >= 0
    assert status["checked_out"] >= 0

@pytest.mark.integration
def test_transaction_rollback():
    """Test automatic rollback on error."""
    db_service = DbSessionService()
    
    try:
        with db_service.session_scope() as session:
            from src.app.entities.core.user import UserRepository, User
            user_repo = UserRepository(session)
            
            # Create user
            user = User(first_name="Test", last_name="User", email="test@example.com")
            user_repo.create(user)
            
            # Force error
            raise ValueError("Simulated error")
    except ValueError:
        pass
    
    # Verify rollback (user should not exist)
    with db_service.session_scope() as session:
        from sqlmodel import select
        from src.app.entities.core.user import UserTable
        
        statement = select(UserTable).where(UserTable.email == "test@example.com")
        user = session.exec(statement).first()
        assert user is None
```

## Advanced Patterns

### Bulk Operations

```python
from sqlmodel import Session

with db_service.session_scope() as session:
    # Bulk insert
    users = [
        UserTable(first_name=f"User{i}", last_name="Test", email=f"user{i}@example.com")
        for i in range(1000)
    ]
    session.bulk_save_objects(users)
    
    # Bulk update
    statement = select(UserTable).where(UserTable.email.like("%@example.com"))
    users = session.exec(statement).all()
    
    for user in users:
        user.address = "Updated Address"
    
    session.commit()
```

### Raw SQL Queries

```python
from sqlalchemy import text

with db_service.session_scope() as session:
    # Execute raw SQL
    result = session.exec(
        text("SELECT * FROM usertable WHERE email = :email"),
        {"email": "john@example.com"}
    )
    rows = result.all()
    
    # Execute with parameters
    session.exec(
        text("UPDATE usertable SET address = :address WHERE id = :id"),
        {"address": "New Address", "id": "user-123"}
    )
```

### Query Result Streaming

```python
from sqlmodel import select

with db_service.session_scope() as session:
    # Stream large result sets
    statement = select(UserTable)
    
    for user in session.exec(statement):
        # Process one user at a time (memory efficient)
        print(f"Processing user: {user.id}")
        
        # Update user
        user.processed = True
        
        # Commit every 100 records
        if int(user.id.split("-")[1]) % 100 == 0:
            session.commit()
```

### Optimistic Locking

```python
from sqlmodel import Field

class UserTable(EntityTable, table=True):
    """User table with version field for optimistic locking."""
    
    first_name: str
    last_name: str
    email: str | None
    version: int = Field(default=0)  # Version field

# Usage:
with db_service.session_scope() as session:
    user = session.get(UserTable, "user-123")
    current_version = user.version
    
    # Modify user
    user.email = "newemail@example.com"
    user.version += 1
    
    # Update with version check
    statement = text("""
        UPDATE usertable 
        SET email = :email, version = :new_version 
        WHERE id = :id AND version = :old_version
    """)
    
    result = session.exec(statement, {
        "email": user.email,
        "new_version": user.version,
        "id": user.id,
        "old_version": current_version
    })
    
    if result.rowcount == 0:
        raise ValueError("Concurrent modification detected")
```

## Related Documentation

- [Main Documentation](./main.md) - PostgreSQL overview
- [Configuration Guide](./configuration.md) - Connection settings and environment variables
- [Security Guide](./security.md) - TLS, authentication, and access control
- [Migrations Guide](./migrations.md) - Schema management with Alembic
- [Production Deployment](../PRODUCTION_DEPLOYMENT.md) - Production setup
