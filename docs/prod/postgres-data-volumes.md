## 🗂️ **Working with Data Volumes**

### **Volume Management Commands**

#### **List PostgreSQL Volumes**
```bash
# List all project volumes
docker volume ls | grep api_project_template3

# Inspect specific volume
docker volume inspect api_project_template3_postgres_data
docker volume inspect api_project_template3_postgres_backups

# Check volume usage
docker system df -v | grep postgres
```

#### **Volume Backup and Restore**
```bash
# Backup volume to tar archive
docker run --rm -v api_project_template3_postgres_data:/source -v $(pwd):/backup \
  alpine tar czf /backup/postgres_volume_backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /source .

# Restore volume from tar archive
docker run --rm -v api_project_template3_postgres_data:/target -v $(pwd):/backup \
  alpine tar xzf /backup/postgres_volume_backup_20241010_120000.tar.gz -C /target

# Copy volume to another volume
docker run --rm -v api_project_template3_postgres_data:/source -v new_postgres_data:/target \
  alpine sh -c "cd /source && cp -a . /target"
```

### **Data Directory Operations**

#### **Accessing Data Files**
```bash
# Browse data directory contents
docker exec api_project_template3_postgres_1 ls -la /var/lib/postgresql/data/

# Check database files
docker exec api_project_template3_postgres_1 ls -la /var/lib/postgresql/data/base/

# View configuration files
docker exec api_project_template3_postgres_1 cat /var/lib/postgresql/data/postgresql.conf
docker exec api_project_template3_postgres_1 cat /var/lib/postgresql/data/pg_hba.conf

# Check log files
docker exec api_project_template3_postgres_1 ls -la /var/lib/postgresql/data/log/
```

#### **Volume Size Monitoring**
```bash
# Check volume disk usage
docker exec api_project_template3_postgres_1 df -h /var/lib/postgresql/data

# Check database size from inside PostgreSQL
docker exec api_project_template3_postgres_1 bash -c \
  'PGPASSWORD=$(cat /run/secrets/postgres_password) psql -U appuser -d appdb -c "
SELECT 
    pg_size_pretty(pg_database_size(current_database())) AS database_size,
    pg_size_pretty(pg_total_relation_size('\''pg_stat_statements'\'')) AS stats_size;
"'

# Check individual table sizes
docker exec api_project_template3_postgres_1 bash -c \
  'PGPASSWORD=$(cat /run/secrets/postgres_password) psql -U appuser -d appdb -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'\''.'\'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = '\''app'\''
ORDER BY pg_total_relation_size(schemaname||'\''.'\'||tablename) DESC;
"'
```

### **Volume Migration and Cloning**

#### **Migrate to New Host**
```bash
# 1. Stop the PostgreSQL service
docker-compose -f docker-compose.prod.yml stop postgres

# 2. Create volume backup
docker run --rm -v api_project_template3_postgres_data:/source -v $(pwd):/backup \
  alpine tar czf /backup/postgres_migration_$(date +%Y%m%d).tar.gz -C /source .

# 3. Transfer backup to new host
scp postgres_migration_20241010.tar.gz user@newhost:/path/to/project/

# 4. On new host, restore volume
docker run --rm -v api_project_template3_postgres_data:/target -v $(pwd):/backup \
  alpine tar xzf /backup/postgres_migration_20241010.tar.gz -C /target

# 5. Start PostgreSQL on new host
docker-compose -f docker-compose.prod.yml up -d postgres
```

#### **Create Development Copy**
```bash
# 1. Create new volume for development
docker volume create dev_postgres_data

# 2. Copy production data to development
docker run --rm \
  -v api_project_template3_postgres_data:/source \
  -v dev_postgres_data:/target \
  alpine sh -c "cd /source && cp -a . /target"

# 3. Update docker-compose for development
# Modify docker-compose.dev.yml to use dev_postgres_data
```

### **Volume Cleanup and Maintenance**

#### **Clean Unused Volumes**
```bash
# List unused volumes
docker volume ls -f dangling=true

# Remove unused volumes (BE CAREFUL!)
docker volume prune

# Remove specific volume (only when service is stopped)
docker-compose -f docker-compose.prod.yml down
docker volume rm api_project_template3_postgres_data
```

#### **Volume Space Management**
```bash
# Check volume usage across all containers
docker system df -v

# Find large files in data directory
docker exec api_project_template3_postgres_1 find /var/lib/postgresql/data -type f -size +100M -exec ls -lh {} \;

# PostgreSQL vacuum to reclaim space
docker exec api_project_template3_postgres_1 bash -c \
  'PGPASSWORD=$(cat /run/secrets/postgres_password) psql -U appuser -d appdb -c "VACUUM FULL;"'

# Analyze table bloat
docker exec api_project_template3_postgres_1 bash -c \
  'PGPASSWORD=$(cat /run/secrets/postgres_password) psql -U appuser -d appdb -c "
SELECT 
    schemaname, 
    tablename, 
    n_dead_tup, 
    n_live_tup,
    round(n_dead_tup * 100.0 / (n_live_tup + n_dead_tup), 2) AS dead_ratio
FROM pg_stat_user_tables 
WHERE n_dead_tup > 0
ORDER BY dead_ratio DESC;
"'
```

### **Bind Mount Management**

