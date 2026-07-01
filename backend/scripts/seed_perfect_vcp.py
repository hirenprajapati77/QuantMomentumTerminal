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
from backend.app.models.scan_result import ScanResult

def generate_perfect_vcp_candles(trading_dates, base_price=100.0, volume_factor=1.0):
    n = len(trading_dates)
    close = [0.0] * n
    
    # Scale all closing prices according to the base_price relative to 100.0
    scale = base_price / 100.0
    
    for t in range(190):
        close[t] = (5.0 + (t / 190.0) * 85.0) * scale
        
    for t in range(190, 226):
        close[t] = (90.0 + ((t - 190) / 36.0) * 7.0) * scale
        
    close[226] = 98.0 * scale
    close[227] = 99.0 * scale
    close[228] = 100.0 * scale  # High 1 (t=228)
    close[229] = 96.0 * scale
    close[230] = 93.0 * scale
    
    for t in range(231, 236):
        close[t] = (93.0 - ((t - 230) / 5.0) * 21.0) * scale
        
    close[236] = 73.0 * scale
    close[237] = 71.5 * scale
    close[238] = 70.0 * scale   # Low 1 (t=238)
    close[239] = 72.5 * scale
    close[240] = 75.0 * scale
    
    for t in range(241, 246):
        close[t] = (75.0 + ((t - 240) / 5.0) * 14.0) * scale
        
    close[246] = 91.5 * scale
    close[247] = 93.5 * scale
    close[248] = 95.0 * scale   # High 2 (t=248)
    close[249] = 92.5 * scale
    close[250] = 90.0 * scale
    
    for t in range(251, 256):
        close[t] = (90.0 - ((t - 250) / 5.0) * 11.0) * scale
        
    close[256] = 78.5 * scale
    close[257] = 77.0 * scale
    close[258] = 76.0 * scale   # Low 2 (t=258)
    close[259] = 78.0 * scale
    close[260] = 80.0 * scale
    
    for t in range(261, 266):
        close[t] = (80.0 + ((t - 260) / 5.0) * 5.0) * scale
        
    close[266] = 86.5 * scale
    close[267] = 88.5 * scale
    close[268] = 90.0 * scale   # High 3 (t=268)
    close[271] = 88.0 * scale
    close[272] = 86.0 * scale
    
    for t in range(269, 274):
        close[t] = (90.0 - ((t - 268) / 5.0) * 8.0) * scale
        
    close[274] = 83.0 * scale
    close[275] = 82.0 * scale
    close[276] = 81.0 * scale   # Low 3 (t=276)
    close[277] = 81.2 * scale
    close[278] = 81.5 * scale   # CPR Day (t=278)
    close[279] = 105.0 * scale  # Breakout Day (t=279)
    
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
            volume[t] = int((1000000 + np.random.normal(0, 50000)) * volume_factor)
        elif t <= 278:
            # Volume dries up from 1,500,000 to 200,000
            fraction = (t - 228) / 50.0
            volume[t] = int((1500000 - fraction * 1300000 + np.random.normal(0, 10000)) * volume_factor)
        else:
            volume[t] = int(2500000 * volume_factor)  # Breakout day volume
            
    # Overwrite High 1 (t=228)
    high[228] = 104.0 * scale
    low[228] = 96.0 * scale
    volume[228] = int(1500000 * volume_factor)
    
    # Overwrite Low 1 (t=238)
    high[238] = 73.0 * scale
    low[238] = 67.5 * scale
    volume[238] = int(1200000 * volume_factor)
    
    # Overwrite High 2 (t=248)
    high[248] = 98.0 * scale
    low[248] = 92.0 * scale
    volume[248] = int(800000 * volume_factor)
    
    # Overwrite Low 2 (t=258)
    high[258] = 78.0 * scale
    low[258] = 74.0 * scale
    volume[258] = int(500000 * volume_factor)
    
    # Overwrite High 3 (t=268)
    high[268] = 92.0 * scale
    low[268] = 88.0 * scale
    volume[268] = int(350000 * volume_factor)
    
    # Overwrite Low 3 (t=276)
    high[276] = 82.5 * scale
    low[276] = 79.5 * scale
    volume[276] = int(220000 * volume_factor)
    
    # Overwrite CPR Day (t=278)
    high[278] = 81.8 * scale
    low[278] = 81.0 * scale
    open_val[278] = 81.2 * scale
    close[278] = 81.5 * scale
    volume[278] = int(200000 * volume_factor)
    
    # Overwrite Breakout Day (t=279)
    close[279] = 105.0 * scale
    high[279] = 105.0 * scale
    low[279] = 99.8 * scale
    open_val[279] = 100.0 * scale
    volume[279] = int(2500000 * volume_factor)
    
    return open_val, high, low, close, volume

