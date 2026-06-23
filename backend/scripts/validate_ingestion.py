import sys
import datetime
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from backend.app.core.logging import logger
from backend.app.core.exceptions import FyersTokenExpiredException
from backend.app.storage.database import init_db, SessionLocal
from backend.app.services.market_data import MarketDataService
from backend.app.models.candle import DailyCandle

def main():
    print("=" * 70)
    print(" NSE Momentum Scanner - Ingestion Validation Tool ")
    print("=" * 70)
    
    # 1. Initialize DB tables
    print("\n[1/3] Initializing local database...")
    init_db()
    
    db = SessionLocal()
    service = MarketDataService()
    
    # Define validation symbols
    # 1. RELIANCE (Large Cap)
    # 2. TCS (Large Cap IT)
    # 3. INFY (Large Cap IT)
    # 4. KPITTECH (Mid Cap)
    # 5. IREDA (Recent IPO)
    symbols = ["RELIANCE", "TCS", "INFY", "KPITTECH", "IREDA"]
    
    # Define date range (last ~10 trading days)
    end_date = datetime.date(2026, 6, 22)
    start_date = datetime.date(2026, 6, 8)
    
    print(f"\n[2/3] Ingesting data from {start_date} to {end_date}...")
    print("Retrieving from Fyers (OHLCV) and NSE Archives (Delivery volume)...")
    
    # Cache downloaded Bhavcopies to avoid downloading multiple times for each symbol
    bhavcopy_cache = {}
    
    try:
        # Pre-download Bhavcopies for the entire date range to speed up processing
        curr = start_date
        while curr <= end_date:
            # Skip weekends
            if curr.weekday() < 5:
                try:
                    print(f"  Downloading NSE Bhavcopy for {curr}...")
                    bhav_df = service.download_nse_bhavcopy(curr)
                    if not bhav_df.empty:
                        bhavcopy_cache[curr] = bhav_df
                except Exception as e:
                    print(f"  Warning: Could not fetch Bhavcopy for {curr}: {e}")
            curr += datetime.timedelta(days=1)
            
        # Ingest symbols
        for symbol in symbols:
            print(f"  Processing symbol: {symbol}...")
            count = service.ingest_symbol_data(db, symbol, start_date, end_date, bhavcopy_cache)
            print(f"  Successfully processed {count} records for {symbol}.")
            
    except FyersTokenExpiredException as e:
        print("\n" + "!" * 70)
        print("ERROR: Fyers access token is missing or expired!")
        print(f"Message: {e}")
        print("Please run: python backend/scripts/login_fyers.py")
        print("!" * 70 + "\n")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR during ingestion: {e}")
        logger.error(f"Ingestion failed", exc_info=True)
        sys.exit(1)
        
    print("\n[3/3] Printing the last 10 rows for each symbol:")
    print("=" * 80)
    
    for symbol in symbols:
        print(f"\nSymbol: {symbol}")
        print("-" * 80)
        
        candles = db.query(DailyCandle).filter(
            DailyCandle.symbol == symbol
        ).order_by(DailyCandle.date.asc()).all()
        
        if not candles:
            print("No data stored in database for this symbol.")
            continue
            
        # Print table headers
        print(f"{'Date':<12} | {'Open':<10} | {'High':<10} | {'Low':<10} | {'Close':<10} | {'Volume':<12} | {'Del Qty':<12} | {'Del %':<6}")
        print("-" * 80)
        
        # Display the last 10 candles
        for candle in candles[-10:]:
            del_pct_str = f"{candle.delivery_pct:.2f}%" if candle.delivery_pct is not None else "N/A"
            del_qty_str = f"{candle.delivery_qty}" if candle.delivery_qty is not None else "N/A"
            print(f"{candle.date.strftime('%Y-%m-%d'):<12} | {float(candle.open):<10.2f} | {float(candle.high):<10.2f} | {float(candle.low):<10.2f} | {float(candle.close):<10.2f} | {candle.volume:<12} | {del_qty_str:<12} | {del_pct_str:<6}")
            
    db.close()
    print("=" * 80)
    print("\nValidation completed. Please eyeball verify these rows against the NSE website.")

if __name__ == "__main__":
    main()
