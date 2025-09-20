# Development Guide

## Template Development

If you want to contribute to or modify this template itself:

### Development Setup

```bash
# Clone the template repository
git clone https://github.com/piewared/api_template.git
cd api_template

# Install development dependencies
uv sync

# Initialize development database
./dev.sh init-db
```

### Development Commands

```bash
# Run infrastructure tests (62 tests for template infrastructure)
./dev.sh test

# Run template generation tests (3 tests for cookiecutter generation)
./dev.sh test-template

# Run all tests (infrastructure + template generation)
./dev.sh test-all

# Start development server for template testing
./dev.sh serve

# Code quality checks
./dev.sh lint
./dev.sh format
```

### Development Workflow

The template has a unified test structure in `tests/` at the project root:

1. **Infrastructure Tests** (`tests/unit/`, `tests/integration/`): Test the template infrastructure code directly
2. **Template Generation Tests** (`tests/template/`): Test the cookiecutter template generation process

This unified structure allows you to:
- Work on template features and run unit tests immediately
- Validate template generation without manually creating new projects
- Maintain fast development cycles with a single test command
- Easily debug both infrastructure and generation issues

### Template Testing Results

✅ **Verified template generation working correctly:**
- Template generates successfully with custom project values
- Generated FastAPI application starts and runs properly  
- All API endpoints functional (health, docs, business routes)
- Generated project tests pass (3/3 tests)
- Template infrastructure tests pass (62/62 tests)
- Graceful fallback for missing dependencies (Redis → in-memory rate limiting)

## Template Updates

This template is designed to evolve over time. Generated projects can easily receive updates:

### Automatic Updates (Recommended)

The generated project includes a GitHub Action that:
- Checks for template updates weekly
- Creates a pull request with changes
- Provides detailed migration notes

### Manual Updates

```bash
# Check for available updates
cruft check

# Apply updates interactively
cruft update

# Review changes and test
git diff
pytest
```

### Linking Existing Projects

To link an existing project to this template:

```bash
# In your existing project directory
cruft link https://github.com/piewared/api_template
```

## Development Commands for Generated Projects

```bash
# Development server
uvicorn main:app --reload

# Testing
pytest                        # Run tests
pytest --cov=your_package    # With coverage
pytest -k "test_auth"        # Run specific tests

# Code quality
ruff check .                 # Linting
ruff format .               # Formatting
mypy your_package           # Type checking

# Database
uv run init-db              # Initialize database
```

## Deployment

### Environment Variables

Key production settings:

```bash
ENVIRONMENT=production
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
JWT_ISSUER_JWKS_MAP={"https://...":"https://..."}
CORS_ORIGINS=https://yourdomain.com
```

## Contributing to the Template

We welcome contributions to improve this template:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add/update tests
5. Update documentation
6. Submit a pull request

### Template Development

To test template changes:

```bash
# Test template generation
cruft create . --output-dir /tmp/test-project

# Test updates
cd existing-project
cruft update
```