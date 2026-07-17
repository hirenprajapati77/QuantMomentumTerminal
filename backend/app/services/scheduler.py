import asyncio
import datetime
import logging
import time
from zoneinfo import ZoneInfo
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.app.storage.database import SessionLocal
from backend.app.services.market_data import MarketDataService
from backend.app.services.scanner import ScannerService, set_scanner_running
from backend.app.models.universe import UniverseStock
from backend.app.models.candle import DailyCandle

logger = logging.getLogger("nse_scanner.scheduler")

# Trend scoring needs ~200 trading days; keep a buffer for weekends/holidays.
MIN_HISTORY_CANDLES = 200
HISTORY_LOOKBACK_DAYS = 450
# Cap catch-up so a long outage cannot block the event loop worker forever.
MAX_CATCHUP_DAYS = 15


def get_ist_now() -> datetime.datetime:
    """
    Returns current time in Indian Standard Time (IST = UTC + 5:30).
    """
    return datetime.datetime.now(ZoneInfo("Asia/Kolkata"))


def iter_weekdays(start: datetime.date, end: datetime.date):
    """Yield weekdays from start..end inclusive."""
    if start > end:
        return
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            yield cur
        cur += datetime.timedelta(days=1)


def get_latest_candle_date(db: Session) -> datetime.date | None:
    return db.query(func.max(DailyCandle.date)).scalar()


def get_short_history_symbols(db: Session, active_symbols: list[str], min_candles: int = MIN_HISTORY_CANDLES) -> list[str]:
    """Return active symbols that do not yet have enough candle history to score reliably."""
    if not active_symbols:
        return []
    rows = (
        db.query(DailyCandle.symbol, func.count(DailyCandle.date))
        .filter(DailyCandle.symbol.in_(active_symbols))
        .group_by(DailyCandle.symbol)
        .all()
    )
    counts = {sym: cnt for sym, cnt in rows}
    return [sym for sym in active_symbols if counts.get(sym, 0) < min_candles]


def backfill_short_history_symbols(
    db: Session,
    market_data_service: MarketDataService,
    active_symbols: list[str],
    through_date: datetime.date,
) -> int:
    """
    Ingest multi-month history for symbols that currently have too few candles.
    Live diagnosis (Jul 2026): ~half the active universe only had ~26 days of
    history after an interrupted backfill, so trend/VCP scoring could never fire.
    """
    short = get_short_history_symbols(db, active_symbols)
    if not short:
        logger.info("All active symbols have sufficient candle history.")
        return 0

    start_date = through_date - datetime.timedelta(days=HISTORY_LOOKBACK_DAYS)
    logger.warning(
        "Backfilling history for %d short-history symbols from %s to %s...",
        len(short), start_date, through_date
    )
    saved = 0
    bhavcopy_cache: dict = {}
    for sym in short:
        try:
            count = market_data_service.ingest_symbol_data(
                db, sym, start_date, through_date, bhavcopy_cache
            )
            saved += count
            time.sleep(0.35)  # Fyers rate-limit guard
        except Exception as e:
            logger.error(f"History backfill failed for {sym}: {e}")
    logger.info(f"Short-history backfill complete. Candle upserts: {saved}")
    return saved


def sync_daily_ingestion_and_scan(target_date: datetime.date) -> bool:
    """
    Synchronous implementation of daily ingestion and scan.
    Runs inside a worker thread via asyncio.to_thread to avoid blocking event loop.

    Returns True if the scanner ran for target_date, False if ingestion produced
    no candles (holiday / upstream failure) and scoring was skipped.
    """
    logger.info(f"Starting synchronous daily ingestion and scan worker for date: {target_date}")
    market_data_service = MarketDataService()
    scanner_service = ScannerService()

    db = SessionLocal()
    try:
        # Check active symbols
        active_stocks = db.query(UniverseStock).filter(UniverseStock.is_active == True).all()
        active_symbols = [s.symbol for s in active_stocks]
        if not active_symbols:
            logger.warning("No active symbols found. Daily ingestion skipped.")
            return False

        logger.info(f"Active universe has {len(active_symbols)} symbols to update.")

        # Try downloading Bhavcopy with 4 attempts and 15-minute delay
        bhav_df = None
        for attempt in range(1, 5):
            try:
                logger.info(f"Attempting to download NSE Bhavcopy for {target_date} (Attempt {attempt}/4)...")
                bhav_df = market_data_service.download_nse_bhavcopy(target_date)
                if not bhav_df.empty:
                    logger.info("NSE Bhavcopy successfully downloaded.")
                    break
                else:
                    logger.warning(f"Bhavcopy for {target_date} returned empty. Attempt {attempt} failed.")
            except Exception as e:
                logger.warning(f"Bhavcopy download failed on attempt {attempt}: {e}")

            if attempt < 4:
                logger.info("Waiting 15 minutes before retrying...")
                time.sleep(15 * 60)  # 15 minutes (synchronous sleep in worker thread)

        if bhav_df is None or bhav_df.empty:
            logger.error(f"Failed to fetch Bhavcopy for {target_date} after 4 attempts. Proceeding with OHLCV only.")
            bhavcopy_cache = {}
        else:
            bhavcopy_cache = {target_date: bhav_df}

        # Ingest daily candle for each active symbol
        logger.info("Ingesting OHLCV and delivery data for active symbols...")
        ingested = 0
        for sym in active_symbols:
            try:
                count = market_data_service.ingest_symbol_data(
                    db, sym, target_date, target_date, bhavcopy_cache
                )
                if count:
                    ingested += 1
                # Prevent Fyers API rate limiting (HTTP 429)
                time.sleep(0.35)
            except Exception as e:
                logger.error(f"Failed to ingest data for symbol {sym} on {target_date}: {e}")

        logger.info(f"Ingestion finished for {target_date}: {ingested}/{len(active_symbols)} symbols updated.")

        # Skip scanner when nothing was ingested (weekend/holiday / API failure)
        if ingested == 0:
            logger.warning(
                f"No candles ingested for {target_date}; skipping scanner "
                "(likely market holiday or upstream data failure)."
            )
            return False

        # Run Scanner to cache today's scores and entry signals
        logger.info("Running daily composite strategy scanner...")
        # Parent catch-up holds the busy lock; avoid clearing it mid-pipeline.
        scanner_service.run_daily_scan(db, target_date, manage_status_lock=False)
        logger.info("Daily ingestion and scanner run completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Scheduler worker encountered an error: {e}", exc_info=True)
        from backend.app.core.alerts import send_telegram_alert
        send_telegram_alert(
            f"⚠️ <b>NSE Scanner Alert</b>\n"
            f"Daily scan failed on {target_date}\n"
            f"Error: {type(e).__name__}: {str(e)[:200]}"
        )
        return False
    finally:
        db.close()


