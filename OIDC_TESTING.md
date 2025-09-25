# OIDC Testing Guide

This guide covers comprehensive testing of the OIDC (OpenID Connect) implementation including both unit tests and integration tests with a local Keycloak server.

## Test Structure Overview

```
tests/
├── fixtures/
│   ├── oidc.py              # OIDC-specific test fixtures
│   └── core.py              # General test fixtures
├── unit/
│   ├── core/
│   │   ├── test_oidc_client_service.py    # OIDC client service unit tests
│   │   └── test_session_service.py        # Session service unit tests
│   └── api/
│       └── test_auth_bff_router.py        # BFF router unit tests
└── integration/
    └── test_oidc_keycloak.py              # Integration tests with Keycloak
```

## Unit Tests (No Network, Fully Mocked)

The unit tests prove your JIT/BFF logic without requiring an IdP running. They use comprehensive mocking to test all components in isolation.

### Running Unit Tests

```bash
# Run all OIDC unit tests
python -m pytest tests/unit/core/test_oidc_client_service.py -v
python -m pytest tests/unit/core/test_session_service.py -v
python -m pytest tests/unit/api/test_auth_bff_router.py -v

# Run all unit tests at once
python -m pytest tests/unit/ -k "oidc or session or bff" -v
```

### Unit Test Coverage

#### OIDC Client Service Tests (`test_oidc_client_service.py`)
- **PKCE Generation**: Tests PKCE code verifier and challenge generation
- **Token Exchange**: Tests authorization code to token exchange with mocked HTTP responses
- **User Claims Extraction**: Tests claims extraction from ID tokens and userinfo endpoints
- **Token Refresh**: Tests refresh token flow
- **Error Handling**: Tests various error scenarios and HTTP failures

#### Session Service Tests (`test_session_service.py`)
- **Auth Session Management**: Tests temporary session creation/retrieval for OIDC flows
- **User Session Management**: Tests persistent session management after authentication
- **JIT User Provisioning**: Tests Just-In-Time user creation from OIDC claims
- **CSRF Protection**: Tests CSRF token generation and validation
- **Session Expiry**: Tests session cleanup and expiry handling

#### BFF Router Tests (`test_auth_bff_router.py`)
- **Login Initiation** (`/auth/web/login`): Tests OIDC flow initiation with PKCE
- **Callback Handling** (`/auth/web/callback`): Tests authorization code callback processing
- **Logout** (`/auth/web/logout`): Tests session termination and provider logout
- **Authentication State** (`/auth/web/me`): Tests current user state retrieval
- **Session Refresh** (`/auth/web/refresh`): Tests token refresh handling
- **Error Cases**: Tests various error scenarios and edge cases

## Integration Tests (Local IdP Container)

The integration tests exercise real OIDC flows with a local Keycloak container, providing end-to-end validation.

### Setting Up the Development Environment

1. **Start Keycloak and configure it automatically:**
   ```bash
   ./dev/setup_dev.sh
   ```

2. **Verify setup:**
   ```bash
   ./dev/dev_utils.py status
   ```

3. **Access Keycloak Admin Console:**
   - URL: http://localhost:8080
   - Username: `admin`
   - Password: `admin`

### Running Integration Tests

```bash
# Run integration tests (Keycloak must be running)
python -m pytest tests/integration/test_oidc_keycloak.py -v

# Run with the dev utils helper
./dev/dev_utils.py test
```

### Integration Test Coverage

#### Keycloak Configuration Tests
- **Realm Configuration**: Verifies test-realm is properly configured
- **OIDC Endpoints**: Tests all OIDC discovery endpoints are accessible
- **Client Configuration**: Verifies OIDC client settings

#### OIDC Flow Tests
- **Login Initiation**: Tests redirect to Keycloak authorization endpoint
- **Parameter Validation**: Verifies PKCE parameters, state, redirect URIs
- **Error Handling**: Tests callback without session, missing parameters
- **Authentication State**: Tests unauthenticated state handling

#### Manual End-to-End Test
- **Full Flow Demonstration**: Shows complete OIDC flow (requires manual browser interaction)
- **Documentation**: Provides step-by-step instructions for manual testing

## Test Configuration

### Test Environment Variables

The integration tests automatically configure the application to use the local Keycloak:

```bash
# These are set automatically by the test fixtures
OIDC_DEFAULT_CLIENT_ID=test-client
OIDC_DEFAULT_CLIENT_SECRET=test-client-secret  
OIDC_DEFAULT_ISSUER=http://localhost:8080/realms/test-realm
OIDC_DEFAULT_AUTHORIZATION_ENDPOINT=http://localhost:8080/realms/test-realm/protocol/openid-connect/auth
OIDC_DEFAULT_TOKEN_ENDPOINT=http://localhost:8080/realms/test-realm/protocol/openid-connect/token
OIDC_DEFAULT_USERINFO_ENDPOINT=http://localhost:8080/realms/test-realm/protocol/openid-connect/userinfo
OIDC_DEFAULT_JWKS_URI=http://localhost:8080/realms/test-realm/protocol/openid-connect/certs
OIDC_DEFAULT_END_SESSION_ENDPOINT=http://localhost:8080/realms/test-realm/protocol/openid-connect/logout
OIDC_DEFAULT_REDIRECT_URI=http://localhost:8000/auth/web/callback
```

