# Copilot Agent Onboarding - FastAPI Production Template

## Repository Overview

**Project Type**: Cookiecutter-based FastAPI API template for production-ready microservices  
**Primary Language**: Python 3.13+  
**Package Manager**: `uv` (fast Python package installer/manager)  
**Size**: ~500 files, dual structure (infrastructure + cookiecutter template)  
**Key Frameworks**: FastAPI, SQLModel, Pydantic, Temporal, Docker Compose

This is both a **working infrastructure codebase** AND a **Cookiecutter template generator**. The repository contains:
1. **Infrastructure code** in `src/` - the actual working codebase for testing/development
2. **Template code** in `{{cookiecutter.project_slug}}/` - what gets generated when users run `cruft create`

### Core Features
- OIDC authentication (Keycloak dev/test, Google/Microsoft prod) with BFF pattern
- Secure session management with HttpOnly cookies, CSRF protection, client fingerprinting
- PostgreSQL (prod) / SQLite (dev) with SQLModel ORM
- Redis for caching, sessions, and rate limiting
- Temporal workflows for async/background processing
- Full Docker Compose development environment (Keycloak, PostgreSQL, Redis, Temporal)
- Clean Architecture with entities → repositories → services → API layers

---

## Critical Build & Test Commands

**ALWAYS use these exact command sequences. They have been validated to work.**

### Environment Setup (First Time)
```bash
# 1. Copy environment file
cp .env.example .env

# 2. Install dependencies (uv handles virtual env automatically)
uv sync --dev

# 3. Start Docker development environment
uv run cli dev start-env
# Wait 30-60 seconds for services to initialize

# 4. Verify services are healthy
uv run cli dev status

# 5. Initialize database
uv run init-db
```

### Development Server
```bash
# Method 1: Using CLI (recommended, includes hot reload)
uv run cli dev start-server

# Method 2: Direct uvicorn (infrastructure testing)
PYTHONPATH=src uv run uvicorn src.app.api.http.app:app --reload

# Method 3: Legacy dev mode (for cookiecutter template testing)
uv run uvicorn main:app --reload
```

### Testing
```bash
# Run all tests (328 tests, ~15-30 seconds)
uv run pytest tests/ -v

# Run specific test categories
uv run pytest tests/unit/ -v              # Unit tests only
uv run pytest tests/integration/ -v       # Integration tests
uv run pytest tests/template/ -v          # Template generation tests

# With coverage
uv run pytest --cov=src --cov-report=xml

# Skip manual tests (require user interaction)
uv run pytest -m "not manual"
```

### Code Quality
```bash
# Lint (shows 36 errors currently - mostly formatting)
uv run ruff check src/

# Auto-fix linting issues (fixes 31/36 errors)
uv run ruff check src/ --fix

# Format code
uv run ruff format src/

# Type checking (strict mode enabled)
uv run mypy src/
```

### Docker Operations
```bash
# Start dev environment
uv run cli dev start-env

# Check service status
uv run cli dev status

# View logs for specific service
uv run cli dev logs postgres
uv run cli dev logs keycloak
uv run cli dev logs redis
uv run cli dev logs temporal

# Stop environment (preserves data)
uv run cli dev stop-env

# Complete cleanup (destroys volumes/data)
docker-compose -f docker-compose.dev.yml down -v
```

### Database Management
```bash
# Initialize/reset database
uv run init-db

# Direct DB access (dev environment)
docker exec -it api-template-postgres-dev psql -U postgres -d appdb
```

---

## Known Issues & Workarounds

### 1. CLI Status Command Container Names (FIXED)
**Issue**: `uv run cli dev status` showed services as "Not running" when they were actually running  
**Root Cause**: Container name mismatch - code was checking for `app_dev_*` names but actual containers use `api-template-*-dev` naming convention  
**Fix Applied**: Updated `src/dev/cli/dev_commands.py` to use correct container names:
- `api-template-keycloak-dev`
- `api-template-postgres-dev`
- `api-template-redis-dev`
- `api-template-temporal-dev`
- `api-template-temporal-ui-dev`

