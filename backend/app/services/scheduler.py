import asyncio
import datetime
import logging
import time
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from backend.app.storage.database import SessionLocal
from backend.app.services.market_data import MarketDataService
from backend.app.services.scanner import ScannerService
from backend.app.models.universe import UniverseStock

logger = logging.getLogger("nse_scanner.scheduler")

def get_ist_now() -> datetime.datetime:
    """
    Returns current time in Indian Standard Time (IST = UTC + 5:30).
    """
    return datetime.datetime.now(ZoneInfo("Asia/Kolkata"))

def sync_daily_ingestion_and_scan(target_date: datetime.date):
    """
    Synchronous implementation of daily ingestion and scan.
    Runs inside a worker thread via asyncio.to_thread to avoid blocking event loop.
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
            return
            
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
                time.sleep(15 * 60) # 15 minutes (synchronous sleep in worker thread)
                
        if bhav_df is None or bhav_df.empty:
            logger.error(f"Failed to fetch Bhavcopy for {target_date} after 4 attempts. Proceeding with OHLCV only.")
            bhavcopy_cache = {}
        else:
            bhavcopy_cache = {target_date: bhav_df}
            
        # Ingest daily candle for each active symbol
        logger.info("Ingesting OHLCV and delivery data for active symbols...")
        for sym in active_symbols:
            try:
                # Ingest for target_date
                market_data_service.ingest_symbol_data(db, sym, target_date, target_date, bhavcopy_cache)
                # Prevent Fyers API rate limiting (HTTP 429)
                time.sleep(0.35)
            except Exception as e:
                logger.error(f"Failed to ingest data for symbol {sym} on {target_date}: {e}")
                
        # Run Scanner to cache today's scores and entry signals
        logger.info("Running daily composite strategy scanner...")
        scanner_service.run_daily_scan(db, target_date)
        logger.info("Daily ingestion and scanner run completed successfully!")
        
    except Exception as e:
        logger.error(f"Scheduler worker encountered an error: {e}", exc_info=True)
        from backend.app.core.alerts import send_telegram_alert
        send_telegram_alert(
            f"⚠️ <b>NSE Scanner Alert</b>\n"
            f"Daily scan failed on {target_date}\n"
            f"Error: {type(e).__name__}: {str(e)[:200]}"
        )
    finally:
        db.close()

async def run_daily_ingestion_and_scan(target_date: datetime.date):
    """
    Downloads Bhavcopy, enriches OHLCV, and runs scanner for target_date.
    Delegates to threadpool using asyncio.to_thread to avoid blocking event loop.
    """
    await asyncio.to_thread(sync_daily_ingestion_and_scan, target_date)

async def start_scheduler():
    """
    Main scheduler loop. Check current time in IST every minute, and trigger
    ingestion and scanner at 6:30 PM IST on weekdays.
    """
    logger.info("Daily Ingestion Scheduler background task started.")
    last_run_date = None
    
    while True:
        try:
            ist_now = get_ist_now()
            today_date = ist_now.date()
            
            # Check if weekday (Monday=0 to Friday=4)
            is_weekday = ist_now.weekday() < 5
            
            # Trigger at 7:00 PM IST (19:00)
            is_trigger_time = ist_now.hour == 19
            
            if is_weekday and is_trigger_time and today_date != last_run_date:
                # Trigger worker task
                await run_daily_ingestion_and_scan(today_date)
                last_run_date = today_date
                
        except Exception as e:
            logger.error(f"Error in scheduler main loop: {e}", exc_info=True)
            
        # Check every 60 seconds
        await asyncio.sleep(60)
