# Changelog

All notable changes to the FastAPI Hexagonal Architecture Template will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial template structure with hexagonal architecture
- Cookiecutter configuration with comprehensive options
- Cruft integration for template updates
- GitHub Actions workflows for CI and automated updates
- Pre/post generation hooks for validation and setup
- Comprehensive documentation and examples

## [0.1.0] - 2025-09-19

### Added
- FastAPI application with hexagonal architecture
- JWT/OIDC authentication with multi-issuer support
- Rate limiting with Redis or in-memory backends
- Security middleware and headers
- Comprehensive test suite with fixtures
- Database management with SQLModel
- Environment configuration with Pydantic Settings
- Developer experience tools (linting, formatting, typing)
- Production-ready defaults and best practices

### Security
- CORS configuration with credential support
- Security headers middleware
- JWT validation with JWKS endpoints
- Role and scope-based authorization

### Developer Experience
- Type safety throughout the application
- Comprehensive test coverage
- Pre-configured development tools
- Auto-generated API documentation
- Environment-based configuration

---

## Release Process

### For Template Maintainers

1. **Update Version Numbers**:
   - Update version in `cookiecutter.json`
   - Update version references in documentation
   - Update this CHANGELOG.md

2. **Create Release**:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

3. **GitHub Release**:
   - Create GitHub release from tag
   - Include changelog notes
   - Highlight breaking changes

### For Template Users

When a new template version is released:

1. **Automatic Updates**: GitHub Actions will create a PR if enabled
2. **Manual Updates**: Run `cruft check` and `cruft update`
3. **Review Changes**: Check MIGRATING.md for breaking changes
4. **Test Thoroughly**: Run full test suite after updates

### Breaking Changes Policy

- **Major versions** (1.0.0, 2.0.0): May include breaking changes
- **Minor versions** (0.1.0, 0.2.0): Backward compatible features
- **Patch versions** (0.1.1, 0.1.2): Bug fixes only

Breaking changes will always be documented in MIGRATING.md with:
- Clear description of the change
- Migration steps required
- Code examples showing before/after
- Timeline for deprecation (when applicable)