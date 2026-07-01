import sys
import datetime
import time
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from backend.app.storage.database import SessionLocal, init_db
from backend.app.models.universe import UniverseStock
from backend.app.models.fundamental import CompanyFundamental
from backend.app.models.candle import DailyCandle
from backend.app.models.scan_result import ScanResult
from backend.app.services.universe import UniverseService
from backend.app.services.market_data import MarketDataService
from backend.app.services.scanner import ScannerService

# Configure logging to show process in stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("nse_scanner.universe_build")

def main():
    print("=" * 80)
    print(" Production Setup: Full NIFTY 500 Universe Ingestion & Backfill ")
    print("=" * 80)
    
    init_db()
    db = SessionLocal()
    universe_service = UniverseService()
    market_data_service = MarketDataService()
    scanner_service = ScannerService()
    
    # 1. Clear database tables
    print("\n[1/4] Clearing previous database tables...")
    db.query(DailyCandle).delete()
    db.query(CompanyFundamental).delete()
    db.query(UniverseStock).delete()
    db.query(ScanResult).delete()
    db.commit()
    print("Tables cleared successfully.")
    
    # 2. Rebuild Universe (Downloads Nifty 500 & applies all Hard Filters)
    print("\n[2/4] Downloading Nifty 500 list and applying hard filters...")
    print("Note: This will download ind_nifty500list.csv and scrape Screener.in fundamentals.")
    print("This step can take 20-30 minutes due to rate-limiting and check requirements.\n")
    
    start_time = time.time()
    summary = universe_service.rebuild_universe(db)
    elapsed = time.time() - start_time
    
    print("\nUniverse Rebuild Summary:")
    print(f"  Total Nifty 500 symbols: {summary['total_nifty500']}")
    print(f"  Passed (Active): {summary['passed']}")
    print(f"  Failed (Excluded): {summary['failed']}")
    print(f"  Time taken: {elapsed/60:.1f} minutes")
    
    # Fetch active symbols
    active_stocks = db.query(UniverseStock).filter(UniverseStock.is_active == True).all()
    active_symbols = [s.symbol for s in active_stocks]
    
    # Report filter failure reasons
    print("\nFilter Exclusions Breakdown:")
    exclusions = db.query(UniverseStock.exclusion_reason).filter(UniverseStock.is_active == False).all()
    reasons = {}
    for r in exclusions:
        reason = r[0] or "Unknown"
        # Categorize simple reasons
        short_reason = reason.split(":")[0] if ":" in reason else reason
        reasons[short_reason] = reasons.get(short_reason, 0) + 1
    for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {reason}: {count} symbols")
        
    if not active_symbols:
        print("\nERROR: No symbols survived the hard filters! Ingestion aborted.")
        db.close()
        return
        
    # 3. Backfill 2 Years of Daily Candles from Fyers
    ist_now = datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
    target_date = ist_now.date()
    # Adjust target date for weekends/market close
    if target_date.weekday() == 5:  # Saturday
        target_date -= datetime.timedelta(days=1)
    elif target_date.weekday() == 6:  # Sunday
        target_date -= datetime.timedelta(days=2)
        
    # 2 Years lookback
    start_date = target_date - datetime.timedelta(days=365 * 2)
    
    print(f"\n[3/4] Backfilling 2-year daily history from Fyers for {len(active_symbols)} active symbols...")
    print(f"Date Range: {start_date} to {target_date}")
    
    failed_fetches = []
    total_candles_saved = 0
    
    for idx, sym in enumerate(active_symbols):
        try:
            print(f"  ({idx+1}/{len(active_symbols)}) Fetching {sym}... ", end="", flush=True)
            # Ingest symbol data handles fetching, formatting, and database commit
            market_data_service.ingest_symbol_data(db, sym, start_date, target_date)
            
            # Query count of saved candles to display progress
            candles_count = db.query(DailyCandle).filter(DailyCandle.symbol == sym).count()
            total_candles_saved += candles_count
            print(f"Saved {candles_count} candles.")
        except Exception as e:
            print(f"FAILED: {e}")
            failed_fetches.append((sym, str(e)))
            
    # 4. Trigger Daily Scan
    print(f"\n[4/4] Triggering daily scan for {target_date}...")
    results = scanner_service.run_daily_scan(db, target_date)
    print(f"Scan complete. Generated {len(results)} scan results.")
    
    print(f"\nFinal active universe symbols count: {len(active_symbols)}")
    print(f"Total candles rows ingested: {total_candles_saved}")
    if failed_fetches:
        print(f"Symbols that failed Fyers fetches ({len(failed_fetches)}):")
        for sym, err in failed_fetches:
            print(f"  - {sym}: {err}")
            
    db.close()
    print("\nProduction universe buildup completed successfully!")
    print("Refresh your browser dashboard to view the scanned universe.")

if __name__ == "__main__":
    main()
