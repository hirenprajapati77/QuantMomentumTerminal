import sys
import datetime
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
from backend.app.services.market_data import MarketDataService
from backend.app.services.scanner import ScannerService

def main():
    init_db()
    db = SessionLocal()
    market_data_service = MarketDataService()
    
    # 1. Determine target date (default to today in IST, or read command-line arg)
    ist_now = datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
    target_date = ist_now.date()
    
    if len(sys.argv) > 1:
        date_str = sys.argv[1]
        try:
            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            print("Error: Invalid date format. Please use YYYY-MM-DD.")
            db.close()
            sys.exit(1)
            
    print("=" * 80)
    print(f" Running Live Ingestion & Scan for Target Date: {target_date} ")
    print("=" * 80)
    
    symbols = ["RELIANCE", "TCS", "INFY", "KPITTECH", "IREDA"]
    
    # Ensure symbols are configured
    for sym in symbols:
        stock = db.query(UniverseStock).filter(UniverseStock.symbol == sym).first()
        if not stock:
            db.add(UniverseStock(symbol=sym, is_active=True))
        else:
            stock.is_active = True
            db.add(stock)
            
        fund = db.query(CompanyFundamental).filter(CompanyFundamental.symbol == sym).first()
        if not fund:
            db.add(CompanyFundamental(
                symbol=sym,
                sector="Information Technology" if "TCS" in sym or "INFY" in sym or "KPIT" in sym else "Energy",
                industry="Software" if "TCS" in sym or "INFY" in sym or "KPIT" in sym else "Refineries",
                market_cap=150000.0,
                sales_growth_yoy=20.0,
                profit_growth_yoy=25.0,
                roce=30.0,
                roe=25.0,
                debt_to_equity=0.1,
                promoter_pledge=0.0,
                under_surveillance=False
            ))
    db.commit()
    
    # Ingest 1 year of daily candles up to target_date
    start_date = target_date - datetime.timedelta(days=365)
    print(f"Ingesting daily candles from {start_date} to {target_date}...")
    
    for sym in symbols:
        # Clear existing candles in this date range to update them with fresh data
        db.query(DailyCandle).filter(
            DailyCandle.symbol == sym,
            DailyCandle.date >= start_date,
            DailyCandle.date <= target_date
        ).delete()
        db.commit()
        
        try:
            print(f"  Ingesting {sym}...")
            df = market_data_service.fetch_fyers_ohlcv(sym, start_date, target_date)
            if df.empty:
                print(f"  No candles returned for {sym}.")
                continue
                
            candles = []
            for _, row in df.iterrows():
                candle = DailyCandle(
                    symbol=sym,
                    date=row['date'],
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=row['close'],
                    volume=int(row['volume']),
                    delivery_qty=None,
                    delivery_pct=None
                )
                candles.append(candle)
            db.bulk_save_objects(candles)
            db.commit()
            print(f"  Saved {len(candles)} candles for {sym}.")
        except Exception as e:
            print(f"  Error fetching candles for {sym}: {e}")
            
    # Run manual daily scan
    print(f"\nTriggering scanner scoring on {target_date}...")
    db.query(ScanResult).filter(ScanResult.date == target_date).delete()
    db.commit()
    
    scanner_service = ScannerService()
    results = scanner_service.run_daily_scan(db, target_date)
    print(f"Scan complete. Generated {len(results)} scan results.")
    
    for r in results:
        print(f"  Symbol: {r.symbol} | Grade: {r.grade} | Score: {r.final_score:.1f} | Entry Price: {r.entry}")
        
    db.close()
    print("Done!")

if __name__ == "__main__":
    main()
