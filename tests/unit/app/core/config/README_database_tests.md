# Database Configuration Tests

## Overview

The tests in `test_database_config.py` provide comprehensive coverage for the `DatabaseConfig.password` computed field, testing all password resolution scenarios across different environments and configurations.

## Test Coverage

### Development & Test Mode Tests
- ✅ Password extraction from URL with normal characters
- ✅ Password extraction from URL with special characters (URL-encoded)
- ✅ Error handling when password is missing from URL
- ✅ Support for both `development` and `test` environment modes

### Production Mode Tests
- ✅ Password reading from mounted secrets file
- ✅ Password reading with whitespace trimming from files
- ✅ Error handling for non-existent password files
- ✅ Error handling for file permission issues
- ✅ Password reading from environment variables
- ✅ Error handling for missing environment variables
- ✅ Error handling for empty environment variables
- ✅ Precedence: file takes priority over environment variable
- ✅ Error when neither file nor environment variable is configured

### Edge Cases & Error Handling
- ✅ Invalid environment mode validation
- ✅ SQLite URLs (which don't have passwords)
- ✅ Complex PostgreSQL URLs with query parameters
- ✅ Environment variables containing newlines
- ✅ File passwords with newlines (properly stripped)

### Computed Field Behavior
- ✅ Password accessible as model attribute
- ✅ Password included in model dumps when requested
- ✅ Consistent results across multiple accesses

## Password Resolution Logic

The `password()` computed field follows this resolution order:

1. **Development/Test Mode**: Extract password from the database URL
2. **Production Mode**: 
   - First try `password_file_path` (Docker secrets file)
   - Fall back to `password_environment_variable`
   - Error if neither is configured

## Running the Tests

```bash
# Run just the database config tests
pytest tests/unit/app/core/config/test_database_config.py -v

# Run with coverage
pytest tests/unit/app/core/config/test_database_config.py --cov=src.app.runtime.config.config_data --cov-report=term-missing
```

## Test Dependencies

- `pytest` - Test framework
- `pydantic` - For the DatabaseConfig model
- `sqlalchemy` - For URL parsing (imported in the password method)
- Standard library: `os`, `tempfile`, `unittest.mock`