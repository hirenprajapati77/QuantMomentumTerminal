import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from backend.app.services.fundamental import FundamentalService
from backend.app.services.universe import UniverseService
from backend.app.storage.database import SessionLocal

def test_filters():
    print("=" * 60)
    print(" Testing Specific Failure Cases for Hard Filters ")
    print("=" * 60)
    
    service = UniverseService()
    db = SessionLocal()
    
    # Symbols to test:
    # 1. MFSL (Max Financial Services) -> Expected to fail on Promoter Pledge
    # 2. OLAELEC (Ola Electric) -> Expected to fail on 2y listing history
    # 3. MAPMYINDIA -> Expected to fail on Market Cap
    test_symbols = ["MFSL", "OLAELEC", "MAPMYINDIA"]
    
    # Fetch Nifty 500 list to see if they are in it
    all_symbols = service.download_nifty_500_list()
    
    for symbol in test_symbols:
        in_nifty500 = symbol in all_symbols
        print(f"\nSymbol: {symbol} (In Nifty 500: {in_nifty500})")
        
        passed, reason = service.apply_hard_filters(db, symbol)
        if passed:
            print("  Result: PASSED")
        else:
            print(f"  Result: EXCLUDED -> Reason: {reason}")
            
    db.close()

if __name__ == "__main__":
    test_filters()