### 2. Keycloak Setup Module Import Error (FIXED)
**Issue**: `ModuleNotFoundError: No module named 'src.dev.setup_keycloak'`  
**Fix Applied**: Volume mount path corrected from `../src/dev` to `./src/dev` in `docker-compose.dev.yml`  
**Action**: Rebuild keycloak-setup service if error persists

### 3. Temporal Database Connection Issues
**Issue**: Temporal server can't connect despite schemas existing  
**Root Cause**: `temporaluser` search_path is `"$user", public` but schemas are `temporal` and `temporal_visibility`  
**Workaround**: Grant schema access:
```sql
ALTER USER temporaluser SET search_path TO temporal,temporal_visibility,public;
GRANT USAGE ON SCHEMA temporal, temporal_visibility TO temporaluser;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA temporal TO temporaluser;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA temporal_visibility TO temporaluser;
```

### 4. Test Failures in Integration Tests
**Expected Behavior**: Some integration tests fail without Docker environment running  
**Action**: ALWAYS run `uv run cli dev start-env` before integration tests

### 5. Port Conflicts
**Ports Used**: 
- 8000 (FastAPI app)
- 8080 (Keycloak)
- 8081 (Temporal UI)
- 5432 (PostgreSQL - production)
- 5433 (PostgreSQL - development)
- 6379 (Redis - production)
- 6380 (Redis - development)
- 7233 (Temporal)

**Check for conflicts**:
```bash
sudo netstat -tlnp | grep -E ':8080|:5432|:6379|:7233'
```

### 6. Linting Warnings
**Current State**: 36 ruff errors (mostly whitespace/formatting)  
**Safe to ignore** for functionality, but run `uv run ruff check src/ --fix` before committing

---

## Development Environment Test Users

### Keycloak Preloaded Test Users
The development Keycloak service (`api-template-keycloak-dev`) is automatically configured with test users when you run `uv run cli dev start-env`. These users are created by the `src/dev/setup_keycloak.py` script.

**Test Users Available:**
- **Username**: `testuser1`
  - **Email**: testuser1@example.com
  - **Password**: password123
  - **Name**: Test User One
  - **Email Verified**: Yes

- **Username**: `testuser2`
  - **Email**: testuser2@example.com
  - **Password**: password123
  - **Name**: Test User Two
  - **Email Verified**: Yes

**Keycloak Configuration:**
- **Realm**: `test-realm`
- **Client ID**: `test-client`
- **Client Secret**: `test-client-secret`
- **Admin Console**: http://localhost:8080/admin (admin/admin)
- **Redirect URI**: http://localhost:8000/auth/web/callback

**Testing OAuth Flow:**
1. Navigate to http://localhost:8000/auth/web/login?provider=keycloak
2. You'll be redirected to Keycloak login page
3. Login with `testuser1` / `password123`
4. After successful authentication, you'll be redirected back with a session

**Note**: The setup script (`src/dev/setup_keycloak.py`) is idempotent - it will skip creating users/realm/client if they already exist.

---

## Project Architecture & File Locations

