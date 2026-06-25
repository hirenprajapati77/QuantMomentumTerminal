import sys
import datetime
from pathlib import Path
import pandas as pd
import numpy as np

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from backend.app.storage.database import SessionLocal
from backend.app.models.candle import DailyCandle
from backend.app.models.universe import UniverseStock
from backend.app.models.fundamental import CompanyFundamental

def generate_perfect_vcp_candles(trading_dates):
    n = len(trading_dates)
    close = [0.0] * n
    
    # 1. Generate close prices
    for t in range(190):
        close[t] = 5.0 + (t / 190.0) * 85.0  # Linearly rising 5 -> 90
        
    for t in range(190, 226):
        close[t] = 90.0 + ((t - 190) / 36.0) * 7.0
        
    close[226] = 98.0
    close[227] = 99.0
    close[228] = 100.0  # High 1 (t=228)
    close[229] = 96.0
    close[230] = 93.0
    
    for t in range(231, 236):
        close[t] = 93.0 - ((t - 230) / 5.0) * 21.0  # falling to 72
        
    close[236] = 73.0
    close[237] = 71.5
    close[238] = 70.0   # Low 1 (t=238)
    close[239] = 72.5
    close[240] = 75.0
    
    for t in range(241, 246):
        close[t] = 75.0 + ((t - 240) / 5.0) * 14.0  # rising to 89
        
    close[246] = 91.5
    close[247] = 93.5
    close[248] = 95.0   # High 2 (t=248)
    close[249] = 92.5
    close[250] = 90.0
    
    for t in range(251, 256):
        close[t] = 90.0 - ((t - 250) / 5.0) * 11.0  # falling to 79
        
    close[256] = 78.5
    close[257] = 77.0
    close[258] = 76.0   # Low 2 (t=258)
    close[259] = 78.0
    close[260] = 80.0
    
    for t in range(261, 266):
        close[t] = 80.0 + ((t - 260) / 5.0) * 5.0   # rising to 85
        
    close[266] = 86.5
    close[267] = 88.5
    close[268] = 90.0   # High 3 (t=268)
    close[271] = 88.0
    close[272] = 86.0
    
    for t in range(269, 274):
        close[t] = 90.0 - ((t - 268) / 5.0) * 8.0   # falling to 82
        
    close[274] = 83.0
    close[275] = 82.0
    close[276] = 81.0   # Low 3 (t=276)
    close[277] = 81.2
    close[278] = 81.5   # CPR Day (t=278)
    close[279] = 105.0  # Breakout Day (t=279)
    
    # 2. Generate High, Low, Open, Volume
    high = [0.0] * n
    low = [0.0] * n
    open_val = [0.0] * n
    volume = [0] * n
    
    for t in range(n):
        if t < 228:
            range_pct = 7.0
        elif t > 276:
            range_pct = 1.5
        else:
            range_pct = 7.0 - ((t - 228) / 48.0) * (7.0 - 1.5)
            
        # Introduce asymmetry: high is slightly wider than low
        high[t] = round(close[t] * (1.0 + range_pct / 180.0), 2)
        low[t] = round(close[t] * (1.0 - range_pct / 220.0), 2)
        open_val[t] = round(close[t], 2)
        
        # Volume profile: flat-ish early, but contracts heavily during VCP
        if t < 228:
            volume[t] = int(1000000 + np.random.normal(0, 50000))
        elif t <= 278:
            # Volume dries up from 1,500,000 to 200,000
            fraction = (t - 228) / 50.0
            volume[t] = int(1500000 - fraction * 1300000 + np.random.normal(0, 10000))
        else:
            volume[t] = 2500000  # Will be set to 2.5M below for breakout day
            
    # Overwrite High 1 (t=228)
    high[228] = 104.0
    low[228] = 96.0
    volume[228] = 1500000
    
    # Overwrite Low 1 (t=238)
    high[238] = 73.0
    low[238] = 67.5
    volume[238] = 1200000
    
    # Overwrite High 2 (t=248)
    high[248] = 98.0
    low[248] = 92.0
    volume[248] = 800000
    
    # Overwrite Low 2 (t=258)
    high[258] = 78.0
    low[258] = 74.0
    volume[258] = 500000
    
    # Overwrite High 3 (t=268)
    high[268] = 92.0
    low[268] = 88.0
    volume[268] = 350000
    
    # Overwrite Low 3 (t=276)
    high[276] = 82.5
    low[276] = 79.5
    volume[276] = 220000
    
    # Overwrite CPR Day (t=278)
    high[278] = 81.8
    low[278] = 81.0
    open_val[278] = 81.2
    close[278] = 81.5
    volume[278] = 200000
    
    # Overwrite Breakout Day (t=279)
    close[279] = 105.0
    high[279] = 105.0
    low[279] = 99.8
    open_val[279] = 100.0
    
    # Prior 50-day average volume (days 229 to 278) will be ~850,000.
    # Set breakout volume to 2,500,000 to get a 2.94x ratio.
    volume[279] = 2500000
    
    return open_val, high, low, close, volume

def main():
    print("=" * 80)
    print(" Seeding Perfect VCP Candlesticks for Offline UI Testing ")
    print("=" * 80)
    
    db = SessionLocal()
    
    # Get trading dates from existing STOCK001 candles
    dates_query = db.query(DailyCandle.date).filter(DailyCandle.symbol == 'STOCK001').order_by(DailyCandle.date.asc()).all()
    trading_dates = [d[0] for d in dates_query]
    
    if len(trading_dates) != 280:
        print(f"Error: Expected 280 trading dates, found {len(trading_dates)}. Please run seed_mock_data.py first.")
        db.close()
        sys.exit(1)
        
    targets = ['STOCK001', 'STOCK002', 'STOCK003', 'STOCK004', 'STOCK005']
    print(f"Overwriting candles for {targets}...")
    
    for sym in targets:
        # Delete existing candles
        db.query(DailyCandle).filter(DailyCandle.symbol == sym).delete()
        
        # Generate perfect VCP candles
        open_val, high, low, close, volume = generate_perfect_vcp_candles(trading_dates)
        
        candles = []
        for t, date in enumerate(trading_dates):
            candle = DailyCandle(
                symbol=sym,
                date=date,
                open=open_val[t],
                high=high[t],
                low=low[t],
                close=close[t],
                volume=volume[t],
                delivery_qty=int(volume[t] * 0.6),
                delivery_pct=60.0
            )
            candles.append(candle)
        db.bulk_save_objects(candles)
        
        # Update fundamental sector to Information Technology (top performing sector)
        fund = db.query(CompanyFundamental).filter(CompanyFundamental.symbol == sym).first()
        if fund:
            fund.sector = "Information Technology"
            # Ensure it passes fundamental gate
            fund.roe = 25.0
            fund.roce = 30.0
            fund.debt_to_equity = 0.1
            fund.sales_growth_yoy = 20.0
            fund.profit_growth_yoy = 25.0
            fund.promoter_pledge = 0.0
            fund.under_surveillance = False
            db.add(fund)
            
    db.commit()
    print("Perfect VCP candles seeded successfully!")
    db.close()

if __name__ == "__main__":
    main()
