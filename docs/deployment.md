# Deployment Documentation

This document describes the host-level configurations and services required to run the NSE India Equity Momentum Scanner in production.

## Environment Variables (.env)
A `.env` file must be located in the repository root directory on the host VPS. See [.env.example](file:///C:/Users/hiren/.gemini/antigravity/scratch/nse-momentum-scanner/.env.example) for required configuration keys.

Ensure file permissions are restricted to the owner:
```bash
chmod 600 .env
```

## Nightly Database Backups
A nightly cron job must be configured on the host Oracle VPS to run the PostgreSQL database backup script daily at 2:00 AM IST.

### Configuration Instructions:
1. Log in to the Oracle VPS.
2. Edit the cron table for the `ubuntu` user:
   ```bash
   crontab -e
   ```
3. Append the following cron line:
   ```cron
   0 2 * * * /home/ubuntu/nse-momentum-scanner/backend/scripts/backup_db.sh >> /home/ubuntu/db_backups/backup.log 2>&1
   ```
4. Save and close. The backups will be compressed and saved on the host system under `/home/ubuntu/db_backups/`. Backups older than 7 days will be pruned automatically.
