#!/bin/bash
# Nightly PostgreSQL backup — run via cron on the Oracle VPS
# Cron configuration:
# 0 2 * * * /home/ubuntu/nse-momentum-scanner/backend/scripts/backup_db.sh >> /home/ubuntu/db_backups/backup.log 2>&1

BACKUP_DIR="/home/ubuntu/db_backups"
DATE=$(date +%Y%m%d_%H%M%S)
FILENAME="nse_scanner_backup_${DATE}.sql.gz"

mkdir -p "$BACKUP_DIR"

docker exec nse_scanner_db pg_dump -U postgres nse_scanner \
    | gzip > "${BACKUP_DIR}/${FILENAME}"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: ${FILENAME}"
