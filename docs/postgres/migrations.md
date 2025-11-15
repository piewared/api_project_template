# PostgreSQL Migrations Guide

## Overview

This guide covers database schema management, migration strategies, and future integration with Alembic for version-controlled schema changes.

## Table of Contents

1. [Current State](#current-state)
2. [SQLModel Metadata Approach](#sqlmodel-metadata-approach)
3. [Schema Versioning Strategy](#schema-versioning-strategy)
4. [Manual Migrations](#manual-migrations)
5. [Alembic Integration (Future)](#alembic-integration-future)
6. [Migration Best Practices](#migration-best-practices)
7. [Production Deployment](#production-deployment)
8. [Rollback Strategies](#rollback-strategies)

## Current State

### No Migration System

**Current Implementation:** The application uses SQLModel's `create_all()` method to create tables directly from model definitions:

```python
# src/app/runtime/init_db.py
from sqlmodel import SQLModel
from src.app.core.services.database.db_manage import DbManageService

# Import all table models (required for metadata registration)
from src.app.entities.core.user import UserTable
from src.app.entities.core.user_identity import UserIdentityTable

def init_db() -> None:
    """Create all database tables."""
    db_manage_service = DbManageService()
    db_manage_service.create_all()

# In DbManageService:
def create_all(self) -> None:
    SQLModel.metadata.create_all(self._engine)
```

**Limitations:**
- ❌ No version tracking
- ❌ No incremental changes
- ❌ No automatic schema diffing
- ❌ Destructive for existing data on schema changes
- ❌ No rollback capability

**When This Works:**
- ✅ Initial development
- ✅ Prototyping
- ✅ Testing environments
- ✅ SQLite databases (can drop and recreate)

**When This Fails:**
- ❌ Production databases with existing data
- ❌ Schema changes requiring data transformation
- ❌ Column renames (appears as drop + create)
- ❌ Multiple developers with schema conflicts

### Why Use Migrations?

**Benefits:**
1. **Version Control**: Schema changes tracked in code
2. **Reproducibility**: Same schema on all environments
3. **Safety**: Test migrations before production
4. **Rollback**: Undo changes if needed
5. **Audit Trail**: Who changed what and when
6. **Collaboration**: Multiple developers coordinate schema changes

## SQLModel Metadata Approach

### How SQLModel Tracks Tables

SQLModel uses SQLAlchemy's metadata registry:

```python
from sqlmodel import SQLModel

# When you define a table class
class UserTable(SQLModel, table=True):
    id: str
    email: str

# SQLModel registers it in metadata
print(SQLModel.metadata.tables)
# Output: {'usertable': Table('usertable', MetaData(), ...)}
```

### Creating All Tables

```python
from sqlmodel import create_engine
from src.app.core.services.database.db_manage import DbManageService

db_service = DbManageService()

# Creates ALL tables defined in imported modules
db_service.create_all()

# Equivalent to:
SQLModel.metadata.create_all(engine)
```

**Important:** Only creates tables for **imported** model classes.

### Import Registration Pattern

```python
# src/app/runtime/init_db.py
from src.app.core.services.database.db_manage import DbManageService

# MUST import all table models for registration
from src.app.entities.core.user import UserTable  # noqa: F401
from src.app.entities.core.user_identity import UserIdentityTable  # noqa: F401

# Now create_all() will create both tables
db_manage = DbManageService()
db_manage.create_all()
```

**Best Practice:** Create a central imports file:

```python
# src/app/entities/__init__.py
from .core.user import UserTable
from .core.user_identity import UserIdentityTable

__all__ = ["UserTable", "UserIdentityTable"]

# In init_db.py:
from src.app.entities import *  # Imports all tables
```

### Limitations of create_all()

**Does NOT:**
- ❌ Modify existing tables
- ❌ Add new columns to existing tables
- ❌ Rename columns
- ❌ Change column types
- ❌ Drop removed columns

**Only Does:**
- ✅ Create missing tables
- ✅ Skip existing tables

**Example Problem:**
```python
# Original model
class UserTable(SQLModel, table=True):
    id: str
    email: str

# Updated model (added phone field)
class UserTable(SQLModel, table=True):
    id: str
    email: str
    phone: str | None = None  # New field!

# Running create_all() again...
db_service.create_all()
# Result: Nothing happens! Table already exists.
# phone column is NOT added.
```

## Schema Versioning Strategy

### Semantic Versioning for Schemas

Use semantic versioning (MAJOR.MINOR.PATCH) for schema changes:

```
1.0.0 - Initial schema
│
├─ 1.1.0 - Add phone column to users (backward compatible)
├─ 1.2.0 - Add user_preferences table (backward compatible)
│
└─ 2.0.0 - Rename email to email_address (breaking change)
```

**Version Tracking Table:**
```sql
CREATE TABLE schema_version (
    version VARCHAR(50) PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT NOW(),
    description TEXT
);

INSERT INTO schema_version (version, description)
VALUES ('1.0.0', 'Initial schema');
```

### Version Checking

```python
from sqlmodel import Session, select

def get_current_schema_version(session: Session) -> str:
    """Get current schema version from database."""
    statement = select(SchemaVersionTable.version).order_by(
        SchemaVersionTable.applied_at.desc()
    ).limit(1)
    version = session.exec(statement).first()
    return version or "0.0.0"

def record_schema_version(session: Session, version: str, description: str):
    """Record schema version in database."""
    version_record = SchemaVersionTable(
        version=version,
        applied_at=datetime.now(UTC),
        description=description
    )
    session.add(version_record)
    session.commit()
```

## Manual Migrations

### Migration File Structure

Create a migrations directory:

```
migrations/
├── 001_initial_schema.sql
├── 002_add_user_phone.sql
├── 003_add_user_preferences.sql
└── README.md
```

### Migration File Format

**001_initial_schema.sql:**
```sql
-- Migration: 001_initial_schema
-- Version: 1.0.0
-- Description: Initial database schema
-- Author: Developer Name
-- Date: 2025-11-02

BEGIN;

-- Create users table
CREATE TABLE usertable (
    id UUID PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create user identities table
CREATE TABLE useridentitytable (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES usertable(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(provider, provider_user_id)
);

-- Create indexes
CREATE INDEX idx_user_email ON usertable(email);
CREATE INDEX idx_identity_user ON useridentitytable(user_id);
CREATE INDEX idx_identity_provider ON useridentitytable(provider, provider_user_id);

-- Record schema version
INSERT INTO schema_version (version, description)
VALUES ('1.0.0', 'Initial schema');

COMMIT;
```

**002_add_user_phone.sql:**
```sql
-- Migration: 002_add_user_phone
-- Version: 1.1.0
-- Description: Add phone and address fields to users
-- Author: Developer Name
-- Date: 2025-11-03

BEGIN;

-- Add new columns
ALTER TABLE usertable ADD COLUMN phone VARCHAR(20);
ALTER TABLE usertable ADD COLUMN address VARCHAR(500);

-- Record schema version
INSERT INTO schema_version (version, description)
VALUES ('1.1.0', 'Add phone and address to users');

COMMIT;
```

### Running Manual Migrations

**Development:**
```bash
# Apply migration
docker exec -i api-forge-postgres-dev psql -U postgres -d appdb < migrations/002_add_user_phone.sql
```

**Production:**
```bash
# 1. Backup database first
docker exec api-forge-postgres pg_dump -U appuser appdb > backup.sql

# 2. Apply migration
docker exec -i api-forge-postgres psql -U appuser -d appdb < migrations/002_add_user_phone.sql

# 3. Verify
docker exec api-forge-postgres psql -U appuser -d appdb -c "\d usertable"
```

### Migration Script (Shell)

**migrate.sh:**
```bash
#!/bin/bash
set -euo pipefail

MIGRATIONS_DIR="./migrations"
DB_CONTAINER="api-forge-postgres"
DB_USER="appuser"
DB_NAME="appdb"

# Get current version
CURRENT_VERSION=$(docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c \
    "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1" | xargs)

echo "Current schema version: ${CURRENT_VERSION:-none}"

# Find unapplied migrations
for migration in $(ls $MIGRATIONS_DIR/*.sql | sort); do
    filename=$(basename "$migration")
    
    # Check if already applied
    applied=$(docker exec $DB_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c \
        "SELECT COUNT(*) FROM schema_version WHERE description LIKE '%${filename}%'" | xargs)
    
    if [ "$applied" -eq 0 ]; then
        echo "Applying migration: $filename"
        docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME < "$migration"
        echo "✓ Applied $filename"
    else
        echo "⊘ Skipping $filename (already applied)"
    fi
done

echo "All migrations applied successfully"
```

**Usage:**
```bash
chmod +x migrate.sh
./migrate.sh
```

## Alembic Integration (Future)

### Why Alembic?

**Benefits:**
- ✅ Automatic schema diffing
- ✅ Version control integration
- ✅ Upgrade and downgrade support
- ✅ Branching and merging support
- ✅ Database-agnostic migrations
- ✅ Industry standard (used by SQLAlchemy community)

### Installation

```bash
# Add Alembic to dependencies
uv add alembic

# Initialize Alembic
alembic init alembic/
```

**Generated Structure:**
```
alembic/
├── env.py              # Alembic environment configuration
├── script.py.mako      # Migration template
├── README
└── versions/           # Migration files
    └── (empty)

alembic.ini             # Alembic configuration
```

### Configuration

**alembic/env.py:**
```python
from logging.config import fileConfig
from sqlmodel import SQLModel
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import all table models for autogeneration
from src.app.entities import *

# Alembic Config object
config = context.config

# Configure logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogeneration
target_metadata = SQLModel.metadata

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    
    # Get database URL from config
    from src.app.runtime.context import get_config
    app_config = get_config()
    
    # Create engine
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = app_config.database.connection_string
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # Detect column type changes
            compare_server_default=True,  # Detect default value changes
        )
        
        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
```

**alembic.ini:**
```ini
[alembic]
# Path to migration scripts
script_location = alembic

# Template file for new migrations
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(slug)s

# Timezone
timezone = UTC

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[logger_alembic]
level = INFO
handlers =
qualname = alembic
```

### Creating Migrations

**Auto-generate from model changes:**
```bash
# Generate migration from model changes
alembic revision --autogenerate -m "Add phone field to users"

# Output:
# Generating /path/to/alembic/versions/20251102_1030_add_phone_field_to_users.py
```

**Generated Migration:**
```python
"""Add phone field to users

Revision ID: abc123def456
Revises: previous_revision
Create Date: 2025-11-02 10:30:00

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

# Revision identifiers
revision = 'abc123def456'
down_revision = 'previous_revision'
branch_labels = None
depends_on = None

def upgrade() -> None:
    """Apply migration."""
    op.add_column('usertable', sa.Column('phone', sa.String(length=20), nullable=True))
    op.add_column('usertable', sa.Column('address', sa.String(length=500), nullable=True))

def downgrade() -> None:
    """Rollback migration."""
    op.drop_column('usertable', 'address')
    op.drop_column('usertable', 'phone')
```

**Manual migration (complex changes):**
```bash
# Create empty migration
alembic revision -m "Migrate user data to new schema"

# Edit generated file to add custom logic
```

### Applying Migrations

**Upgrade to latest:**
```bash
# Apply all pending migrations
alembic upgrade head

# Output:
# INFO  [alembic.runtime.migration] Running upgrade abc123 -> def456, Add phone field to users
```

**Upgrade to specific version:**
```bash
# Upgrade to specific revision
alembic upgrade abc123def456

# Upgrade one version
alembic upgrade +1

# Upgrade two versions
alembic upgrade +2
```

**Downgrade:**
```bash
# Downgrade one version
alembic downgrade -1

# Downgrade to specific version
alembic downgrade abc123

# Downgrade to base (remove all migrations)
alembic downgrade base
```

### Migration History

```bash
# Show current version
alembic current

# Show migration history
alembic history

# Show pending migrations
alembic history --verbose

# Output:
# abc123 -> def456 (head), Add phone field to users
# xyz789 -> abc123, Add user identities table
# base   -> xyz789, Initial schema
```

### Alembic Best Practices

**1. Always Review Auto-Generated Migrations:**
```bash
# Generate migration
alembic revision --autogenerate -m "Schema changes"

# REVIEW before applying!
cat alembic/versions/latest_migration.py

# Check for:
# - Unintended table drops
# - Missing columns
# - Incorrect column types
# - Missing indexes
```

**2. Test Migrations Locally:**
```bash
# Apply migration to development database
alembic upgrade head

# Test application functionality
uv run pytest

# If issues, downgrade and fix
alembic downgrade -1
```

**3. Add Data Migrations:**
```python
def upgrade() -> None:
    """Apply migration."""
    # Schema change
    op.add_column('usertable', sa.Column('full_name', sa.String(200)))
    
    # Data migration
    op.execute("""
        UPDATE usertable
        SET full_name = first_name || ' ' || last_name
        WHERE full_name IS NULL
    """)
    
    # Make column non-nullable after data migration
    op.alter_column('usertable', 'full_name', nullable=False)
```

**4. Use Transactions:**
```python
def upgrade() -> None:
    """Apply migration in transaction."""
    with op.batch_alter_table('usertable', schema=None) as batch_op:
        batch_op.add_column(sa.Column('phone', sa.String(20)))
        batch_op.add_column(sa.Column('address', sa.String(500)))
    
    # All changes applied atomically
```

## Migration Best Practices

### 1. Always Backup Before Migrations

```bash
# Create backup
docker exec api-forge-postgres pg_dump -U appuser appdb > backup_$(date +%Y%m%d_%H%M%S).sql

# Verify backup
ls -lh backup_*.sql

# Test restore (optional)
docker exec -i api-forge-postgres-dev psql -U postgres -d appdb < backup_latest.sql
```

### 2. Use Transactional Migrations

```sql
-- Good: Wrapped in transaction
BEGIN;

ALTER TABLE usertable ADD COLUMN phone VARCHAR(20);
ALTER TABLE usertable ADD COLUMN address VARCHAR(500);

COMMIT;

-- Bad: No transaction (partial application on error)
ALTER TABLE usertable ADD COLUMN phone VARCHAR(20);
ALTER TABLE usertable ADD COLUMN address VARCHAR(500);
```

### 3. Make Migrations Reversible

```python
def upgrade() -> None:
    """Add phone column."""
    op.add_column('usertable', sa.Column('phone', sa.String(20)))

def downgrade() -> None:
    """Remove phone column."""
    op.drop_column('usertable', 'phone')
```

### 4. Test Migrations on Staging

```bash
# 1. Copy production data to staging
pg_dump -h production-db -U appuser appdb | \
    psql -h staging-db -U appuser appdb

# 2. Apply migration on staging
alembic upgrade head

# 3. Run integration tests
uv run pytest tests/integration/

# 4. If successful, apply to production
```

### 5. Use Descriptive Migration Names

```bash
# Good
alembic revision -m "Add phone and address fields to users table"
alembic revision -m "Create user preferences table with foreign key"

# Bad
alembic revision -m "Update schema"
alembic revision -m "Fix bug"
```

### 6. Handle Large Data Migrations

For tables with millions of rows:

```python
def upgrade() -> None:
    """Migrate large dataset in batches."""
    
    # Add column as nullable first
    op.add_column('usertable', sa.Column('full_name', sa.String(200), nullable=True))
    
    # Update in batches (avoid long-running transaction)
    connection = op.get_bind()
    
    batch_size = 10000
    offset = 0
    
    while True:
        result = connection.execute(sa.text(f"""
            UPDATE usertable
            SET full_name = first_name || ' ' || last_name
            WHERE full_name IS NULL
            LIMIT {batch_size}
        """))
        
        if result.rowcount == 0:
            break
        
        offset += batch_size
        print(f"Processed {offset} rows")
    
    # Make column non-nullable after data is migrated
    op.alter_column('usertable', 'full_name', nullable=False)
```

## Production Deployment

### Pre-Deployment Checklist

- [ ] Backup database
- [ ] Test migration on staging
- [ ] Review migration code
- [ ] Estimate migration duration
- [ ] Plan rollback strategy
- [ ] Schedule maintenance window (if needed)
- [ ] Notify stakeholders

### Deployment Process

**1. Pre-Migration Backup:**
```bash
# Create timestamped backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
docker exec api-forge-postgres pg_dump -U appuser appdb > backup_pre_migration_$TIMESTAMP.sql

# Verify backup
ls -lh backup_pre_migration_$TIMESTAMP.sql
```

**2. Stop Application (if needed):**
```bash
# For breaking schema changes, stop app first
docker-compose -f docker-compose.prod.yml stop app

# For additive changes (new columns), app can stay running
```

**3. Apply Migration:**
```bash
# Using Alembic
alembic upgrade head

# Or manual SQL
docker exec -i api-forge-postgres psql -U appuser -d appdb < migration.sql
```

**4. Verify Migration:**
```bash
# Check schema version
alembic current

# Verify table structure
docker exec api-forge-postgres psql -U appuser -d appdb -c "\d usertable"

# Test basic queries
docker exec api-forge-postgres psql -U appuser -d appdb -c "SELECT COUNT(*) FROM usertable"
```

**5. Start Application:**
```bash
docker-compose -f docker-compose.prod.yml up -d app
```

**6. Monitor for Issues:**
```bash
# Check application logs
docker-compose -f docker-compose.prod.yml logs -f app

# Check database logs
docker-compose -f docker-compose.prod.yml logs -f postgres
```

### Zero-Downtime Migrations

For high-availability systems:

**Phase 1: Add new column (nullable):**
```sql
-- Application continues running
ALTER TABLE usertable ADD COLUMN phone VARCHAR(20);
```

**Phase 2: Deploy code that populates new column:**
```python
# Application writes to both old and new fields
user.phone = request.phone
```

**Phase 3: Backfill existing data:**
```sql
-- Run during off-peak hours
UPDATE usertable SET phone = legacy_phone WHERE phone IS NULL;
```

**Phase 4: Make column non-nullable (optional):**
```sql
ALTER TABLE usertable ALTER COLUMN phone SET NOT NULL;
```

**Phase 5: Remove old code paths:**
```python
# Stop writing to legacy_phone
```

## Rollback Strategies

### Automatic Rollback (Alembic)

```bash
# Rollback last migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade abc123

# Rollback all migrations
alembic downgrade base
```

### Manual Rollback (SQL)

**Create rollback scripts for each migration:**

**002_add_user_phone_rollback.sql:**
```sql
-- Rollback: 002_add_user_phone
-- Version: 1.1.0 -> 1.0.0

BEGIN;

-- Remove added columns
ALTER TABLE usertable DROP COLUMN IF EXISTS phone;
ALTER TABLE usertable DROP COLUMN IF EXISTS address;

-- Remove version record
DELETE FROM schema_version WHERE version = '1.1.0';

COMMIT;
```

### Database Restore

**Last resort: Restore from backup:**
```bash
# 1. Stop application
docker-compose -f docker-compose.prod.yml stop app

# 2. Drop database
docker exec api-forge-postgres psql -U postgres -c "DROP DATABASE appdb"

# 3. Create database
docker exec api-forge-postgres psql -U postgres -c "CREATE DATABASE appdb OWNER appowner"

# 4. Restore backup
docker exec -i api-forge-postgres psql -U appuser -d appdb < backup_pre_migration.sql

# 5. Verify
docker exec api-forge-postgres psql -U appuser -d appdb -c "SELECT COUNT(*) FROM usertable"

# 6. Start application
docker-compose -f docker-compose.prod.yml up -d app
```

## Related Documentation

- [Main Documentation](./main.md) - PostgreSQL overview
- [Configuration Guide](./configuration.md) - Connection settings
- [Usage Guide](./usage.md) - Code examples
- [Security Guide](./security.md) - TLS and authentication
- [Production Deployment](../PRODUCTION_DEPLOYMENT.md) - Production setup
