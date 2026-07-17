# Deployment Documentation

This document describes the host-level configurations and services required to run the NSE India Equity Momentum Scanner in production.

## Environment Variables (.env)
A `.env` file must be located in the repository root directory on the host VPS. See [.env.example](file:///C:/Users/hiren/.gemini/antigravity/scratch/nse-momentum-scanner/.env.example) for required configuration keys.

Ensure file permissions are restricted to the owner:
```bash
chmod 600 .env
```

## Market Data Catch-Up

The backend scheduler now self-heals after outages (expired Fyers token, missed 7 PM IST job, or container restart):

1. On startup and every weekday at 7:00 PM IST, it runs a **catch-up pipeline**.
2. Symbols with fewer than 200 daily candles are history-backfilled (~450 calendar days) so trend/VCP scoring can run.
3. Missing weekdays since the latest candle date are ingested from Fyers + NSE Bhavcopy (capped at 15 weekdays per run), then scored.
4. Dashboard **Trigger Ingest + Scan** calls the same catch-up path (default `POST /api/v1/scanner/scan` with `ingest: true`).
5. `GET /api/v1/scanner/data-health` reports last candle date, scoreable-universe coverage, and staleness warnings.

If Elite Signals stay empty after a healthy catch-up, that means no symbol met the simultaneous entry gates (score ≥ 85, vol ≥ 2×, trend pass, top-sector, breakout candle quality, fundamental gate) — not that the scanner failed to run.

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
