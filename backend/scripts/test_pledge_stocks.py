import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from backend.app.storage.database import SessionLocal
from backend.app.services.fundamental import FundamentalService

def test_pledged_stocks():
    print("=" * 60)
    print(" Testing Promoter Pledge Detection on Known Pledged Stocks ")
    print("=" * 60)
    
    service = FundamentalService()
    
    # We will test SWSOLAR (Sterling and Wilson) and ZEEL (Zee Entertainment)
    # Both are known to have promoter pledge.
    test_symbols = ["SWSOLAR", "ZEEL"]
    
    for symbol in test_symbols:
        try:
            print(f"\nScraping {symbol}...")
            data = service.scrape_company_fundamentals(symbol)
            print(f"  Symbol:          {data['symbol']}")
            print(f"  Promoter Pledge: {data['promoter_pledge']} %")
            print(f"  Sector:          {data['sector']}")
            print(f"  Market Cap (Cr): Rs. {data['market_cap']}")
        except Exception as e:
            print(f"  Error testing {symbol}: {e}")

if __name__ == "__main__":
    test_pledged_stocks()
