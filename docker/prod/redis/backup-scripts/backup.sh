#!/bin/bash
# Redis backup script for production

set -e

# Configuration
BACKUP_DIR="/var/lib/redis/backups"
DATA_DIR="/data"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="redis_backup_${TIMESTAMP}"
RETENTION_DAYS=7

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo "Starting Redis backup..."

# Trigger a background save
redis-cli BGSAVE

# Wait for background save to complete
while [ "$(redis-cli LASTSAVE)" = "$(redis-cli LASTSAVE)" ]; do
    echo "Waiting for background save to complete..."
    sleep 1
done

# Copy the RDB file
if [ -f "$DATA_DIR/dump.rdb" ]; then
    cp "$DATA_DIR/dump.rdb" "$BACKUP_DIR/${BACKUP_NAME}.rdb"
    echo "RDB backup created: ${BACKUP_NAME}.rdb"
else
    echo "Warning: No RDB file found"
fi

# Copy the AOF file if it exists
if [ -f "$DATA_DIR/appendonly.aof" ]; then
    cp "$DATA_DIR/appendonly.aof" "$BACKUP_DIR/${BACKUP_NAME}.aof"
    echo "AOF backup created: ${BACKUP_NAME}.aof"
fi

# Compress backups
if [ -f "$BACKUP_DIR/${BACKUP_NAME}.rdb" ]; then
    gzip "$BACKUP_DIR/${BACKUP_NAME}.rdb"
fi

if [ -f "$BACKUP_DIR/${BACKUP_NAME}.aof" ]; then
    gzip "$BACKUP_DIR/${BACKUP_NAME}.aof"
fi

# Generate checksums
if [ -f "$BACKUP_DIR/${BACKUP_NAME}.rdb.gz" ]; then
    sha256sum "$BACKUP_DIR/${BACKUP_NAME}.rdb.gz" > "$BACKUP_DIR/${BACKUP_NAME}.rdb.gz.sha256"
fi

if [ -f "$BACKUP_DIR/${BACKUP_NAME}.aof.gz" ]; then
    sha256sum "$BACKUP_DIR/${BACKUP_NAME}.aof.gz" > "$BACKUP_DIR/${BACKUP_NAME}.aof.gz.sha256"
fi

echo "Backup completed successfully"

# Cleanup old backups
find "$BACKUP_DIR" -name "redis_backup_*.rdb.gz" -type f -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "redis_backup_*.aof.gz" -type f -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "redis_backup_*.sha256" -type f -mtime +$RETENTION_DAYS -delete

echo "Cleanup completed. Backups older than $RETENTION_DAYS days have been removed."

# List current backups
echo "Current backups:"
ls -la "$BACKUP_DIR"/redis_backup_*