def sync_catch_up_pipeline(through_date: datetime.date | None = None):
    """
    Repair gaps caused by expired Fyers tokens / missed scheduler runs:
      1) Backfill short-history symbols so trend/VCP can score
      2) Ingest+scan each missing weekday up to through_date
    """
    through_date = through_date or get_ist_now().date()
    logger.info(f"Starting catch-up pipeline through {through_date}...")
    set_scanner_running(True)

    market_data_service = MarketDataService()
    db = SessionLocal()
    try:
        active_stocks = db.query(UniverseStock).filter(UniverseStock.is_active == True).all()
        active_symbols = [s.symbol for s in active_stocks]
        if not active_symbols:
            logger.warning("Catch-up skipped: no active symbols.")
            return

        backfilled = backfill_short_history_symbols(db, market_data_service, active_symbols, through_date)

        latest = get_latest_candle_date(db)
        if latest is None:
            # Cold start: ingest today only; full history already attempted above.
            logger.warning("No candles in DB after history backfill; ingesting through_date only.")
            sync_daily_ingestion_and_scan(through_date)
            return

        start = latest + datetime.timedelta(days=1)
        if start > through_date:
            logger.info(f"Candle data already current through {latest}. No daily catch-up needed.")
            logger.info(f"Re-scoring latest candle date {latest}...")
            scanner_service = ScannerService()
            scanner_service.run_daily_scan(
                db, latest, force_recompute=bool(backfilled), manage_status_lock=False
            )
            return

        days = list(iter_weekdays(start, through_date))
        if len(days) > MAX_CATCHUP_DAYS:
            logger.warning(
                "Catch-up window has %d weekdays; limiting to the most recent %d.",
                len(days), MAX_CATCHUP_DAYS
            )
            days = days[-MAX_CATCHUP_DAYS:]

        logger.info(
            f"Catching up {len(days)} weekday(s) from {days[0]} to {days[-1]} "
            f"(latest candle was {latest})..."
        )
        last_scanned = None
        for d in days:
            if sync_daily_ingestion_and_scan(d):
                last_scanned = d

        # If catch-up days were all holidays/failures, still score whatever we have
        latest_after = get_latest_candle_date(db)
        if latest_after and last_scanned != latest_after:
            logger.info(f"Scoring latest available candle date {latest_after}...")
            scanner_service = ScannerService()
            scanner_service.run_daily_scan(
                db,
                latest_after,
                force_recompute=bool(backfilled),
                manage_status_lock=False,
            )

        logger.info("Catch-up pipeline finished.")
    except Exception as e:
        logger.error(f"Catch-up pipeline failed: {e}", exc_info=True)
        from backend.app.core.alerts import send_telegram_alert
        send_telegram_alert(
            f"⚠️ <b>NSE Scanner Alert</b>\n"
            f"Catch-up pipeline failed through {through_date}\n"
            f"Error: {type(e).__name__}: {str(e)[:200]}"
        )
    finally:
        db.close()
        set_scanner_running(False)


async def run_daily_ingestion_and_scan(target_date: datetime.date):
    """
    Downloads Bhavcopy, enriches OHLCV, and runs scanner for target_date.
    Delegates to threadpool using asyncio.to_thread to avoid blocking event loop.
    """
    await asyncio.to_thread(sync_daily_ingestion_and_scan, target_date)


async def run_catch_up_pipeline(through_date: datetime.date | None = None):
    """Async wrapper for catch-up ingestion + scan."""
    await asyncio.to_thread(sync_catch_up_pipeline, through_date)


async def start_scheduler():
    """
    Main scheduler loop.
    - On startup: catch up any missed trading days and short-history symbols.
    - Weekdays at 7:00 PM IST: run catch-up through today (covers the regular
      daily job and any gaps if the process was down).
    """
    logger.info("Daily Ingestion Scheduler background task started.")
    last_run_date = None

    # Startup catch-up (non-fatal if it fails)
    try:
        await run_catch_up_pipeline()
    except Exception as e:
        logger.error(f"Startup catch-up failed: {e}", exc_info=True)

    while True:
        try:
            ist_now = get_ist_now()
            today_date = ist_now.date()

            # Check if weekday (Monday=0 to Friday=4)
            is_weekday = ist_now.weekday() < 5

            # Trigger at 7:00 PM IST (19:00)
            is_trigger_time = ist_now.hour == 19

            if is_weekday and is_trigger_time and today_date != last_run_date:
                await run_catch_up_pipeline(today_date)
                last_run_date = today_date

        except Exception as e:
            logger.error(f"Error in scheduler main loop: {e}", exc_info=True)

        # Check every 60 seconds
        await asyncio.sleep(60)
