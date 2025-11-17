# FastAPI Testing Strategy

Learn how to test your FastAPI application with pytest, including unit tests, integration tests, fixtures, and test automation. This guide covers the comprehensive testing strategy included in API Forge for building reliable, well-tested FastAPI microservices.

## Overview

API Forge includes a complete testing infrastructure for FastAPI applications with:

- **pytest framework** - Modern Python testing with fixtures and parametrization
- **Unit tests** - Test individual functions and classes in isolation
- **Integration tests** - Test API endpoints with real database
- **Test fixtures** - Reusable test data and setup
- **Async support** - Test async FastAPI endpoints with pytest-asyncio
- **Test database** - Isolated SQLite database for testing
- **Mocking** - Mock external services and dependencies
- **Coverage reporting** - Track test coverage with pytest-cov

The testing strategy follows the **Test Pyramid**: many unit tests, some integration tests, few end-to-end tests.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests (fast, isolated)
│   ├── entities/
│   │   └── user/
│   │       ├── test_model.py      # Entity business logic
│   │       ├── test_service.py    # Service logic (mocked)
│   │       └── test_repository.py # Repository (mocked)
│   ├── core/
│   │   └── services/
│   │       ├── test_jwt_service.py
│   │       └── test_session_service.py
│   └── worker/
│       ├── activities/
│       │   └── test_email.py
│       └── workflows/
│           └── test_order.py
│
├── integration/             # Integration tests (slower, real dependencies)
│   ├── api/
│   │   └── test_user_router.py    # API endpoint tests
│   ├── database/
│   │   └── test_user_repository.py # Real database tests
│   └── worker/
│       └── test_workflows.py       # Temporal workflow tests
│
└── fixtures/                # Test data
    ├── users.json
    └── orders.json
```

## Running Tests

### Run All Tests

```bash
# Run entire test suite
uv run pytest tests/ -v

# With coverage report
uv run pytest tests/ -v --cov=src --cov-report=term-missing

# Generate HTML coverage report
uv run pytest tests/ --cov=src --cov-report=html
# Open htmlcov/index.html in browser
```

### Run Specific Test Categories

```bash
# Unit tests only (fast)
uv run pytest tests/unit/ -v

# Integration tests only
uv run pytest tests/integration/ -v

# Specific test file
uv run pytest tests/unit/entities/user/test_service.py -v

# Specific test function
uv run pytest tests/unit/entities/user/test_service.py::test_create_user -v

# Tests matching pattern
uv run pytest tests/ -k "user" -v
```

### Test Markers

```bash
# Skip slow tests
uv run pytest -m "not slow"

# Run only manual tests (require interaction)
uv run pytest -m "manual"

# Run only tests that require Docker
uv run pytest -m "docker"
```

## Test Configuration

### pytest.ini

```ini
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "manual: marks tests that require manual interaction",
    "docker: marks tests that require Docker services",
    "integration: marks integration tests",
    "unit: marks unit tests",
]
addopts = [
    "--strict-markers",
    "--tb=short",
    "-ra",
]
```

## Test Fixtures

### Database Fixtures

```python
# tests/conftest.py
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from src.app.entities.user.model import User
from src.app.entities.order.model import Order

