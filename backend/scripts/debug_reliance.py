import sys
import datetime
import requests
import json
import hashlib
import yfinance as yf
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from backend.app.config.settings import settings

def debug_data():
    symbol = "RELIANCE"
    fyers_symbol = f"NSE:{symbol}-EQ"
    
    # Read token
    token_path = settings.token_path
    if not token_path.exists():
        print("Token missing!")
        return
    token = token_path.read_text().strip()
    
    # 1. Fetch from yfinance
    print("\n--- Yahoo Finance Data for RELIANCE ---")
    ticker = yf.Ticker("RELIANCE.NS")
    # Query for historical data
    df_yf = ticker.history(start="2026-06-18", end="2026-06-23")
    print(df_yf)
    
    # 2. Fetch from Fyers
    print("\n--- Fyers History API Raw Response for RELIANCE ---")
    url = "https://api-t1.fyers.in/data/history"
    headers = {
        "Authorization": f"{settings.FYERS_APP_ID}:{token}"
    }
    params = {
        "symbol": fyers_symbol,
        "resolution": "D",
        "date_format": "1",
        "range_from": "2026-06-18",
        "range_to": "2026-06-23",
        "cont_flag": "0"
    }
    
    response = requests.get(url, params=params, headers=headers)
    print("Fyers Status:", response.status_code)
    if response.status_code == 200:
        data = response.json()
        print("Fyers JSON keys:", list(data.keys()))
        if data.get("s") == "ok":
            candles = data.get("candles", [])
            for c in candles:
                # [epoch, open, high, low, close, volume]
                dt = datetime.datetime.fromtimestamp(c[0])
                print(f"Epoch: {c[0]} -> Date: {dt} | Open: {c[1]} | High: {c[2]} | Low: {c[3]} | Close: {c[4]} | Volume: {c[5]}")
        else:
            print("Fyers error:", data)
    else:
        print("Fyers HTTP error:", response.text)

    # 3. Query local database
    print("\n--- Stored Data in SQLite Database ---")
    import sqlite3
    db_path = Path("data/scanner.db")
    if db_path.exists():
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_candles WHERE symbol='RELIANCE' AND date='2026-06-22'")
        row = cursor.fetchone()
        print("Stored Row:", row)
        conn.close()
    else:
        print("Database file not found at", db_path)

if __name__ == "__main__":
    debug_data()
