import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from backend.app.core.logging import logger
from backend.app.storage.database import init_db, SessionLocal
from backend.app.services.fundamental import FundamentalService
from backend.app.models.fundamental import CompanyFundamental

def main():
    print("=" * 80)
    print(" NSE Momentum Scanner - Fundamentals Ingestion & Verification Tool ")
    print("=" * 80)
    
    # 1. Initialize DB tables
    print("\n[1/2] Initializing database...")
    init_db()
    
    db = SessionLocal()
    service = FundamentalService()
    
    # Validation symbols
    symbols = ["RELIANCE", "TCS", "INFY", "KPITTECH", "IREDA"]
    
    print("\n[2/2] Scraping and ingesting company fundamentals from Screener.in...")
    
    for symbol in symbols:
        print(f"\n--------------------------------------------------------------------------------")
        print(f" Processing: {symbol}")
        print(f"--------------------------------------------------------------------------------")
        
        try:
            # Scrape and save
            db_record = service.ingest_company_fundamentals(db, symbol)
            
            # Print parsed values
            print(f"  Sector:                     {db_record.sector}")
            print(f"  Industry:                   {db_record.industry}")
            print(f"  Market Cap (Cr):            Rs. {float(db_record.market_cap) if db_record.market_cap else 'N/A'}")
            print(f"  Sales Growth QoQ %:          {float(db_record.sales_growth_qoq) if db_record.sales_growth_qoq is not None else 'N/A'} %")
            print(f"  Sales Growth YoY %:          {float(db_record.sales_growth_yoy) if db_record.sales_growth_yoy is not None else 'N/A'} %")
            print(f"  Profit Growth YoY %:         {float(db_record.profit_growth_yoy) if db_record.profit_growth_yoy is not None else 'N/A'} %")
            print(f"  ROCE %:                     {float(db_record.roce) if db_record.roce else 'N/A'} %")
            print(f"  ROE %:                      {float(db_record.roe) if db_record.roe else 'N/A'} %")
            print(f"  Debt to Equity Ratio:       {float(db_record.debt_to_equity) if db_record.debt_to_equity is not None else 'N/A'}")
            print(f"  Inst. Holding %:            {float(db_record.institutional_holding) if db_record.institutional_holding is not None else 'N/A'} %")
            print(f"  Inst. Holding QoQ Change %: {float(db_record.institutional_holding_qoq_change) if db_record.institutional_holding_qoq_change is not None else 'N/A'} %")
            print(f"  Promoter Pledge %:          {float(db_record.promoter_pledge) if db_record.promoter_pledge is not None else '0.0'} %")
            
        except Exception as e:
            print(f"  Error ingesting fundamentals for {symbol}: {e}")
            logger.error(f"Fundamentals ingestion failed for {symbol}", exc_info=True)
            
    db.close()
    print("\n" + "=" * 80)
    print("Verification completed. Please eyeball verify these values against Screener.in website.")
    print("=" * 80)

if __name__ == "__main__":
    main()
