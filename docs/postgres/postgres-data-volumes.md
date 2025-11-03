# 🗂️ Working with Data Volumes

> **Database Reset Script:**
> Use `./reset_database.sh` for full cleanup of volumes, containers, and bind mounts.
> This script safely handles the complexity of Docker named volumes and bind mounts.

---

## 🚀 Quick Start: Reset & Launch

```bash
# Complete database cleanup (removes all data!)
./reset_database.sh

# Start fresh PostgreSQL
docker-compose -f docker-compose.prod.yml up postgres

# Optional: also remove Docker images
./reset_database.sh --remove-images
```

---

## 📦 Volume Management

<details>
<summary><strong>🔍 List & Inspect Volumes</strong></summary>

```bash
# List PostgreSQL-related volumes
docker volume ls | grep postgres

# Inspect specific volumes
docker volume inspect postgres_data
docker volume inspect postgres_backups

# Check volume disk usage
docker system df -v | grep postgres
```

</details>

<details>
<summary><strong>💾 Backup & Restore Volumes</strong></summary>

```bash
# Backup volume to a tar archive
docker run --rm \
  -v postgres_data:/source \
  -v $(pwd):/backup \
  alpine tar czf /backup/postgres_volume_backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /source .

# Restore from backup
docker run --rm \
  -v postgres_data:/target \
  -v $(pwd):/backup \
  alpine tar xzf /backup/postgres_volume_backup_<timestamp>.tar.gz -C /target

# Copy one volume to another
docker run --rm \
  -v postgres_data:/source \
  -v new_postgres_data:/target \
  alpine sh -c "cd /source && cp -a . /target"
```

</details>

<details>
<summary><strong>🗃️ Database-Level Backups</strong></summary>

```bash
# SQL dump using backup user (recommended)
BACKUP_PASSWORD=$(cat secrets/backup_password.txt)
docker exec -e PGPASSWORD="$BACKUP_PASSWORD" app_data_postgres_db \
  pg_dump -U backup -d appdb --schema=app > backup_$(date +%Y%m%d_%H%M%S).sql

# Full database dump using main user
POSTGRES_PASSWORD=$(cat secrets/postgres_password.txt)
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" app_data_postgres_db \
  pg_dump -U appuser -d appdb > full_backup_$(date +%Y%m%d_%H%M%S).sql

# Restore from SQL dump
docker exec -i app_data_postgres_db \
  psql -U appuser -d appdb < backup_file.sql
```

</details>

---

## 🗃️ Data Directory Operations

<details>
<summary><strong>📁 Accessing Data Files</strong></summary>

```bash
# Browse data directory
docker exec app_data_postgres_db ls -la /var/lib/postgresql/data/

# View configuration files
docker exec app_data_postgres_db cat /var/lib/postgresql/data/postgresql.conf
docker exec app_data_postgres_db cat /var/lib/postgresql/data/pg_hba.conf

# View logs
docker exec app_data_postgres_db ls -la /var/lib/postgresql/data/log/
```

</details>

<details>
<summary><strong>🧮 Volume Size Monitoring</strong></summary>

```bash
# Check volume disk usage
docker exec app_data_postgres_db df -h /var/lib/postgresql/data

# Check database size from PostgreSQL
POSTGRES_PASSWORD=$(cat secrets/postgres_password.txt)
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" app_data_postgres_db \
  psql -U appuser -d appdb -c "
SELECT 
    pg_size_pretty(pg_database_size(current_database())) AS database_size,
    pg_size_pretty(pg_total_relation_size('pg_stat_statements')) AS stats_size;"
```

</details>

<details>
<summary><strong>👤 Test Backup User Access</strong></summary>

```bash
# Test read access
BACKUP_PASSWORD=$(cat secrets/backup_password.txt)
docker exec -e PGPASSWORD="$BACKUP_PASSWORD" app_data_postgres_db \
  psql -U backup -d appdb -c "SELECT current_user, current_database();"

# Test write access (should fail)
docker exec -e PGPASSWORD="$BACKUP_PASSWORD" app_data_postgres_db \
  psql -U backup -d appdb -c "CREATE TABLE test_readonly (id SERIAL);"
```

