# Migration Guide

This document provides detailed instructions for migrating between major versions of the FastAPI Hexagonal Architecture Template.

## General Migration Process

1. **Backup Your Project**: Always commit your changes before updating
2. **Check the Version**: Run `cruft status` to see current template version
3. **Review Changes**: Check this guide and CHANGELOG.md for breaking changes
4. **Update Template**: Run `cruft update` to apply changes
5. **Resolve Conflicts**: Manually resolve any merge conflicts
6. **Test Thoroughly**: Run your full test suite
7. **Update Dependencies**: Check if any new dependencies are required

## Version Migration Guides

### From v0.1.0 to v0.2.0 (Future)

*This section will be populated when v0.2.0 is released.*

## Common Migration Scenarios

### Handling Merge Conflicts

When `cruft update` encounters conflicts:

1. **Identify Conflict Files**:
   ```bash
   git status
   # Look for files with merge conflict markers
   ```

2. **Resolve Each Conflict**:
   ```python
   # Example conflict in settings.py
   <<<<<<< HEAD
   # Your custom configuration
   custom_setting: str = "your_value"
   =======
   # Template update
   new_template_setting: bool = True
   >>>>>>> template
   ```

3. **Choose Resolution Strategy**:
   - Keep your changes if they're business logic
   - Adopt template changes for framework/infrastructure code
   - Merge both if compatible

4. **Test After Resolution**:
   ```bash
   pytest
   mypy your_package
   ```

### Updating Import Statements

If the template renames modules or packages:

1. **Use IDE Refactoring**: Most IDEs can safely rename imports
2. **Search and Replace**: Use `grep` and `sed` for bulk changes
3. **Check Test Files**: Don't forget test imports

### Updating Configuration

When new configuration options are added:

1. **Check `.env.example`**: Look for new environment variables
2. **Update Your `.env`**: Add new settings with appropriate values
3. **Update Settings Class**: Merge new Pydantic settings
4. **Update Documentation**: Document your custom settings

### Database Schema Changes

If the template updates database models:

1. **Review Model Changes**: Check `*_row.py` files for schema updates
2. **Create Migration**: Generate database migration if needed
3. **Backup Database**: Always backup before schema changes
4. **Test Migration**: Test on development environment first

## Template vs. Application Code

Understanding what code should be updated vs. preserved:

### Template-Managed Code (Usually Update)

- **Infrastructure Configuration**: Database connections, middleware setup
- **Security Settings**: CORS, headers, authentication setup  
- **Build Tools**: CI workflows, linting configuration, project setup
- **Framework Glue**: FastAPI app factory, dependency injection setup
- **Development Tools**: Testing utilities, development scripts

**Strategy**: Generally accept template updates for these files, then re-apply your customizations.

### Application-Owned Code (Usually Preserve)

- **Domain Logic**: Business entities, repository interfaces, services
- **API Routes**: Your specific endpoints and business workflows
- **Custom Middleware**: Application-specific middleware
- **Environment Variables**: Your specific configuration values
- **Custom Tests**: Tests for your business logic

**Strategy**: Preserve your changes and manually integrate template improvements.

### Hybrid Areas (Review Carefully)

- **Settings Classes**: Merge new template settings with your custom ones
- **Main Application**: Keep your routes, update infrastructure
- **Database Models**: Preserve your entities, update base classes
- **Test Fixtures**: Merge template improvements with your custom fixtures

## Troubleshooting

### Common Issues

#### 1. Import Errors After Update

```bash
# Error: ModuleNotFoundError
# Solution: Check if module was renamed
grep -r "old_module_name" .
# Update imports to new module name
```

#### 2. Configuration Validation Errors

```bash
# Error: ValidationError in settings
# Solution: Check for new required settings
diff .env.example .env
# Add missing configuration
```

#### 3. Test Failures

```bash
# Run specific failing tests
pytest tests/path/to/failing_test.py -v
# Check if test fixtures need updating
```

#### 4. Type Checking Errors

```bash
# Run mypy to see specific type issues
mypy your_package
# Update type annotations as needed
```

### Recovery Strategies

#### If Update Breaks Your Application

1. **Revert the Update**:
   ```bash
   git reset --hard HEAD~1
   # or
   git revert <commit-hash>
   ```

2. **Apply Updates Gradually**:
   ```bash
   # Update specific files manually
   cruft update --skip-apply-ask
   # Review changes file by file
   ```

3. **Selective Integration**:
   - Cherry-pick specific template improvements
   - Ignore changes that conflict with your customizations

#### If Cruft Gets Confused

1. **Reset Template Tracking**:
   ```bash
   # Remove .cruft.json
   rm .cruft.json
   # Re-link to template
   cruft link https://github.com/YOUR_ORG/fastapi-hexagonal-template
   ```

2. **Manual Sync**:
   - Download latest template
   - Manually compare and merge changes
   - Update .cruft.json with new commit SHA

## Best Practices

### Before Each Update

- [ ] Commit all local changes
- [ ] Read CHANGELOG.md for the new version
- [ ] Review this migration guide
- [ ] Backup database if schema changes expected
- [ ] Plan for testing time

### During Updates

- [ ] Resolve conflicts thoughtfully (don't just accept all changes)
- [ ] Preserve your business logic
- [ ] Update configuration files
- [ ] Test incrementally as you resolve conflicts

### After Updates

- [ ] Run full test suite
- [ ] Test application manually
- [ ] Update documentation
- [ ] Deploy to staging environment first
- [ ] Monitor for issues

### Ongoing Maintenance

- [ ] Review template updates regularly
- [ ] Keep customizations minimal and well-documented
- [ ] Use inheritance/composition over modification when possible
- [ ] Contribute improvements back to the template

## Getting Help

If you encounter issues during migration:

1. **Check Documentation**: README.md, this guide, and template docs
2. **Search Issues**: Look for similar problems in GitHub issues
3. **Ask for Help**: Create a GitHub issue with:
   - Template version you're updating from/to
   - Specific error messages
   - Steps to reproduce the issue
   - Your customizations that might be relevant

## Contributing Migration Guides

If you encounter migration challenges not covered here:

1. Document your solution
2. Submit a PR to update this guide
3. Help other users avoid the same issues

---

**Remember**: Template updates are meant to improve your application. Take time to understand changes rather than blindly accepting them.