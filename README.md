# FastAPI Hexagonal Architecture Template

A modern, production-ready [Cookiecutter](https://cookiecutter.readthedocs.io/) template for creating FastAPI applications with hexagonal (ports and adapters) architecture. Build scalable REST APIs with built-in authentication, authorization, rate limiting, and automated template updates.

## 🎯 Why Use This Template?

Create enterprise-grade FastAPI applications in minutes with:
- **Production-ready architecture** with clean separation of concerns
- **Complete authentication system** with JWT/OIDC support
- **Comprehensive testing** (62 tests) with CI/CD pipeline
- **Auto-updating template** to keep projects current
- **Type-safe codebase** with full Pydantic integration

Perfect for building microservices, REST APIs, and backend services that need to scale.

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+** (3.13 recommended)
- **[Cookiecutter](https://cookiecutter.readthedocs.io/en/latest/installation.html)**: `pip install cookiecutter`
- **[Cruft](https://cruft.github.io/cruft/)** (recommended): `pip install cruft`

### Create Your Project

#### Option 1: With Auto-Updates (Recommended)
```bash
# Create with update capabilities
cruft create https://github.com/piewared/api_template

# Follow interactive prompts
```

#### Option 2: Standard Generation
```bash
# One-time generation
cookiecutter https://github.com/piewared/api_template
```

#### Option 3: Non-Interactive
```bash
# Automated generation
cruft create https://github.com/piewared/api_template \
  --no-input \
  project_name="My API" \
  project_description="A FastAPI service" \
  author_name="Your Name" \
  author_email="you@example.com"
```

### Get Started with Your New Project

```bash
# Navigate to your project
cd your-project-name

# Project is ready! Dependencies installed, git initialized
# Configure environment
cp .env.example .env

# Initialize database
uv run init-db

# Start development server
uvicorn main:app --reload
```

Your API is ready at:
- **Application**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## ⚙️ Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `project_name` | Human-readable project name | "My API Project" |
| `project_slug` | URL/filesystem safe name | auto-generated |
| `project_description` | Brief project description | "A FastAPI service..." |
| `author_name` | Your name | "Your Name" |
| `author_email` | Your email | "you@example.com" |
| `version` | Initial version | "0.1.0" |
| `python_version` | Minimum Python version | "3.13" |
| `use_redis` | Include Redis rate limiting | "y" |
| `use_postgres` | Include PostgreSQL examples | "n" |
| `license` | License type | "MIT" |

## 🏗️ What's Included

Your generated project includes:

### Core Features
- ✅ **FastAPI application** with hexagonal architecture
- ✅ **JWT/OIDC authentication** with role-based access control
- ✅ **SQLModel database** integration (SQLite default, PostgreSQL ready)
- ✅ **Redis rate limiting** with in-memory fallback
- ✅ **Security middleware** (CORS, HSTS, security headers)
- ✅ **Comprehensive testing** with 3 example tests ready to extend
- ✅ **GitHub Actions CI/CD** pipeline
- ✅ **Auto-documentation** with OpenAPI/Swagger

### Developer Tools
- 🔧 **Code quality**: Ruff (linting & formatting), MyPy (type checking)
- 🧪 **Testing**: pytest with async support and coverage
- 📦 **Dependencies**: uv for fast package management
- 🔄 **Template updates**: Cruft integration for staying current
- ⚙️ **Environment**: Pydantic Settings with .env support

### Project Structure
```
your-project/
├── main.py                    # FastAPI app entry point
├── your_package/
│   ├── api/http/             # HTTP layer (routes, middleware)
│   ├── core/                 # Domain logic (entities, services)
│   ├── application/          # Application services
│   ├── business/             # Business logic
│   └── runtime/              # Infrastructure (database, settings)
├── tests/                    # Test suite
├── .github/workflows/        # CI/CD
└── .env.example             # Environment template
```

## 📚 Documentation

- **[Features](FEATURES.md)** - Complete feature list and capabilities
- **[Architecture](ARCHITECTURE.md)** - Hexagonal architecture details and design patterns
- **[Development](DEVELOPMENT.md)** - Contributing, template development, and deployment guide

## 🔄 Staying Updated

Generated projects automatically receive template updates:
- Weekly GitHub Action checks for updates
- Pull requests created with migration notes
- Manual updates: `cruft update`

## 📈 SEO Keywords

FastAPI template, Python REST API, hexagonal architecture, cookiecutter template, microservices template, FastAPI boilerplate, Python API template, JWT authentication FastAPI, production-ready FastAPI, FastAPI project generator

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/piewared/api_template/issues)
- **Discussions**: [GitHub Discussions](https://github.com/piewared/api_template/discussions)

## 📄 License

MIT License. Generated projects can use any license you specify.

---

**⭐ Star this repo** if it helped you build better APIs!