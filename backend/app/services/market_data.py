import time
import datetime
import logging
import requests
import zipfile
import io
import pandas as pd
from sqlalchemy.orm import Session
from backend.app.config.settings import settings
from backend.app.core.exceptions import FyersTokenExpiredException, IngestionException
from backend.app.models.candle import DailyCandle
from backend.app.core.crypto import decrypt_str

logger = logging.getLogger("nse_scanner.market_data")

class MarketDataService:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.nseindia.com/'
        }

    def _get_fyers_token(self) -> str:
        """Reads cached Fyers access token or raises exception if missing/expired"""
        token_path = settings.token_path
        if not token_path.exists():
            logger.critical("Fyers access token file missing. Action required: Run Fyers login helper.")
            raise FyersTokenExpiredException("Fyers token file missing. Please run login_fyers.py.")
        
        # Check token modification time (if older than 24 hours, consider expired)
        mtime = datetime.datetime.fromtimestamp(token_path.stat().st_mtime, datetime.timezone.utc)
        age = datetime.datetime.now(datetime.timezone.utc) - mtime
        if age > datetime.timedelta(hours=24):
            logger.critical("Fyers access token is older than 24 hours. Action required: Run Fyers login helper.")
            raise FyersTokenExpiredException("Fyers token expired. Please run login_fyers.py.")
            
        return decrypt_str(token_path.read_text().strip())

    def _fetch_fyers_ohlcv_chunk(self, symbol: str, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """Helper to fetch a single sub-365 day segment of OHLCV candles from Fyers History API"""
        token = self._get_fyers_token()
        fyers_symbol = f"NSE:{symbol}-EQ"
        
        url = "https://api-t1.fyers.in/data/history"
        headers = {
            "Authorization": f"{settings.FYERS_APP_ID}:{token}"
        }
        params = {
            "symbol": fyers_symbol,
            "resolution": "D",
            "date_format": "1",  # YYYY-MM-DD string format
            "range_from": start_date.strftime("%Y-%m-%d"),
            "range_to": end_date.strftime("%Y-%m-%d"),
            "cont_flag": "0"
        }
        
        max_retries = 3
        backoff = 1.0
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(f"Fetching Fyers OHLCV chunk for {symbol} from {start_date} to {end_date} (attempt {attempt})...")
                response = requests.get(url, params=params, headers=headers, timeout=15)
                
                if response.status_code == 401:
                    logger.critical("Fyers API returned 401 Unauthorized. Access token expired.")
                    raise FyersTokenExpiredException("Fyers access token unauthorized. Please run login_fyers.py.")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("s") == "ok":
                        candles = data.get("candles", [])
                        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
                        # Convert epoch timestamps to datetime.date
                        # Fyers returns epoch timestamp in seconds at 00:00:00 UTC or market open
                        df["date"] = df["timestamp"].apply(lambda t: datetime.datetime.fromtimestamp(t, datetime.timezone.utc).date())
                        df = df.drop(columns=["timestamp"])
                        return df
                    elif data.get("s") == "no_data":
                        logger.warning(f"No OHLCV data found for {symbol} from {start_date} to {end_date}")
                        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
                    else:
                        raise IngestionException(f"Fyers data error: {data.get('message', 'Unknown error')}")
                else:
                    logger.warning(f"Fyers HTTP {response.status_code}: {response.text}")
                    
            except requests.RequestException as e:
                logger.warning(f"Network error on attempt {attempt}: {e}")
            
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                
        raise IngestionException(f"Failed to fetch Fyers OHLCV for {symbol} after {max_retries} attempts.")

    def fetch_fyers_ohlcv(self, symbol: str, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """Fetches OHLCV candles from Fyers History API, automatically splitting into sub-365 day chunks if needed"""
        if start_date > end_date:
            raise ValueError(f"start_date {start_date} cannot be after end_date {end_date}")
            
        chunks = []
        curr_start = start_date
        while curr_start <= end_date:
            curr_end = min(curr_start + datetime.timedelta(days=364), end_date)
            chunks.append((curr_start, curr_end))
            curr_start = curr_end + datetime.timedelta(days=1)
            
        dfs = []
        for s_date, e_date in chunks:
            df_chunk = self._fetch_fyers_ohlcv_chunk(symbol, s_date, e_date)
            if not df_chunk.empty:
                dfs.append(df_chunk)
                
        if not dfs:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
            
        combined_df = pd.concat(dfs).drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
        return combined_df

    def download_nse_bhavcopy(self, date: datetime.date) -> pd.DataFrame:
        """Downloads and parses security-wise daily bhavcopy from NSE archives"""
        date_str = date.strftime("%d%m%Y")  # Format: DDMMYYYY
        url = f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{date_str}.csv"
        
        max_retries = 3
        backoff = 2.0
        
        # Need session to establish cookies and bypass basic robot checks
        session = requests.Session()
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(f"Downloading NSE Bhavcopy for {date} (attempt {attempt})...")
                # Touch homepage first to get cookies
                session.get("https://www.nseindia.com/", headers=self.headers, timeout=10)
                
                response = session.get(url, headers=self.headers, timeout=15)
                
                if response.status_code == 200:
                    # Parse CSV
                    # The CSV contains spaces in column headers, so we strip them
                    df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
                    df.columns = [col.strip() for col in df.columns]
                    
                    # Normalize columns
                    # SYMBOL, SERIES, DATE1, PREV_CLOSE, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, LAST_PRICE, CLOSE_PRICE, AVG_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES, DELIV_QTY, DELIV_PER
                    required_cols = {"SYMBOL", "SERIES", "TTL_TRD_QNTY", "DELIV_QTY", "DELIV_PER"}
                    if not required_cols.issubset(df.columns):
                        raise IngestionException(f"Missing required columns in Bhavcopy. Found: {list(df.columns)}")
                        
                    # Filter only EQ series (standard equity delivery)
                    df = df[df["SERIES"].str.strip() == "EQ"]
                    
                    # Map to target schema
                    df["symbol"] = df["SYMBOL"].str.strip()
                    df["volume"] = pd.to_numeric(df["TTL_TRD_QNTY"], errors='coerce').fillna(0).astype('int64')
                    df["delivery_qty"] = pd.to_numeric(df["DELIV_QTY"], errors='coerce').fillna(0).astype('int64')
                    
                    # Parse DELIV_PER: sometimes contains '-' or is empty, we handle it
                    df["delivery_pct"] = pd.to_numeric(df["DELIV_PER"], errors='coerce').fillna(0.0)
                    
                    return df[["symbol", "volume", "delivery_qty", "delivery_pct"]]
                    
                elif response.status_code == 404:
                    logger.warning(f"Bhavcopy not found for {date} (status 404). Likely a weekend or market holiday.")
                    return pd.DataFrame(columns=["symbol", "volume", "delivery_qty", "delivery_pct"])
                else:
                    logger.warning(f"NSE Bhavcopy HTTP {response.status_code}: {response.text}")
                    
            except Exception as e:
                logger.warning(f"Error downloading Bhavcopy on attempt {attempt}: {e}")
                
            if attempt < max_retries:
                time.sleep(backoff)
                backoff *= 2
                
        raise IngestionException(f"Failed to download NSE Bhavcopy for {date} after {max_retries} attempts.")

    def ingest_symbol_data(self, db: Session, symbol: str, start_date: datetime.date, end_date: datetime.date, bhavcopy_cache: dict = None) -> int:
        """Fetches OHLCV from Fyers, enriches with Delivery from cached Bhavcopies, and stores in DB"""
        try:
            # 1. Fetch OHLCV from Fyers
            ohlcv_df = self.fetch_fyers_ohlcv(symbol, start_date, end_date)
            if ohlcv_df.empty:
                return 0
                
            # Batch fetch all existing DailyCandle records for this symbol in date range to avoid N+1 queries
            existing_candles = db.query(DailyCandle).filter(
                DailyCandle.symbol == symbol,
                DailyCandle.date >= start_date,
                DailyCandle.date <= end_date
            ).all()
            
            # Map existing candles by YYYY-MM-DD string format to prevent type/tz mismatches
            candle_map = {}
            for c in existing_candles:
                d_key = c.date.strftime("%Y-%m-%d") if hasattr(c.date, "strftime") else str(c.date)
                candle_map[d_key] = c
                
            records_count = 0
            # 2. Iterate through each day and enrich
            for _, row in ohlcv_df.iterrows():
                date_val = row["date"]
                
                # Fetch delivery data for this date
                delivery_qty = None
                delivery_pct = None
                
                if bhavcopy_cache is not None and date_val in bhavcopy_cache:
                    bhav_df = bhavcopy_cache[date_val]
                    symbol_bhav = bhav_df[bhav_df["symbol"] == symbol]
                    if not symbol_bhav.empty:
                        delivery_qty = int(symbol_bhav.iloc[0]["delivery_qty"])
                        delivery_pct = float(symbol_bhav.iloc[0]["delivery_pct"])
                
                # If not in cache, try downloading it once and record result (even if empty) to avoid redundant requests
                if delivery_qty is None and (bhavcopy_cache is None or date_val not in bhavcopy_cache):
                    try:
                        bhav_df = self.download_nse_bhavcopy(date_val)
                        bhav_res = bhav_df if (bhav_df is not None and not bhav_df.empty) else pd.DataFrame()
                        if bhavcopy_cache is not None:
                            bhavcopy_cache[date_val] = bhav_res
                        if not bhav_res.empty:
                            symbol_bhav = bhav_res[bhav_res["symbol"] == symbol]
                            if not symbol_bhav.empty:
                                delivery_qty = int(symbol_bhav.iloc[0]["delivery_qty"])
                                delivery_pct = float(symbol_bhav.iloc[0]["delivery_pct"])
                    except Exception as ex:
                        if bhavcopy_cache is not None:
                            bhavcopy_cache[date_val] = pd.DataFrame()
                        logger.warning(f"Could not fetch delivery details for {symbol} on {date_val}: {ex}")
                
                # Lookup DB record using normalized string key representation
                d_key = date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else str(date_val)
                db_candle = candle_map.get(d_key)
                
                if not db_candle:
                    db_candle = DailyCandle(
                        symbol=symbol,
                        date=date_val,
                        open=row["open"],
                        high=row["high"],
                        low=row["low"],
                        # NOTE: We use Fyers' settled closing price (VWAP-based close), not Last Traded Price (LTP)
                        close=row["close"],
                        volume=int(row["volume"]),
                        delivery_qty=delivery_qty,
                        delivery_pct=delivery_pct
                    )
                    db.add(db_candle)
                    candle_map[d_key] = db_candle
                else:
                    db_candle.open = row["open"]
                    db_candle.high = row["high"]
                    db_candle.low = row["low"]
                    db_candle.close = row["close"]
                    db_candle.volume = int(row["volume"])
                    if delivery_qty is not None:
                        db_candle.delivery_qty = delivery_qty
                        db_candle.delivery_pct = delivery_pct
                
                records_count += 1
                
            db.commit()
            return records_count
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error ingesting data for symbol {symbol}: {e}", exc_info=True)
            raise
