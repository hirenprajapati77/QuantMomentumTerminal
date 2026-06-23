import sys
import datetime
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from backend.app.storage.database import init_db, SessionLocal
from backend.app.services.universe import UniverseService
from backend.app.models.universe import UniverseStock

def main():
    print("=" * 80)
    print(" NSE Momentum Scanner - Universe Construction & Filter Validation ")
    print("=" * 80)
    
    # Initialize DB
    init_db()
    db = SessionLocal()
    service = UniverseService()
    
    # 1. Fetch Nifty 500 symbols
    try:
        all_symbols = service.download_nifty_500_list()
    except Exception as e:
        print(f"Error fetching Nifty 500 list: {e}")
        sys.exit(1)
        
    print(f"\nTotal Nifty 500 constituents found: {len(all_symbols)}")
    
    # To prevent rate-limiting/IP-blocking on Screener.in and Fyers during validation, 
    # we select a representative subset of 30 symbols to test every single filter condition:
    # - RELIANCE, TCS, INFY: Large caps (should pass)
    # - KPITTECH: Mid cap (should pass)
    # - SWSOLAR: Has high promoter pledge (should fail)
    # - IREDA: Financial, low history / data (should fail 2y check or pass depending on history)
    # - SME/other symbols that are low market cap (< 10000 Cr) or low traded value.
    test_subset = [
        "RELIANCE", "TCS", "INFY", "KPITTECH", "IREDA",
        "MFSL", "NHPC", "SUZLON", "MRF", "ITC", 
        "HDFCBANK", "ZOMATO", "TATASTEEL", "ADANIPORTS", "ZEEL",
        "TRENT", "JIOFIN", "IDEA", "PAYTM", "AWL",
        "NYKAA", "DELHIVERY", "MAPMYINDIA", "OLAELEC", "LLOYDSME",
        "RBLBANK", "HUDCO", "IRFC", "RVNL", "SJVN"
    ]
    
    # Intersect test_subset with actual Nifty 500 list to be safe
    test_symbols = [s for s in test_subset if s in all_symbols]
    print(f"Running validation filters on a representative subset of {len(test_symbols)} symbols...")
    
    passed_stocks = []
    excluded_stocks = []
    
    for index, symbol in enumerate(test_symbols):
        print(f"  [{index+1}/{len(test_symbols)}] Filtering {symbol}...", end="", flush=True)
        try:
            passed, reason = service.apply_hard_filters(db, symbol)
            
            # Save to DB
            db_stock = db.query(UniverseStock).filter(UniverseStock.symbol == symbol).first()
            if not db_stock:
                db_stock = UniverseStock(symbol=symbol, is_active=passed, exclusion_reason=reason)
                db.add(db_stock)
            else:
                db_stock.is_active = passed
                db_stock.exclusion_reason = reason
            db.commit()
            
            if passed:
                print(" -> PASSED")
                passed_stocks.append(symbol)
            else:
                print(f" -> EXCLUDED ({reason})")
                excluded_stocks.append((symbol, reason))
                
        except Exception as e:
            print(f" -> ERROR ({e})")
            db.rollback()
            
    db.close()
    
    print("\n" + "=" * 80)
    print(" UNIVERSE FILTERING RESULTS (Validation Subset) ")
    print("=" * 80)
    print(f"Total Tested:      {len(test_symbols)}")
    print(f"Passed (Tradeable): {len(passed_stocks)}")
    print(f"Excluded:          {len(excluded_stocks)}")
    
    print("\n--- Passed Symbols ---")
    print(", ".join(passed_stocks))
    
    print("\n--- Excluded Symbols Sample & Reasons ---")
    print(f"{'Symbol':<15} | {'Exclusion Reason'}")
    print("-" * 80)
    for sym, reason in excluded_stocks:
        print(f"{sym:<15} | {reason}")
    print("=" * 80)
    
if __name__ == "__main__":
    main()
