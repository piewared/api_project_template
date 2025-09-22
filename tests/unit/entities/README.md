# Hybrid Entity Structure Unit Tests

This directory contains comprehensive unit tests for the new hybrid entity structure implemented in the project.

## Test Coverage

### `test_user.py`
Tests for the User entity package (`src/entities/user/`):
- **TestUser**: Domain entity creation, validation, and field handling
- **TestUserTable**: Database model conversion and persistence logic  
- **TestUserRepository**: Data access operations (get, create)

### `test_user_identity.py`
Tests for the UserIdentity entity package (`src/entities/user_identity/`):
- **TestUserIdentity**: JWT identity entity creation and validation
- **TestUserIdentityTable**: Database model conversion for identity mapping
- **TestUserIdentityRepository**: Data access operations (get_by_uid, get_by_issuer_subject, create)

## Architecture Validation

These tests validate the hybrid entity-centric structure where:

1. **Domain models** (`entity.py`) contain business logic with auto-generated UUIDs
2. **Database models** (`table.py`) handle persistence with SQLModel 
3. **Repository classes** (`repository.py`) manage data access operations
4. **Package exports** (`__init__.py`) provide clean import interfaces

## Running Tests

```bash
# Run all entity tests
pytest tests/unit/entities/

# Run specific entity tests
pytest tests/unit/entities/test_user.py
pytest tests/unit/entities/test_user_identity.py
```

## Test Features

- **Mocked dependencies**: All database sessions are mocked for isolation
- **Complete coverage**: Tests entity creation, validation, persistence, and retrieval
- **Real-world scenarios**: Tests handle both success and failure cases
- **UUID validation**: Ensures auto-generated IDs are valid UUIDs
- **Type safety**: Validates correct type conversion between domain and database models