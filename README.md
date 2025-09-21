# FastAPI Hexagonal Architecture Template

⚠️ **Alpha Release**: This project is currently in alpha. While functional and tested, APIs and structure may change. Use in production at your own discretion and expect potential breaking changes.

A modern, production-ready [Cookiecutter](https://cookiecutter.readthedocs.io/) template for creating FastAPI applications with hexagonal (ports and adapters) architecture. Build scalable REST APIs with built-in authentication, authorization, rate limiting, and automated template updates.

## 🎯 Motivation

This project exists to **accelerate the development of production-enabled microservices and SaaS APIs** by providing all the necessary primitives, components, and architectural templates that adhere to industry best practices.

### 🎯 Intended Use Cases

This template is specifically designed for:

✅ **User-to-Service Microservices** - Backend APIs that serve client applications (web, mobile, desktop)  
✅ **SaaS Backend Development** - Multi-tenant service APIs with authentication and rate limiting  
✅ **REST API Services** - Standalone API services that integrate with existing systems  
✅ **Microservice Architecture** - Individual services within a larger distributed system  
✅ **Backend-as-a-Service** - APIs that provide core functionality to frontend applications  

### ❌ What This Template Is NOT

This template is **not intended** for:

❌ **Full-Stack Applications** - Does not include frontend frameworks, UI components, or client-side code  
❌ **Monolithic Web Applications** - Not designed for traditional server-rendered web apps  
❌ **Turnkey Complete Solutions** - Requires integration with your chosen frontend and infrastructure  
❌ **All-in-One Platforms** - Focuses purely on API development, not complete application stacks  

**Focus**: This template excels at creating the **backend API layer** that powers modern applications, leaving frontend technology choices and infrastructure decisions to you.

### The Problem This Template Solves

Building production-ready APIs from scratch involves solving the same challenges repeatedly:
- **Authentication & Authorization**: JWT handling, role-based access control, security middleware
- **Architectural Decisions**: Clean separation of concerns, testable code structure
- **Infrastructure Integration**: Database connections, caching, rate limiting, health checks
- **Developer Experience**: Type safety, testing frameworks, documentation generation
- **Operational Readiness**: Monitoring, logging, error handling, graceful degradation

### The Solution Provided

Instead of rebuilding these foundational elements for every project, this template provides:

✅ **Complete API Primitives** - Authentication, rate limiting, database integration, and security middleware  
✅ **Hexagonal Architecture** - Clean, testable code structure with proper separation of concerns  
✅ **Production Components** - Health checks, error handling, logging, and monitoring hooks  
✅ **Best Practices** - Type safety, comprehensive testing, documentation, and CI/CD pipelines  
✅ **Developer Velocity** - Skip the boilerplate and focus on your unique business logic  

**Result**: Transform weeks of setup and architectural decisions into minutes of configuration, allowing you to focus on building features that matter to your users.

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

## �️ Roadmap & Planned Features

We're continuously improving this template to provide the most comprehensive FastAPI development experience. Here's what's coming:

### 🔐 Enhanced Security & Authentication
- [ ] **Multi-Factor Authentication (MFA)** - TOTP and SMS-based 2FA support
- [ ] **OAuth2 Provider Templates** - Ready-to-use integration with Google, GitHub, Microsoft
- [ ] **API Key Management** - Built-in API key generation, rotation, and scoping
- [ ] **Advanced RBAC** - Fine-grained permissions with resource-based access control
- [ ] **Security Audit Logging** - Comprehensive audit trails for compliance requirements
- [ ] **Rate Limiting Strategies** - Multiple rate limiting algorithms (sliding window, token bucket)

### 📊 Observability & Monitoring
- [ ] **OpenTelemetry Integration** - Distributed tracing with Jaeger/Zipkin support
- [ ] **Prometheus Metrics** - Built-in application and business metrics collection
- [ ] **Health Check Dashboard** - Advanced health monitoring with dependency checks
- [ ] **Error Tracking** - Integration with Sentry, Rollbar, or Bugsnag
- [ ] **Performance Profiling** - Built-in APM with request profiling capabilities
- [ ] **Custom Alerting** - Configurable alerts for critical application events

### 🗄️ Database & Storage Enhancements
- [ ] **Multi-Database Support** - MongoDB, DynamoDB, and other NoSQL options
- [ ] **Database Migrations** - Alembic integration with automated migration workflows
- [ ] **Connection Pooling** - Advanced connection pool management and monitoring
- [ ] **Read/Write Splitting** - Automatic routing for read replicas and write masters
- [ ] **Caching Strategies** - Redis caching patterns with cache-aside, write-through
- [ ] **Event Sourcing Support** - Event store integration for audit and replay capabilities

### 🚀 Performance & Scalability
- [ ] **Async Task Processing** - Celery/RQ integration for background job processing
- [ ] **GraphQL Support** - Strawberry GraphQL integration with the existing REST API
- [ ] **WebSocket Templates** - Real-time communication patterns and connection management
- [ ] **API Gateway Integration** - Kong, Ambassador, or Istio service mesh templates
- [ ] **Auto-scaling Configs** - Kubernetes HPA and Docker Swarm scaling configurations
- [ ] **Circuit Breaker Pattern** - Resilient external service integration

### 🧪 Testing & Quality Assurance
- [ ] **Contract Testing** - Pact-based consumer-driven contract testing
- [ ] **Load Testing Templates** - Locust and Artillery test scenarios
- [ ] **Mutation Testing** - Code quality validation with mutation testing tools
- [ ] **Security Testing** - OWASP ZAP integration for automated security scanning
- [ ] **Property-Based Testing** - Hypothesis integration for robust test generation
- [ ] **Visual Regression Testing** - Automated UI testing for API documentation

### 🏗️ Development Experience
- [ ] **IDE Integration** - VS Code/PyCharm project templates and debugging configs
- [ ] **Hot Reloading** - Advanced development server with instant API updates
- [ ] **API Versioning** - Built-in versioning strategies (header, URL, content negotiation)
- [ ] **Documentation Generation** - Enhanced OpenAPI docs with examples and tutorials
- [ ] **CLI Tools** - Project-specific CLI for common development tasks
- [ ] **Template Customization** - Plugin system for extending template functionality

### ☁️ Cloud & Deployment
- [ ] **Cloud Provider Templates** - AWS, GCP, Azure deployment configurations
- [ ] **Serverless Support** - AWS Lambda, Google Cloud Functions deployment options
- [ ] **Container Orchestration** - Advanced Kubernetes manifests with Helm charts
- [ ] **Infrastructure as Code** - Terraform/Pulumi modules for complete stack deployment
- [ ] **CI/CD Pipelines** - GitHub Actions, GitLab CI, Jenkins templates
- [ ] **Blue-Green Deployments** - Zero-downtime deployment strategies

### 🔌 Integration & Ecosystem
- [ ] **Message Queue Integration** - RabbitMQ, Apache Kafka, AWS SQS templates
- [ ] **External API Clients** - Type-safe client generation for common APIs
- [ ] **Webhook Handlers** - Secure webhook processing with signature validation
- [ ] **File Upload/Storage** - S3, MinIO, local storage with image processing
- [ ] **Email Service Integration** - SendGrid, Mailgun, AWS SES template configurations
- [ ] **Search Integration** - Elasticsearch, Solr, or Algolia search capabilities

### 📱 API Client Generation
- [ ] **TypeScript/JavaScript SDK** - Auto-generated client libraries
- [ ] **Python Client Library** - Type-safe Python SDK for API consumption
- [ ] **Mobile SDK Templates** - React Native, Flutter API client generation
- [ ] **Postman Collections** - Auto-generated API testing collections
- [ ] **OpenAPI Generator Integration** - Multi-language client generation

### 🎯 Specialized Templates
- [ ] **E-commerce APIs** - Product catalog, cart, payment processing templates
- [ ] **Content Management** - CMS APIs with media handling and content workflows
- [ ] **IoT Data Processing** - Time-series data ingestion and processing patterns
- [ ] **Financial Services** - Payment processing, compliance, and audit-ready templates
- [ ] **Healthcare APIs** - HIPAA-compliant templates with data privacy features
- [ ] **Real-time Analytics** - Stream processing and dashboard APIs

### 📈 Business Intelligence
- [ ] **Analytics Dashboard** - Built-in analytics for API usage and performance
- [ ] **A/B Testing Framework** - Feature flag management and experiment tracking
- [ ] **User Behavior Tracking** - Anonymous usage analytics and insights
- [ ] **Business Metrics** - Automated reporting for KPIs and business metrics
- [ ] **Data Export APIs** - Scheduled data exports in multiple formats

## 🤝 Contributing to the Roadmap

We welcome community input on our roadmap! Here's how you can contribute:

- **🗳️ Vote on Features**: Comment on [GitHub Issues](https://github.com/piewared/api_template/issues) with 👍 for features you want
- **💡 Suggest Features**: Open a feature request with detailed use cases
- **🔧 Submit PRs**: Help implement roadmap items or propose new ones
- **📖 Documentation**: Help improve docs and examples for new features
- **🧪 Beta Testing**: Test pre-release features and provide feedback

### Priority Levels
- **🔥 High Priority**: Core functionality improvements (Security, Performance, Testing)
- **⭐ Medium Priority**: Developer experience enhancements (IDE, CLI, Documentation)
- **💡 Future Exploration**: Advanced features (Specialized templates, BI features)

## �📚 Documentation

- **[Features](FEATURES.md)** - Complete feature list and capabilities
- **[Architecture](ARCHITECTURE.md)** - Hexagonal architecture details and design patterns
- **[Development](DEVELOPMENT.md)** - Contributing, template development, and deployment guide

## 🔄 Staying Updated

Generated projects automatically receive template updates:
- Weekly GitHub Action checks for updates
- Pull requests created with migration notes
- Manual updates: `cruft update`


## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/piewared/api_template/issues)
- **Discussions**: [GitHub Discussions](https://github.com/piewared/api_template/discussions)

## 📄 License

MIT License. Generated projects can use any license you specify.

---

**⭐ Star this repo** if it helped you build better APIs!