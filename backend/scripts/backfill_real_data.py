import sys
import datetime
from pathlib import Path

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
    print("=" * 80)
    print(" Ingesting 1-Year History for Real Stocks ")
    print("=" * 80)
    
    init_db()
    db = SessionLocal()
    market_data_service = MarketDataService()
    
    symbols = ["RELIANCE", "TCS", "INFY", "KPITTECH", "IREDA"]
    
    # 1. Add to Universe & Fundamentals if not present
    for sym in symbols:
        # Add to universe
        stock = db.query(UniverseStock).filter(UniverseStock.symbol == sym).first()
        if not stock:
            stock = UniverseStock(symbol=sym, is_active=True)
            db.add(stock)
        else:
            stock.is_active = True
            db.add(stock)
            
        # Add to fundamentals with strong metrics so they pass the fundamental gate
        fund = db.query(CompanyFundamental).filter(CompanyFundamental.symbol == sym).first()
        if not fund:
            fund = CompanyFundamental(
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
            )
            db.add(fund)
            
    db.commit()
    print("Universe and Fundamentals configured for real stocks.")
    
    # 2. Ingest 1 Year of candles from Fyers (2025-06-22 to 2026-06-22)
    end_date = datetime.date(2026, 6, 22)
    start_date = end_date - datetime.timedelta(days=365)
    
    print(f"Ingesting daily candles from Fyers for {symbols} ({start_date} to {end_date})...")
    
    for sym in symbols:
        # Clear existing candles for this symbol to start fresh
        db.query(DailyCandle).filter(DailyCandle.symbol == sym).delete()
        db.commit()
        
        try:
            print(f"  Fetching candles for {sym}...")
            # We bypass the NSE delivery bhavcopy ingestion for history speed, inserting basic candles
            df = market_data_service.fetch_fyers_ohlcv(sym, start_date, end_date)
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
            
    # 3. Trigger manual scan calculations on the final day 2026-06-22
    scan_date = datetime.date(2026, 6, 22)
    print(f"\nTriggering dynamic daily scan on {scan_date} for the ingested data...")
    db.query(ScanResult).filter(ScanResult.date == scan_date).delete()
    db.commit()
    
    scanner_service = ScannerService()
    results = scanner_service.run_daily_scan(db, scan_date)
    print(f"Scan completed. Generated {len(results)} scan results.")
    
    db.close()
    print("Done!")

if __name__ == "__main__":
    main()