</details>

<details>
<summary><strong>📊 Check Individual Table Sizes</strong></summary>

```bash
# Check table sizes in app schema
POSTGRES_PASSWORD=$(cat secrets/postgres_password.txt)
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" app_data_postgres_db \
  psql -U appuser -d appdb -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname = 'app'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

</details>

---

## 🧳 Volume Migration & Cloning

<details>
<summary><strong>🚚 Migrate to New Host</strong></summary>

```bash
# Stop PostgreSQL
docker-compose -f docker-compose.prod.yml stop postgres

# Create volume backup
docker run --rm -v postgres_data:/source -v $(pwd):/backup \
  alpine tar czf /backup/postgres_migration_$(date +%Y%m%d).tar.gz -C /source .

# Transfer backup
scp postgres_migration_*.tar.gz user@newhost:/path/to/project/

# Restore on new host
docker run --rm -v postgres_data:/target -v $(pwd):/backup \
  alpine tar xzf /backup/postgres_migration_*.tar.gz -C /target

# Start PostgreSQL
docker-compose -f docker-compose.prod.yml up -d postgres
```

</details>

<details>
<summary><strong>🧩 Create Development Copy</strong></summary>

```bash
# Create new volume
docker volume create dev_postgres_data

# Copy production data
docker run --rm \
  -v postgres_data:/source \
  -v dev_postgres_data:/target \
  alpine sh -c "cd /source && cp -a . /target"

# Update docker-compose.dev.yml to use dev_postgres_data
```

</details>

---

## 🧹 Cleanup & Maintenance

<details>
<summary><strong>⚙️ Automated Cleanup (Recommended)</strong></summary>

```bash
./reset_database.sh                 # Basic cleanup
./reset_database.sh --remove-images # With image cleanup
./reset_database.sh --help          # Show all options
```

</details>

<details>
<summary><strong>🧰 Manual Cleanup (Advanced)</strong></summary>

```bash
docker-compose -f docker-compose.prod.yml down -v
sudo rm -rf data/postgres data/postgres-backups
mkdir -p data/postgres data/postgres-backups
docker volume prune
```

</details>

<details>
<summary><strong>🔐 Access Control & Permissions</strong></summary>

```bash
sudo chmod 700 data/postgres/
sudo chown -R 999:999 data/postgres/
```

</details>

<details>
<summary><strong>💡 Space Management</strong></summary>

```bash
# Check Docker system usage
docker system df -v

# Find large files in data directory
docker exec app_data_postgres_db \
  find /var/lib/postgresql/data -type f -size +100M -exec ls -lh {} \;

# PostgreSQL maintenance (reclaim space)
POSTGRES_PASSWORD=$(cat secrets/postgres_password.txt)
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" app_data_postgres_db \
  psql -U appuser -d appdb -c "VACUUM FULL;"

# Analyze table bloat
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" app_data_postgres_db \
  psql -U appuser -d appdb -c "
SELECT 
    schemaname, 
    tablename, 
    n_dead_tup, 
    n_live_tup,
    CASE WHEN (n_live_tup + n_dead_tup) > 0 
         THEN round(n_dead_tup * 100.0 / (n_live_tup + n_dead_tup), 2) 
         ELSE 0 END AS dead_ratio
