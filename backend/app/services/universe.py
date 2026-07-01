import datetime
import logging
import io
import requests
import pandas as pd
from sqlalchemy.orm import Session
from backend.app.config.settings import settings
from backend.app.core.exceptions import IngestionException
from backend.app.models.universe import UniverseStock
from backend.app.models.fundamental import CompanyFundamental
from backend.app.models.candle import DailyCandle
from backend.app.services.fundamental import FundamentalService
from backend.app.services.market_data import MarketDataService

logger = logging.getLogger("nse_scanner.universe")

class UniverseService:
    def __init__(self):
        self.fundamental_service = FundamentalService()
        self.market_data_service = MarketDataService()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Referer': 'https://www.nseindia.com/'
        }

    def download_nifty_500_list(self) -> list[str]:
        """Downloads the Nifty 500 constituent symbols from NSE"""
        url = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"
        logger.info(f"Downloading Nifty 500 list from {url}...")
        
        # Using requests session to ensure cookies are initialized
        session = requests.Session()
        session.get("https://www.nseindia.com/", headers=self.headers, timeout=10)
        
        response = session.get(url, headers=self.headers, timeout=15)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            # Clean symbols (headers are: Company Name, Industry, Symbol, Series, ISIN Code)
            symbols = df["Symbol"].str.strip().tolist()
            logger.info(f"Successfully loaded {len(symbols)} symbols from Nifty 500 list.")
            return symbols
        else:
            raise IngestionException(f"Failed to download Nifty 500 list. HTTP {response.status_code}")

    def check_listing_history_2y(self, symbol: str) -> bool:
        """Verifies if the stock has at least 2 years of listed history using Fyers.
        Requires a minimum density of trading days (>= 400 days) over the last 2 years.
        """
        today = datetime.date.today()
        two_years_ago = today - datetime.timedelta(days=365 * 2)
        
        try:
            df = self.market_data_service.fetch_fyers_ohlcv(symbol, two_years_ago, today)
            if df.empty:
                return False
            
            trading_days_count = len(df)
            if trading_days_count < 400:
                logger.warning(f"Stock {symbol} has only {trading_days_count} trading days in the last 2 years (expected >= 400).")
                return False
            return True
        except Exception as e:
            logger.warning(f"Error checking 2y history for {symbol}: {e}")
            return False

    def apply_hard_filters(self, db: Session, symbol: str) -> tuple[bool, str]:
        """Applies all Stage 1.4 hard filters for a symbol. Returns (Passed, Reason)"""
        today = datetime.date.today()
        
        # 1. Fetch or Scrape Fundamentals
        fund = db.query(CompanyFundamental).filter(
            CompanyFundamental.symbol == symbol
        ).first()
        
        if not fund:
            try:
                fund = self.fundamental_service.ingest_company_fundamentals(db, symbol)
            except Exception as e:
                logger.warning(f"Could not ingest fundamentals for {symbol}: {e}")
                return False, f"Missing fundamentals: {e}"

        # 2. Market Cap Filter (> 10,000 Cr)
        mc = float(fund.market_cap) if fund.market_cap else 0.0
        if mc < 10000.0:
            return False, f"Market Cap (Rs. {mc:,.1f} Cr) < Rs. 10,000 Cr"

        # 3. Promoter Pledge Filter (< 10%)
        pledge = float(fund.promoter_pledge) if fund.promoter_pledge is not None else 0.0
        if pledge >= 10.0:
            return False, f"Promoter pledge ({pledge:.1f}%) >= 10%"

        # 4. Under Surveillance Filter (ASM/GSM)
        if fund.under_surveillance:
            return False, "Stock currently under ASM/GSM surveillance framework"

        # 5. Listed History Filter (>= 2 Years)
        if not self.check_listing_history_2y(symbol):
            return False, "Listed history < 2 years"

        # 6. Average Traded Value Filter (> 50 Cr/day over last 20 days)
        # Ensure we have at least 20 daily candles in database.
        # If not, download the last 30 calendar days (~20 trading days) from Fyers
        candles_count = db.query(DailyCandle).filter(
            DailyCandle.symbol == symbol
        ).count()
        
        if candles_count < 20:
            start_date = today - datetime.timedelta(days=35)
            try:
                self.market_data_service.ingest_symbol_data(db, symbol, start_date, today)
            except Exception as e:
                logger.warning(f"Could not ingest historical candles for {symbol} to calculate avg value: {e}")
                
        # Query the last 20 candles
        candles = db.query(DailyCandle).filter(
            DailyCandle.symbol == symbol
        ).order_by(DailyCandle.date.desc()).limit(20).all()
        
        if len(candles) < 15:  # Allow some margin if newly listed/data gap, but need minimum 15
            return False, f"Insufficient price history to calculate traded value (found {len(candles)} days)"
            
        # Calculate average daily traded value = mean(close * volume)
        traded_values = [float(c.close) * int(c.volume) for c in candles]
        avg_value = sum(traded_values) / len(traded_values)
        avg_value_cr = avg_value / 10000000.0  # Convert to Crores (1 Cr = 10,000,000)
        
        if avg_value_cr < 50.0:
            return False, f"Avg traded value (Rs. {avg_value_cr:.1f} Cr/day) < Rs. 50 Cr/day"

        return True, None

    def rebuild_universe(self, db: Session) -> dict:
        """Downloads Nifty 500 list, applies filters, and populates the universe_stocks table"""
        try:
            symbols = self.download_nifty_500_list()
            
            passed_count = 0
            failed_count = 0
            
            for index, symbol in enumerate(symbols):
                logger.info(f"[{index+1}/{len(symbols)}] Filtering {symbol}...")
                passed, reason = self.apply_hard_filters(db, symbol)
                
                db_stock = db.query(UniverseStock).filter(
                    UniverseStock.symbol == symbol
                ).first()
                
                if not db_stock:
                    db_stock = UniverseStock(
                        symbol=symbol,
                        is_active=passed,
                        exclusion_reason=reason[:250] if reason else None
                    )
                    db.add(db_stock)
                else:
                    db_stock.is_active = passed;
                    db_stock.exclusion_reason = reason[:250] if reason else None
                    
                if passed:
                    passed_count += 1
                else:
                    failed_count += 1
                    
                # Commit periodically
                if index % 20 == 0:
                    db.commit()
                    
            db.commit()
            return {
                "total_nifty500": len(symbols),
                "passed": passed_count,
                "failed": failed_count
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error rebuilding universe: {e}", exc_info=True)
            raise