### Test Data

The development setup creates these test accounts:

- **testuser1@example.com** / password: `password123`
- **testuser2@example.com** / password: `password123`

## Development Utilities

The `dev/dev_utils.py` script provides helpful utilities for OIDC development and testing:

### Check Keycloak Status
```bash
./dev/dev_utils.py status
```

### Get Access Token for Testing
```bash
./dev/dev_utils.py token --username testuser1 --password password123
```

### Decode JWT Token (Development Only)
```bash
./dev/dev_utils.py decode eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Test Userinfo Endpoint
```bash
./dev/dev_utils.py userinfo <access_token>
```

### Run Integration Tests
```bash
./dev/dev_utils.py test
```

## Running All Tests

### Run All Unit Tests
```bash
# OIDC-related unit tests only
python -m pytest tests/unit/ -k "oidc or session or auth_bff" -v

# All unit tests
python -m pytest tests/unit/ -v
```

### Run All Integration Tests
```bash
# Requires Keycloak to be running
python -m pytest tests/integration/ -v
```

### Run Full Test Suite
```bash
# Start Keycloak first
./dev/setup_dev.sh

# Run all tests
python -m pytest tests/ -v

# Cleanup after testing
./dev/cleanup_dev.sh
```

## Test Architecture Patterns

### Mocking Strategy
- **Service Level Mocking**: Mock `oidc_client_service` and `session_service` for router tests
- **HTTP Level Mocking**: Mock `httpx.AsyncClient` for service-level tests
- **Configuration Mocking**: Mock `get_config()` for environment-specific testing

### Fixture Design
- **Hierarchical Fixtures**: Base fixtures for common objects, specialized fixtures for specific scenarios
- **Factory Fixtures**: Create customizable mock objects for different test scenarios
- **Cleanup Fixtures**: Ensure proper test isolation and cleanup

### Conditional Testing
- **Keycloak Availability**: Integration tests skip when Keycloak isn't running
- **Environment Specific**: Tests adapt behavior based on available services
- **Manual Tests**: Mark tests requiring human interaction for documentation

## Troubleshooting Tests

### Common Issues

#### Unit Tests Failing
- **Import Errors**: Ensure all test dependencies are installed
- **Fixture Errors**: Check that mock fixtures match actual service interfaces
- **Assertion Errors**: Verify test expectations match current implementation

#### Integration Tests Skipping
```bash
# Check if Keycloak is running
./dev/dev_utils.py status

# If not running, start it
./dev/setup_dev.sh

# Verify configuration
curl http://localhost:8080/realms/test-realm/.well-known/openid_configuration
```

#### Docker Issues
```bash
# Check Docker is running
docker info

# Check container status
docker-compose -f dev/docker-compose.yml ps

# View Keycloak logs
docker-compose -f dev/docker-compose.yml logs keycloak
```

### Test Data Reset
```bash
# Remove all Keycloak data and restart fresh
./dev/cleanup_dev.sh --remove-data
./dev/setup_dev.sh
```

## Continuous Integration

### CI Pipeline Recommendations
```yaml
# Example GitHub Actions workflow
- name: Run Unit Tests
  run: python -m pytest tests/unit/ -v

- name: Start Keycloak
  run: |
    cd dev
    docker-compose up -d keycloak
    ./setup_keycloak.py

- name: Run Integration Tests  
  run: python -m pytest tests/integration/ -v

- name: Cleanup
  run: cd dev && docker-compose down
```

### Local Development Workflow
1. **Start Development**: `./dev/setup_dev.sh`
2. **Run Unit Tests**: `python -m pytest tests/unit/ -v`
3. **Run Integration Tests**: `python -m pytest tests/integration/ -v`
4. **Develop/Debug**: Use `./dev/dev_utils.py` for debugging
5. **Cleanup**: `./dev/cleanup_dev.sh`

## Best Practices

### Writing New OIDC Tests
1. **Unit First**: Write unit tests with mocks before integration tests
2. **Realistic Mocks**: Ensure mocks match real service behavior
3. **Error Coverage**: Test both success and failure scenarios
4. **Isolation**: Each test should be independent and cleanup after itself

### Maintaining Tests
1. **Keep Fixtures Updated**: Update fixtures when service interfaces change
2. **Test Environment Parity**: Ensure test Keycloak config matches production patterns
3. **Documentation**: Update test documentation when adding new test scenarios
4. **Performance**: Keep unit tests fast, use integration tests sparingly

This testing strategy provides comprehensive coverage of your OIDC implementation with both fast unit tests for development and thorough integration tests for confidence in real-world scenarios.