#### **Working with Host Directories**
```bash
# Check host directory permissions
ls -la data/postgres/
ls -la data/postgres-backups/

# Fix permissions if needed
sudo chown -R 999:999 data/postgres/
sudo chown -R 999:999 data/postgres-backups/

# Set proper directory permissions
sudo chmod 700 data/postgres/
sudo chmod 755 data/postgres-backups/
```

#### **Host-Level Backup**
```bash
# Stop PostgreSQL for consistent backup
docker-compose -f docker-compose.prod.yml stop postgres

# Create host-level backup
sudo tar czf postgres_host_backup_$(date +%Y%m%d_%H%M%S).tar.gz data/postgres/

# Sync to remote backup location
rsync -av data/postgres/ backup-server:/backups/postgres/$(date +%Y%m%d)/

# Restart PostgreSQL
docker-compose -f docker-compose.prod.yml start postgres
```

### **Volume Security**

#### **Encrypt Volume Data**
```bash
# For production environments, consider encrypting the host filesystem
# Example with LUKS encryption:

# 1. Create encrypted disk partition
sudo cryptsetup luksFormat /dev/sdb1

# 2. Open encrypted partition
sudo cryptsetup luksOpen /dev/sdb1 postgres_encrypted

# 3. Create filesystem
sudo mkfs.ext4 /dev/mapper/postgres_encrypted

# 4. Mount encrypted partition
sudo mount /dev/mapper/postgres_encrypted /var/lib/docker/volumes/

# 5. Update Docker to use encrypted storage
```

#### **Volume Access Control**
```bash
# Restrict access to postgres data directories
sudo chmod 700 data/postgres/
sudo chown -R 999:999 data/postgres/

# Set immutable attributes on critical files (Linux only)
sudo chattr +i data/postgres/postgresql.conf
sudo chattr +i data/postgres/pg_hba.conf

# Remove immutable when updates needed
sudo chattr -i data/postgres/postgresql.conf
```

### **Volume Monitoring and Alerts**

#### **Disk Space Monitoring**
```bash
# Create monitoring script
cat > monitor_postgres_volumes.sh << 'EOF'
#!/bin/bash
THRESHOLD=80  # Alert when 80% full

# Check data volume usage
USAGE=$(docker exec api_project_template3_postgres_1 df /var/lib/postgresql/data | awk 'NR==2 {print $5}' | sed 's/%//')

if [ "$USAGE" -gt "$THRESHOLD" ]; then
    echo "WARNING: PostgreSQL data volume is ${USAGE}% full"
    # Send alert (email, Slack, etc.)
fi

# Check backup volume usage
BACKUP_USAGE=$(docker exec api_project_template3_postgres_1 df /var/lib/postgresql/backups | awk 'NR==2 {print $5}' | sed 's/%//')

if [ "$BACKUP_USAGE" -gt "$THRESHOLD" ]; then
    echo "WARNING: PostgreSQL backup volume is ${BACKUP_USAGE}% full"
fi
EOF

chmod +x monitor_postgres_volumes.sh

# Run via cron every hour
echo "0 * * * * /path/to/monitor_postgres_volumes.sh" | crontab -
```

#### **Volume Health Checks**
```bash
# Check filesystem health
docker exec api_project_template3_postgres_1 fsck -n /var/lib/postgresql/data

# Check for file corruption
docker exec api_project_template3_postgres_1 bash -c \
  'PGPASSWORD=$(cat /run/secrets/postgres_password) psql -U appuser -d appdb -c "
SELECT datname, pg_size_pretty(pg_database_size(datname)) 
FROM pg_database 
WHERE datistemplate = false;
"'

# PostgreSQL consistency check
docker exec api_project_template3_postgres_1 bash -c \
  'PGPASSWORD=$(cat /run/secrets/postgres_password) pg_dump -U appuser -d appdb --schema-only > /tmp/schema_check.sql && echo "Schema dump successful"'
```

### **Disaster Recovery**

#### **Point-in-Time Recovery Setup**
```bash
# Enable continuous archiving (in postgresql.conf)
archive_mode = on
archive_command = 'cp %p /var/lib/postgresql/backups/wal/%f'

# Create WAL archive directory
docker exec api_project_template3_postgres_1 mkdir -p /var/lib/postgresql/backups/wal

# Base backup for PITR
docker exec api_project_template3_postgres_1 bash -c \
  'PGPASSWORD=$(cat /run/secrets/postgres_password) pg_basebackup -U appuser -D /var/lib/postgresql/backups/base_$(date +%Y%m%d_%H%M%S) -Ft -z -P'
```

#### **Emergency Volume Recovery**
```bash
# If volume is corrupted, restore from backup
# 1. Stop PostgreSQL
docker-compose -f docker-compose.prod.yml stop postgres

# 2. Remove corrupted volume
docker volume rm api_project_template3_postgres_data

# 3. Recreate volume
docker volume create api_project_template3_postgres_data

# 4. Restore from backup
docker run --rm -v api_project_template3_postgres_data:/target -v $(pwd):/backup \
  alpine tar xzf /backup/postgres_volume_backup_latest.tar.gz -C /target

# 5. Start PostgreSQL
docker-compose -f docker-compose.prod.yml up -d postgres
```

---

---