FROM pg_stat_user_tables 
WHERE n_dead_tup > 0
ORDER BY dead_ratio DESC;"
```

</details>

---

## 🧱 Bind Mount Management

<details>
<summary><strong>📂 Host Directory Permissions</strong></summary>

```bash
ls -la data/postgres/ data/postgres-backups/
sudo chown -R 999:999 data/postgres/ data/postgres-backups/
sudo chmod 700 data/postgres/
sudo chmod 755 data/postgres-backups/
```

</details>

<details>
<summary><strong>🗄️ Host-Level Backups</strong></summary>

```bash
docker-compose -f docker-compose.prod.yml stop postgres
sudo tar czf postgres_host_backup_$(date +%Y%m%d_%H%M%S).tar.gz data/postgres/
rsync -av data/postgres/ backup-server:/backups/postgres/$(date +%Y%m%d)/
docker-compose -f docker-compose.prod.yml start postgres
```

</details>

---

## 🔒 Volume Security

<details>
<summary><strong>🧱 Encrypt Volume Data</strong></summary>

```bash
sudo cryptsetup luksFormat /dev/sdb1
sudo cryptsetup luksOpen /dev/sdb1 postgres_encrypted
sudo mkfs.ext4 /dev/mapper/postgres_encrypted
sudo mount /dev/mapper/postgres_encrypted /var/lib/docker/volumes/
```

</details>

<details>
<summary><strong>🛡️ Lock Critical Files</strong></summary>

```bash
sudo chattr +i data/postgres/postgresql.conf
sudo chattr +i data/postgres/pg_hba.conf

# Remove immutability when updates are needed
sudo chattr -i data/postgres/postgresql.conf
```

</details>

---

## 📈 Monitoring & Alerts

<details>
<summary><strong>🧭 Disk Usage Monitoring Script</strong></summary>

```bash
cat > monitor_postgres_volumes.sh << 'EOF'
#!/bin/bash
THRESHOLD=80
USAGE=$(docker exec app_data_postgres_db df /var/lib/postgresql/data | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$USAGE" -gt "$THRESHOLD" ]; then
  echo "WARNING: PostgreSQL data volume is ${USAGE}% full"
fi
EOF

chmod +x monitor_postgres_volumes.sh
echo "0 * * * * /path/to/monitor_postgres_volumes.sh" | crontab -
```

</details>

<details>
<summary><strong>🩺 Volume Health Checks</strong></summary>

```bash
docker exec app_data_postgres_db fsck -n /var/lib/postgresql/data
```

</details>

---

## 🔧 Troubleshooting

<details>
<summary><strong>🚨 Common Volume Issues</strong></summary>

```bash
# Volume permission issues
sudo chown -R 999:999 data/postgres/
sudo chmod 700 data/postgres/

# Check if PostgreSQL is running
docker-compose -f docker-compose.prod.yml ps postgres

# Check container logs
docker-compose -f docker-compose.prod.yml logs postgres

# Test database connectivity
POSTGRES_PASSWORD=$(cat secrets/postgres_password.txt)
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" app_data_postgres_db \
  pg_isready -U appuser -d appdb

# Check available disk space
docker exec app_data_postgres_db df -h /var/lib/postgresql/data
```

</details>

<details>
<summary><strong>🔄 Reset When Things Go Wrong</strong></summary>

```bash
# Nuclear option: complete reset
./reset_database.sh --remove-images

# Then start fresh
docker-compose -f docker-compose.prod.yml up postgres
```

</details>

---

## 🆘 Disaster Recovery

<details>
<summary><strong>🕒 Point-in-Time Recovery (PITR)</strong></summary>

```bash
# Enable continuous archiving (add to postgresql.conf)
# archive_mode = on
# archive_command = 'cp %p /var/lib/postgresql/backups/wal/%f'

# Create WAL archive directory
docker exec app_data_postgres_db \
  mkdir -p /var/lib/postgresql/backups/wal

# Create base backup for PITR
POSTGRES_PASSWORD=$(cat secrets/postgres_password.txt)
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" app_data_postgres_db \
  pg_basebackup -U appuser -D /var/lib/postgresql/backups/base_$(date +%Y%m%d_%H%M%S) -Ft -z -P
```

</details>

<details>
<summary><strong>🧯 Emergency Recovery</strong></summary>

```bash
docker-compose -f docker-compose.prod.yml stop postgres
docker volume rm postgres_data
docker volume create postgres_data
docker run --rm -v postgres_data:/target -v $(pwd):/backup \
  alpine tar xzf /backup/postgres_volume_backup_latest.tar.gz -C /target
docker-compose -f docker-compose.prod.yml up -d postgres
```

</details>