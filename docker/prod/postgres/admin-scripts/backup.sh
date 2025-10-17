#!/bin/bash
# Automated PostgreSQL backup script for production

set -e

# Configuration
BACKUP_DIR="/var/lib/postgresql/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="backup_${POSTGRES_DB}_${TIMESTAMP}"
RETENTION_DAYS=7

# Use backup user for secure, read-only access
BACKUP_USER="backup"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "Starting backup of database: $POSTGRES_DB using backup user: $BACKUP_USER"

# Set backup password for pg_dump
export PGPASSWORD=$(cat /run/secrets/backup_password)

# Create compressed backup using backup user
pg_dump \
    --host=localhost \
    --port=5432 \
    --username="$BACKUP_USER" \
    --dbname="$POSTGRES_DB" \
    --format=custom \
    --compress=9 \
    --file="$BACKUP_DIR/${BACKUP_NAME}.dump"

# Create SQL backup for easier restore using backup user
pg_dump \
    --host=localhost \
    --port=5432 \
    --username="$BACKUP_USER" \
    --dbname="$POSTGRES_DB" \
    --format=plain \
    --file="$BACKUP_DIR/${BACKUP_NAME}.sql"

# Compress SQL backup
gzip "$BACKUP_DIR/${BACKUP_NAME}.sql"

# Generate checksum
sha256sum "$BACKUP_DIR/${BACKUP_NAME}.dump" > "$BACKUP_DIR/${BACKUP_NAME}.dump.sha256"
sha256sum "$BACKUP_DIR/${BACKUP_NAME}.sql.gz" > "$BACKUP_DIR/${BACKUP_NAME}.sql.gz.sha256"

echo "Backup completed: ${BACKUP_NAME}"

# Cleanup old backups
find "$BACKUP_DIR" -name "backup_${POSTGRES_DB}_*.dump" -type f -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "backup_${POSTGRES_DB}_*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "backup_${POSTGRES_DB}_*.sha256" -type f -mtime +$RETENTION_DAYS -delete

echo "Cleanup completed. Backups older than $RETENTION_DAYS days have been removed."

# List current backups
echo "Current backups:"
ls -la "$BACKUP_DIR"/backup_${POSTGRES_DB}_*