### Root Directory Structure
```
/
├── src/                           # Infrastructure source code
│   ├── app/                       # Application code
│   │   ├── api/http/              # FastAPI routers, dependencies
│   │   ├── core/                  # Auth, DB, config, security
│   │   │   ├── models/            # Domain models
│   │   │   ├── services/          # Business logic (OIDC, JWT, sessions)
│   │   │   ├── storage/           # Data access (session storage, DB)
│   │   │   └── security.py        # Security utilities
│   │   ├── entities/              # Domain entities (CLI generates here)
│   │   ├── runtime/               # App initialization & runtime
│   │   │   ├── config/            # Configuration loading & models
│   │   │   └── init_db.py         # Database initialization
│   │   └── service/               # Application services
│   ├── dev/                       # Development tooling
│   │   ├── cli/                   # CLI commands (dev, entity management)
│   │   ├── setup_keycloak.py      # Keycloak setup automation
│   │   └── dev_utils.py           # Development utilities
│   └── utils/                     # Shared utilities
├── {{cookiecutter.project_slug}}/ # Cookiecutter template (generated projects)
├── tests/                         # Test suites
│   ├── unit/                      # Unit tests
│   ├── integration/               # Integration tests (require Docker)
│   ├── template/                  # Template generation tests
│   └── fixtures/                  # Test fixtures
├── docker/                        # Docker configurations
│   ├── dev/                       # Development services
│   │   ├── keycloak/              # Keycloak setup
│   │   ├── postgres/              # PostgreSQL dev config
│   │   ├── redis/                 # Redis dev config
│   │   └── temporal/              # Temporal dev config
│   └── prod/                      # Production services (with TLS/mTLS)
├── docs/                          # Documentation
│   ├── dev_env/                   # Dev environment guides
│   ├── prod/                      # Production deployment
│   └── clients/                   # Client integration examples
├── secrets/                       # Production secrets (gitignored)
├── hooks/                         # Cookiecutter hooks
├── pyproject.toml                 # Python dependencies & config
├── config.yaml                    # Application configuration
├── .env.example                   # Environment variables template
└── dev.sh                         # Development helper script
```

### Critical Configuration Files

#### `config.yaml` - Main Application Config
- **Location**: `/config.yaml`
- **Format**: YAML with environment variable substitution `${VAR:-default}`
- **Sections**: 
  - `app` - app metadata, sessions, CORS
  - `database` - PostgreSQL/SQLite settings
  - `redis` - cache/session store
  - `temporal` - workflow engine
  - `oidc.providers` - authentication providers (keycloak, google, microsoft)
  - `jwt` - token validation rules
  - `rate_limiter` - per-endpoint throttling
  - `logging` - structured logging config

#### `pyproject.toml` - Python Project Config
- **Location**: `/pyproject.toml`
- **Package Manager**: Uses `uv` for fast dependency management
- **Python Version**: >=3.13
- **Key Dependencies**: 
  - `fastapi>=0.116.1`
  - `sqlmodel>=0.0.24`
  - `authlib>=1.6.4`
  - `pydantic>=2.11.9`
  - `uvicorn[standard]>=0.35.0`
- **Dev Dependencies**: `pytest`, `ruff`, `mypy`, `pytest-asyncio`
- **Scripts**: 
  - `init-db` - database initialization
  - `cli` - development CLI
- **Ruff Config**: Line length 88, target py313, excludes cookiecutter dirs
- **MyPy Config**: Strict type checking enabled
- **Pytest Config**: Auto asyncio mode, marks for manual tests

#### `.env` - Environment Variables
- **Location**: `/.env` (create from `.env.example`)
- **Critical Variables**:
  - `APP_ENVIRONMENT` - development/production/testing
  - `DATABASE_URL` - PostgreSQL connection string
  - `REDIS_URL` - Redis connection string
  - `SESSION_SIGNING_SECRET` - **REQUIRED**, must be changed from default
  - `CSRF_SIGNING_SECRET` - **REQUIRED**, must be changed from default
  - `OIDC_*_CLIENT_SECRET` - Provider OAuth credentials
- **Note**: Development uses separate ports (5433, 6380) from production (5432, 6379)

### Key Source Files

#### `src/app/api/http/app.py` - FastAPI Application
Main application factory and router registration

#### `src/app/api/http/deps.py` - Dependency Injection
FastAPI dependencies for auth, DB, sessions, rate limiting

#### `src/app/runtime/config/config_data.py` - Config Models
Pydantic models for config.yaml validation (464 lines)

#### `src/app/runtime/init_db.py` - Database Initialization
Creates tables, runs migrations

#### `src/app/core/services/oidc_client_service.py` - OIDC Client
Handles OAuth flows, token validation, JWKS caching

#### `src/app/core/services/session_service.py` - Session Management
Session creation, validation, rotation, CSRF protection

#### `src/dev/cli/` - CLI Commands
- `dev_commands.py` - Dev environment management
- `entity_commands.py` - Entity scaffolding

---

## CI/CD & Validation