@pytest.fixture(name="engine")
def engine_fixture():
    """Create test database engine (SQLite in-memory)"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create all tables
    SQLModel.metadata.create_all(engine)
    
    yield engine
    
    # Cleanup
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(name="db_session")
def db_session_fixture(engine):
    """Create test database session"""
    with Session(engine) as session:
        yield session

@pytest.fixture(name="db_session_with_data")
def db_session_with_data_fixture(db_session):
    """Database session pre-populated with test data"""
    from tests.fixtures.users import create_test_users
    
    users = create_test_users(db_session)
    db_session.commit()
    
    yield db_session
```

### API Client Fixtures

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient

from src.app.api.http.app import create_app

@pytest.fixture(name="client")
def client_fixture():
    """Create FastAPI test client"""
    app = create_app()
    
    with TestClient(app) as client:
        yield client

@pytest.fixture(name="authenticated_client")
def authenticated_client_fixture(client, db_session):
    """Test client with authenticated session"""
    from src.app.entities.user.model import UserCreate
    from src.app.entities.user.repository import UserRepository
    from src.app.core.services.session_service import SessionService
    
    # Create test user
    repository = UserRepository(db_session)
    user_data = UserCreate(
        email="test@example.com",
        password="password123",
        full_name="Test User"
    )
    user = repository.create(user_data)
    
    # Create session
    session_service = SessionService(client.app.state.redis, client.app.state.config)
    # Simulate login by setting session cookie
    client.cookies.set("session_id", "test_session_id")
    
    yield client
```

### Mock Fixtures

```python
# tests/conftest.py
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis = Mock()
    redis.get = Mock(return_value=None)
    redis.set = Mock(return_value=True)
    redis.delete = Mock(return_value=1)
    redis.setex = Mock(return_value=True)
    return redis

@pytest.fixture
def mock_temporal_client():
    """Mock Temporal client"""
    client = AsyncMock()
    client.start_workflow = AsyncMock(return_value=Mock(id="test-workflow-id"))
    return client

@pytest.fixture
def mock_email_service():
    """Mock email service"""
    service = Mock()
    service.send_welcome_email = AsyncMock(return_value="email-123")
    service.send_order_confirmation = AsyncMock(return_value="email-456")
    return service
```

## Unit Tests

### Testing Entities (Business Logic)

```python
# tests/unit/entities/user/test_model.py
import pytest
from src.app.entities.user.model import User

def test_user_is_verified():
    """Test user verification business rule"""
    user = User(
        email="test@example.com",
        hashed_password="hash",
        is_active=True,
        email_verified=True
    )
    
    assert user.is_verified() is True

def test_user_not_verified_when_inactive():
    """Test user not verified when inactive"""
    user = User(
        email="test@example.com",
        hashed_password="hash",
        is_active=False,
        email_verified=True
    )
    
    assert user.is_verified() is False

def test_superuser_can_perform_any_action():
    """Test superuser permission check"""
    user = User(
        email="admin@example.com",
        hashed_password="hash",
        is_superuser=True
    )
    
    assert user.can_perform_action("delete_user") is True
    assert user.can_perform_action("view_analytics") is True
```

### Testing Services (With Mocks)

```python
# tests/unit/entities/user/test_service.py
import pytest
from unittest.mock import Mock
from fastapi import HTTPException

from src.app.entities.user.model import UserCreate, User
from src.app.entities.user.service import UserService

def test_create_user_success():
    """Test successful user creation"""
    # Mock repository
    repository = Mock()
    repository.exists.return_value = False
    repository.create.return_value = User(
        id=1,
        email="test@example.com",
        hashed_password="hash",
        full_name="Test User"
    )
    
    service = UserService(repository)
    user_data = UserCreate(
        email="test@example.com",
        password="password123",
        full_name="Test User"
    )
    
    result = service.create_user(user_data)
    
    assert result.email == "test@example.com"
    assert result.full_name == "Test User"
    repository.exists.assert_called_once_with("test@example.com")
    repository.create.assert_called_once()

def test_create_user_duplicate_email():
    """Test user creation fails with duplicate email"""
    # Mock repository
    repository = Mock()
    repository.exists.return_value = True
    
    service = UserService(repository)
    user_data = UserCreate(
        email="test@example.com",
        password="password123"
    )
    
    with pytest.raises(HTTPException) as exc:
        service.create_user(user_data)
    
    assert exc.value.status_code == 400
    assert "already registered" in exc.value.detail
    repository.create.assert_not_called()

def test_get_user_not_found():
    """Test get user raises 404 when not found"""
    repository = Mock()
    repository.get_by_id.return_value = None
    
    service = UserService(repository)
    
    with pytest.raises(HTTPException) as exc:
        service.get_user(999)
    
    assert exc.value.status_code == 404
    assert "not found" in exc.value.detail
```

### Testing Async Functions

```python
# tests/unit/worker/activities/test_email.py
import pytest
from unittest.mock import patch, AsyncMock

from src.app.worker.activities.email import send_welcome_email

@pytest.mark.asyncio
async def test_send_welcome_email_success():
    """Test sending welcome email"""
    with patch("src.app.core.services.email_service.EmailService") as MockEmailService:
        mock_service = MockEmailService.return_value
        mock_service.send_welcome_email = AsyncMock(return_value="email-123")
        
        result = await send_welcome_email(1, "test@example.com")
        
        assert "Email sent" in result
        mock_service.send_welcome_email.assert_called_once_with(
            to="test@example.com",
            user_id=1
        )

@pytest.mark.asyncio
async def test_send_welcome_email_failure():
    """Test email sending failure raises exception"""
    with patch("src.app.core.services.email_service.EmailService") as MockEmailService:
        mock_service = MockEmailService.return_value
        mock_service.send_welcome_email = AsyncMock(side_effect=Exception("SMTP error"))
        
        with pytest.raises(Exception) as exc:
            await send_welcome_email(1, "test@example.com")
        
        assert "SMTP error" in str(exc.value)
```

## Integration Tests

### Testing API Endpoints

```python
# tests/integration/api/test_user_router.py
import pytest
from fastapi.testclient import TestClient

def test_create_user(client: TestClient):
    """Test POST /users/ endpoint"""
    response = client.post(
        "/users/",
        json={
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "full_name": "New User"
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["full_name"] == "New User"
    assert "id" in data
    assert "password" not in data  # Password should not be in response

def test_create_user_duplicate_email(client: TestClient):
    """Test creating user with duplicate email fails"""
    user_data = {
        "email": "duplicate@example.com",
        "password": "password123",
        "full_name": "User One"
    }
    
    # Create first user
    response1 = client.post("/users/", json=user_data)
    assert response1.status_code == 201
    
    # Try to create duplicate
    response2 = client.post("/users/", json=user_data)
    assert response2.status_code == 400
    assert "already registered" in response2.json()["detail"]

def test_list_users_requires_auth(client: TestClient):
    """Test GET /users/ requires authentication"""
    response = client.get("/users/")
    assert response.status_code == 401

def test_list_users_authenticated(authenticated_client: TestClient):
    """Test GET /users/ with authentication"""
    response = authenticated_client.get("/users/")
    
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

def test_get_user_by_id(authenticated_client: TestClient):
    """Test GET /users/{user_id}"""
    # Create user first
    create_response = authenticated_client.post(
        "/users/",
        json={"email": "gettest@example.com", "password": "pass123"}
    )
    user_id = create_response.json()["id"]
    
    # Get user
    response = authenticated_client.get(f"/users/{user_id}")
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user_id
    assert data["email"] == "gettest@example.com"

def test_update_user(authenticated_client: TestClient):
    """Test PATCH /users/{user_id}"""
    # Get current user ID from session
    current_user_id = 1  # From fixture
    
    response = authenticated_client.patch(
        f"/users/{current_user_id}",
        json={"full_name": "Updated Name"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Updated Name"

def test_update_other_user_forbidden(authenticated_client: TestClient):
    """Test updating another user is forbidden"""
    response = authenticated_client.patch(
        "/users/999",  # Different user
        json={"full_name": "Hacker"}
    )
    
    assert response.status_code == 403
```

### Testing with Real Database

```python
# tests/integration/database/test_user_repository.py
import pytest
from sqlmodel import Session

from src.app.entities.user.model import UserCreate, UserUpdate
from src.app.entities.user.repository import UserRepository

def test_create_user(db_session: Session):
    """Test creating user in database"""
    repository = UserRepository(db_session)
    user_data = UserCreate(
        email="dbtest@example.com",
        password="password123",
        full_name="DB Test User"
    )
    
    user = repository.create(user_data)
    
    assert user.id is not None
    assert user.email == "dbtest@example.com"
    assert user.full_name == "DB Test User"
    assert user.hashed_password != "password123"  # Should be hashed

def test_get_by_email(db_session: Session):
    """Test retrieving user by email"""
    repository = UserRepository(db_session)
    
    # Create user
    user_data = UserCreate(email="find@example.com", password="pass123")
    created_user = repository.create(user_data)
    
    # Find by email
    found_user = repository.get_by_email("find@example.com")
    
    assert found_user is not None
    assert found_user.id == created_user.id
    assert found_user.email == "find@example.com"

def test_list_users_with_filters(db_session: Session):
    """Test listing users with filters"""
    repository = UserRepository(db_session)
    
    # Create test users
    repository.create(UserCreate(email="active1@example.com", password="pass", is_active=True))
    repository.create(UserCreate(email="active2@example.com", password="pass", is_active=True))
    repository.create(UserCreate(email="inactive@example.com", password="pass", is_active=False))
    
    # List active users only
    active_users = repository.list(is_active=True)
    
    assert len(active_users) == 2
    assert all(u.is_active for u in active_users)

def test_update_user(db_session: Session):
    """Test updating user"""
    repository = UserRepository(db_session)
    
    # Create user
    user = repository.create(UserCreate(email="update@example.com", password="pass"))
    
    # Update user
    update_data = UserUpdate(full_name="Updated Name")
    updated_user = repository.update(user, update_data)
    
    assert updated_user.full_name == "Updated Name"
    assert updated_user.email == "update@example.com"  # Unchanged

def test_delete_user(db_session: Session):
    """Test deleting user"""
    repository = UserRepository(db_session)
    
    # Create user
    user = repository.create(UserCreate(email="delete@example.com", password="pass"))
    user_id = user.id
    
    # Delete user
    repository.delete(user)
    
    # Verify deleted
    assert repository.get_by_id(user_id) is None
```

### Parametrized Tests

```python
# tests/integration/api/test_validation.py
import pytest

@pytest.mark.parametrize(
    "email,password,expected_status",
    [
        ("valid@example.com", "SecurePass123!", 201),
        ("invalid-email", "password", 422),  # Invalid email
        ("test@example.com", "short", 422),  # Password too short
        ("", "password123", 422),  # Empty email
        ("test@example.com", "", 422),  # Empty password
    ]
)
def test_user_validation(client: TestClient, email, password, expected_status):
    """Test user creation validation"""
    response = client.post(
        "/users/",
        json={"email": email, "password": password}
    )
    
    assert response.status_code == expected_status
```

## Testing Temporal Workflows

### Workflow Unit Tests

```python
# tests/unit/worker/workflows/test_order.py
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from src.app.worker.workflows.order import OrderFulfillmentWorkflow
from src.app.worker.activities.email import send_order_confirmation

@pytest.mark.asyncio
async def test_order_fulfillment_success():
    """Test successful order fulfillment workflow"""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[OrderFulfillmentWorkflow],
            activities=[send_order_confirmation],
        ):
            result = await env.client.execute_workflow(
                OrderFulfillmentWorkflow.run,
                args=[1, "test@example.com", [101, 102], "credit_card"],
                id="test-order-1",
                task_queue="test",
            )
            
            assert result["status"] == "completed"
            assert "tracking_number" in result

@pytest.mark.asyncio
async def test_order_fulfillment_payment_failure():
    """Test workflow handles payment failure"""
    # Mock payment activity to fail
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[OrderFulfillmentWorkflow],
            activities=[],  # No activities, will fail
        ):
            result = await env.client.execute_workflow(
                OrderFulfillmentWorkflow.run,
                args=[1, "test@example.com", [101], "invalid_method"],
                id="test-order-fail",
                task_queue="test",
            )
            
            assert result["status"] == "failed"
            assert result["reason"] == "payment_failed"
```

## Test Data Fixtures

### JSON Fixtures

```python
# tests/fixtures/users.py
from typing import List
from sqlmodel import Session

from src.app.entities.user.model import User, UserCreate
from src.app.entities.user.repository import UserRepository

def create_test_users(session: Session) -> List[User]:
    """Create test users in database"""
    repository = UserRepository(session)
    
    users_data = [
        UserCreate(
            email="admin@example.com",
            password="admin123",
            full_name="Admin User",
            is_superuser=True
        ),
        UserCreate(
            email="user1@example.com",
            password="password123",
            full_name="Regular User One"
        ),
        UserCreate(
            email="user2@example.com",
            password="password123",
            full_name="Regular User Two",
            is_active=False
        ),
    ]
    
    users = [repository.create(user_data) for user_data in users_data]
    session.commit()
    
    return users
```

## Coverage Reports

### Generating Coverage Reports

```bash
# Terminal output with missing lines
uv run pytest --cov=src --cov-report=term-missing

# HTML report (detailed)
uv run pytest --cov=src --cov-report=html
open htmlcov/index.html

# XML report (for CI/CD)
uv run pytest --cov=src --cov-report=xml

# Combine reports
uv run pytest --cov=src --cov-report=term-missing --cov-report=html --cov-report=xml
```

### Coverage Configuration

```ini
# pyproject.toml
[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/migrations/*",
    "*/__pycache__/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
```

## CI/CD Integration

### GitHub Actions

```yaml
# .github/workflows/ci.yml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Install uv
        uses: astral-sh/setup-uv@v1
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      
      - name: Install dependencies
        run: uv sync --dev
      
      - name: Run tests with coverage
        run: uv run pytest tests/ -v --cov=src --cov-report=xml
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: true
```

## Best Practices

### 1. Test Naming

```python
# GOOD: Descriptive test names
def test_create_user_with_valid_data_returns_201():
    pass

def test_create_user_with_duplicate_email_returns_400():
    pass

# BAD: Vague test names
def test_user():
    pass

def test_api():
    pass
```

### 2. Arrange-Act-Assert Pattern

```python
def test_create_order():
    # Arrange - Set up test data
    order_data = OrderCreate(
        user_id=1,
        product_ids=[101, 102],
        total=99.99
    )
    
    # Act - Execute the functionality
    result = order_service.create_order(order_data)
    
    # Assert - Verify the outcome
    assert result.id is not None
    assert result.user_id == 1
    assert result.total == 99.99
```

### 3. Test Isolation

```python
# Each test should be independent
def test_a():
    # Don't rely on test_b running first
    pass

def test_b():
    # Don't rely on test_a's side effects
    pass
```

### 4. Use Fixtures for Setup

```python
# GOOD: Use fixtures
@pytest.fixture
def order_with_items():
    return Order(id=1, items=[...])

def test_calculate_total(order_with_items):
    total = order_with_items.calculate_total()
    assert total == 99.99

# BAD: Duplicate setup in each test
def test_calculate_total():
    order = Order(id=1, items=[...])
    total = order.calculate_total()
    assert total == 99.99
```

### 5. Don't Test Framework Code

```python
# BAD: Testing FastAPI/SQLModel internals
def test_pydantic_validation():
    # Don't test that Pydantic validates emails
    pass

# GOOD: Test your business logic
def test_user_email_must_be_from_allowed_domain():
    # Test your custom validation
    pass
```

## Troubleshooting

### Tests Fail in CI but Pass Locally

**Causes**:
- Database state differences
- Environment variables
- Time zone issues
- File system differences

**Solutions**:
- Use SQLite in-memory for tests
- Load config from .env.test
- Use UTC timestamps
- Don't depend on file paths

### Async Test Failures

**Symptom**: "coroutine was never awaited"

**Solution**:
```python
# Use @pytest.mark.asyncio
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result == expected
```

### Fixture Not Found

**Symptom**: "fixture 'xyz' not found"

**Solutions**:
- Check conftest.py is in correct location
- Verify fixture name matches
- Check fixture scope

## Related Documentation

- [FastAPI Clean Architecture](./fastapi-clean-architecture-overview.md) - Understanding what to test
- [FastAPI Docker Development](./fastapi-docker-dev-environment.md) - Running integration tests
- [Getting Started Guide](./index.md) - Project overview

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)
