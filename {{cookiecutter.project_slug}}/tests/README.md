# Tests for {{cookiecutter.project_name}}

This directory contains tests for your generated project. The template provides a basic structure to get you started.

## What's Included

- `conftest.py` - Test configuration and fixtures
- `test_example.py` - Example test file showing basic patterns

## What You Should Add

You should add tests for:

### Your Business Logic
- Domain entities and business rules
- Use cases and application services  
- Custom repository implementations
- Business validation logic

### Your API Endpoints
- Custom routes you add
- Request/response validation
- Business logic integration
- Error handling

### Your Integrations
- External API integrations
- Custom middleware
- Database migrations
- Configuration validation

## Test Structure

Organize your tests to match your code structure:

```
tests/
├── unit/           # Unit tests for individual components
│   ├── entities/   # Test domain entities
│   ├── services/   # Test business services
│   └── repos/      # Test repository implementations
├── integration/    # Integration tests
│   ├── api/        # Test API endpoints
│   └── db/         # Test database operations
└── e2e/           # End-to-end tests
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov={{cookiecutter.package_name}}

# Run specific test file
uv run pytest tests/test_example.py

# Run tests matching pattern
uv run pytest -k "test_health"
```