### GitHub Actions (Template Projects)
**Location**: `{{cookiecutter.project_slug}}/.github/workflows/ci.yml`

**Workflow**:
1. **Test Job**: Python 3.13, `uv sync --dev`, `uv run pytest -v --cov`
2. **Lint Job**: `ruff check`, `ruff format --check`, `mypy`

**Triggers**: Push to main/develop, PRs to main/develop

### Local Validation Checklist
Before committing changes:
```bash
# 1. Lint and format
uv run ruff check src/ --fix
uv run ruff format src/

# 2. Type check
uv run mypy src/

# 3. Run tests
uv run pytest tests/ -v

# 4. Verify Docker environment works
uv run cli dev start-env
uv run cli dev status
uv run cli dev stop-env
```

---

## Docker Compose Environments

### Development (`docker-compose.dev.yml`)
**Services**: keycloak, keycloak-setup, postgres, redis, temporal, temporal-web  
**Ports**: 8080 (Keycloak), 5433 (PostgreSQL), 6380 (Redis), 7233 (Temporal), 8081 (Temporal UI)  
**Credentials**: All hardcoded (devuser/devpass, admin/admin)  
**Network**: `dev-network` bridge

### Production (`docker-compose.prod.yml`)
**Services**: postgres, redis, temporal, nginx, app  
**Security**: TLS/mTLS, secrets management, SCRAM-SHA-256 auth  
**Ports**: 8000 (Nginx → FastAPI), 5432 (PostgreSQL), 6379 (Redis), 7233 (Temporal)  
**Secrets**: File-based in `/run/secrets/` (see `secrets/generate_secrets.sh`)

---

## Development Workflow Guide

### Adding a New Feature
```bash
# 1. Create feature branch
git checkout -b feature/my-feature

# 2. Generate entity scaffolding (if needed)
uv run cli entity add MyEntity
# Follow prompts for fields

# 3. Start dev environment
uv run cli dev start-env
uv run cli dev start-server

# 4. Make changes, add tests
# Edit src/app/entities/my_entity/...

# 5. Run tests
uv run pytest tests/unit/app/entities/my_entity/ -v

# 6. Lint and format
uv run ruff check src/ --fix
uv run ruff format src/

# 7. Commit and push
git add .
git commit -m "feat: add MyEntity"
git push origin feature/my-feature
```

### Debugging Tips
```bash
# View real-time logs
uv run cli dev logs [service_name]

# Access PostgreSQL
docker exec -it api-template-postgres-dev psql -U postgres

# Access Redis CLI
docker exec -it api-template-redis-dev redis-cli

# Check Keycloak config
curl http://localhost:8080/realms/test-realm/.well-known/openid-configuration

# Test Temporal UI
open http://localhost:8081
```

---

## Trust These Instructions

**When working in this repository:**
1. **ALWAYS use `uv run` prefix** for Python commands (uv handles virtualenv automatically)
2. **ALWAYS start dev environment** before integration tests: `uv run cli dev start-env`
3. **NEVER run `pip install` directly** - use `uv sync` or `uv add`
4. **Check `.env` file exists** - copy from `.env.example` if missing
5. **Wait 30-60 seconds** after `start-env` for services to be healthy
6. **Use PYTHONPATH=src** when running files directly from `src/`
7. **Run linter before committing**: `uv run ruff check src/ --fix`

**Only search for additional info if:**
- These instructions are incomplete for your specific task
- You encounter an error not documented in "Known Issues"
- You need details on a specific module's internals
- You're working on production deployment (see `docs/PRODUCTION_DEPLOYMENT.md`)

**Common Gotchas:**
- Temporal requires PostgreSQL schemas `temporal` and `temporal_visibility` with proper search_path
- Integration tests will fail if Docker services aren't running
- Some tests marked `@pytest.mark.manual` require user interaction - skip with `-m "not manual"`
- Cookiecutter template files in `{{cookiecutter.project_slug}}/` use Jinja2 syntax - don't lint them
- Development and production use different ports (dev offset by 1000: 5433 vs 5432, 6380 vs 6379)