def main():
    print("=" * 80)
    print(" Seeding Dynamic VCP Candlesticks for Live-Like Offline UI Testing ")
    print("=" * 80)
    
    db = SessionLocal()
    
    # Get trading dates from existing STOCK001 candles
    dates_query = db.query(DailyCandle.date).filter(DailyCandle.symbol == 'STOCK001').order_by(DailyCandle.date.asc()).all()
    trading_dates = [d[0] for d in dates_query]
    
    if len(trading_dates) != 280:
        print(f"Error: Expected 280 trading dates, found {len(trading_dates)}. Please run seed_mock_data.py first.")
        db.close()
        sys.exit(1)
        
    target_configs = {
        'STOCK001': {'base_price': 100.0, 'vol_factor': 1.0, 'sector': 'Information Technology'},
        'STOCK002': {'base_price': 150.0, 'vol_factor': 1.2, 'sector': 'Financial Services'},
        'STOCK003': {'base_price': 80.0, 'vol_factor': 0.9, 'sector': 'Energy'},
        'STOCK004': {'base_price': 220.0, 'vol_factor': 1.5, 'sector': 'Healthcare'},
        'STOCK005': {'base_price': 110.0, 'vol_factor': 1.1, 'sector': 'Fast Moving Consumer Goods'}
    }
    
    print("Overwriting candles for target stocks with dynamic configurations...")
    for sym, config in target_configs.items():
        # Delete existing candles
        db.query(DailyCandle).filter(DailyCandle.symbol == sym).delete()
        
        # Generate VCP candles with configuration scales
        open_val, high, low, close, volume = generate_perfect_vcp_candles(
            trading_dates,
            base_price=config['base_price'],
            volume_factor=config['vol_factor']
        )
        
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
        
        # Update fundamental data to pass fundamental gates with slight score variation
        fund = db.query(CompanyFundamental).filter(CompanyFundamental.symbol == sym).first()
        if fund:
            fund.sector = config['sector']
            fund.roe = 25.0
            fund.roce = 30.0
            fund.debt_to_equity = 0.1
            
            # Vary sales/profit growth to vary fundamental scores
            if sym == 'STOCK001':
                fund.sales_growth_yoy = 20.0
                fund.profit_growth_yoy = 25.0
            elif sym == 'STOCK002':
                fund.sales_growth_yoy = 15.0
                fund.profit_growth_yoy = 18.0
            elif sym == 'STOCK003':
                fund.sales_growth_yoy = 25.0
                fund.profit_growth_yoy = 30.0
            elif sym == 'STOCK004':
                fund.sales_growth_yoy = 28.0
                fund.profit_growth_yoy = 32.0
            else:
                fund.sales_growth_yoy = 22.0
                fund.profit_growth_yoy = 24.0
                
            fund.promoter_pledge = 0.0
            fund.under_surveillance = False
            db.add(fund)
            
    db.commit()
    print("Perfect VCP candles and fundamentals updated.")
    
    # Delete old scan results for the date 2026-06-23 to trigger a fresh scan calculation
    scan_date = datetime.date(2026, 6, 23)
    db.query(ScanResult).filter(ScanResult.date == scan_date).delete()
    db.commit()
    
    # Trigger a dynamic live scan using ScannerService to compute actual VCP, CPR, Trend indicators
    print("Triggering dynamic daily scan to calculate composite scores...")
    from backend.app.services.scanner import ScannerService
    scanner_service = ScannerService()
    scanner_service.run_daily_scan(db, scan_date)
    print("Dynamic daily scan completed and scan results populated successfully!")
    
    db.close()

if __name__ == "__main__":
    main()
