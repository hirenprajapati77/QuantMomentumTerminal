import sys
import datetime
import random
from pathlib import Path
import pandas as pd
import numpy as np

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from backend.app.storage.database import init_db, SessionLocal
from backend.app.models.universe import UniverseStock
from backend.app.models.fundamental import CompanyFundamental
from backend.app.models.candle import DailyCandle
from backend.app.models.scan_result import ScanResult

def generate_trading_days(start_date: datetime.date, days_count: int) -> list[datetime.date]:
    dates = []
    current = start_date
    while len(dates) < days_count:
        if current.weekday() < 5:  # Monday to Friday
            dates.append(current)
        current += datetime.timedelta(days=1)
    return dates

def main():
    print("=" * 80)
    print(" NSE Momentum Scanner - Mock Data Seeding Utility ")
    print("=" * 80)
    
    init_db()
    db = SessionLocal()
    
    # 1. Clear existing scanner tables to start fresh
    print("Clearing existing tables...")
    db.query(DailyCandle).delete()
    db.query(CompanyFundamental).delete()
    db.query(UniverseStock).delete()
    db.query(ScanResult).delete()
    db.commit()
    
    # Generate ~280 trading days ending at 2026-06-23
    end_date = datetime.date(2026, 6, 23)
    start_date = end_date - datetime.timedelta(days=400)
    trading_dates = generate_trading_days(start_date, 280)
    # Adjust last date to be exactly 2026-06-23
    trading_dates[-1] = end_date
    
    symbols = [f"STOCK{i:03d}" for i in range(1, 301)]
    print(f"Generating 300 active symbols with {len(trading_dates)} trading days of history each...")
    
    sectors = [
        "Information Technology", "Financial Services", "Healthcare", 
        "Energy", "Fast Moving Consumer Goods", "Automobile", 
        "Construction", "Metals & Mining", "Telecommunication"
    ]
    
    # 2. Seed Universe & Fundamentals
    for i, sym in enumerate(symbols):
        # Universe Stock
        universe_stock = UniverseStock(symbol=sym, is_active=True, exclusion_reason=None)
        db.add(universe_stock)
        
        # Company Fundamental
        # Seed first 15 symbols to pass the fundamental gate perfectly, and others randomly
        is_strong_fundamental = (i < 15)
        sales_growth = random.uniform(15.0, 30.0) if is_strong_fundamental else random.uniform(-10.0, 12.0)
        profit_growth = random.uniform(20.0, 45.0) if is_strong_fundamental else random.uniform(-20.0, 10.0)
        roce = random.uniform(18.0, 35.0) if is_strong_fundamental else random.uniform(5.0, 14.0)
        roe = random.uniform(16.0, 30.0) if is_strong_fundamental else random.uniform(4.0, 12.0)
        debt_to_equity = random.uniform(0.05, 0.4) if is_strong_fundamental else random.uniform(1.2, 3.5)
        pledge = random.uniform(0.0, 2.0) if is_strong_fundamental else random.uniform(5.0, 25.0)
        
        fundamental = CompanyFundamental(
            symbol=sym,
            sector=sectors[i % len(sectors)],
            industry="General Industry",
            market_cap=random.uniform(15000.0, 150000.0),
            sales_growth_qoq=sales_growth,
            sales_growth_yoy=sales_growth,
            profit_growth_yoy=profit_growth,
            roce=roce,
            roe=roe,
            debt_to_equity=debt_to_equity,
            institutional_holding=random.uniform(10.0, 30.0),
            institutional_holding_qoq_change=random.uniform(0.5, 3.0),
            promoter_pledge=pledge,
            under_surveillance=False
        )
        db.add(fundamental)
    db.commit()
    print("Universe and Fundamentals seeded successfully.")
    
    # 3. Seed Daily Candles
    print("Generating candle history (this may take 10-15 seconds)...")
    for i, sym in enumerate(symbols):
        is_momentum_leader = (i < 10)  # STOCK001 to STOCK010
        
        price = 100.0 if is_momentum_leader else random.uniform(50.0, 500.0)
        candles = []
        
        for idx, date in enumerate(trading_dates):
            is_last_day = (idx == len(trading_dates) - 1)
            is_prev_day = (idx == len(trading_dates) - 2)
            
            # Trend calculation
            if is_momentum_leader:
                if is_last_day:
                    # Breakout day: massive jump
                    change = 0.08  # +8%
                elif is_prev_day:
                    # Very tight consolidation day for CPR narrowness
                    change = 0.001
                else:
                    # General steady upward slope
                    change = random.normalvariate(0.003, 0.008)
            else:
                # Random walk
                change = random.normalvariate(-0.0005, 0.02)
                
            price = max(5.0, price * (1.0 + change))
            
            # Candle parameters
            if is_momentum_leader and is_last_day:
                # High at close, low slightly lower, massive volume
                close_val = round(price, 2)
                high_val = close_val
                low_val = round(close_val * 0.98, 2)
                open_val = round(close_val * 0.97, 2)
                volume_val = 5000000  # 5x typical
            elif is_momentum_leader and is_prev_day:
                close_val = round(price, 2)
                high_val = round(close_val * 1.002, 2)
                low_val = round(close_val * 0.998, 2)
                open_val = close_val
                volume_val = 800000
            else:
                close_val = round(price, 2)
                high_val = round(close_val * random.uniform(1.005, 1.03), 2)
                low_val = round(close_val * random.uniform(0.97, 0.995), 2)
                open_val = round(random.uniform(low_val, high_val), 2)
                volume_val = int(random.uniform(500000, 1500000))
                
            candle = DailyCandle(
                symbol=sym,
                date=date,
                open=open_val,
                high=high_val,
                low=low_val,
                close=close_val,
                volume=volume_val,
                delivery_qty=int(volume_val * random.uniform(0.4, 0.7)),
                delivery_pct=round(random.uniform(40.0, 70.0), 2)
            )
            candles.append(candle)
            
        db.bulk_save_objects(candles)
        if (i + 1) % 50 == 0:
            db.commit()
            print(f"  Ingested candles for {i+1}/300 symbols...")
            
    db.commit()
    print("Daily candles seeded successfully!")
    db.close()

if __name__ == "__main__":
    main()
