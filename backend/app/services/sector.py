import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.fundamental import CompanyFundamental
from backend.app.models.candle import DailyCandle
import datetime

logger = logging.getLogger("nse_scanner.sector")

class SectorService:
    def __init__(self):
        pass

    def get_symbol_sector(self, db: Session, symbol: str) -> str:
        """Returns the sector classification for a symbol"""
        fund = db.query(CompanyFundamental).filter(
            CompanyFundamental.symbol == symbol
        ).first()
        return fund.sector if fund else "Unknown"

    def calculate_sector_returns(self, db: Session, date_val: datetime.date) -> dict:
        """Calculates the average 20-day return for all sectors on a given date"""
        # Find 20 trading days ago
        # To do this, we can find the list of dates from the daily_candles table
        dates_query = db.query(DailyCandle.date).distinct().order_by(DailyCandle.date.desc()).all()
        dates = [d[0] for d in dates_query]
        
        if not dates or date_val not in dates:
            logger.warning(f"Date {date_val} not found in database daily candles.")
            return {}
            
        idx = dates.index(date_val)
        if idx + 20 >= len(dates):
            logger.warning(f"Not enough historical data to calculate 20-day sector returns on {date_val}")
            return {}
            
        t_minus_20 = dates[idx + 20]
        
        # Pull close prices for today and 20 days ago, grouped by sector
        # SQL query to get symbol, sector, close at date_val, and close at t_minus_20
        query_sql = """
            SELECT f.sector, c1.symbol, c1.close as close_today, c2.close as close_past
            FROM company_fundamentals f
            JOIN daily_candles c1 ON f.symbol = c1.symbol AND c1.date = :today
            JOIN daily_candles c2 ON f.symbol = c2.symbol AND c2.date = :past
            WHERE f.sector IS NOT NULL AND f.sector != 'Unknown'
        """
        
        from sqlalchemy import text
        results = db.execute(
            text(query_sql), 
            {"today": date_val, "past": t_minus_20}
        ).fetchall()
        
        # Calculate returns per stock and average by sector
        sector_returns = {}
        sector_counts = {}
        
        for row in results:
            sector = row[0]
            close_today = float(row[2])
            close_past = float(row[3])
            
            if close_past > 0:
                ret = (close_today - close_past) / close_past
                
                if sector not in sector_returns:
                    sector_returns[sector] = 0.0
                    sector_counts[sector] = 0
                
                sector_returns[sector] += ret
                sector_counts[sector] += 1
                
        # Calculate averages
        avg_returns = {}
        for sector, total_ret in sector_returns.items():
            count = sector_counts[sector]
            avg_returns[sector] = round((total_ret / count) * 100, 2)
            
        return avg_returns

    def get_sector_ranking(self, db: Session, date_val: datetime.date) -> dict:
        """Returns the ranking and percentile band of each sector on a given date"""
        avg_returns = self.calculate_sector_returns(db, date_val)
        if not avg_returns:
            return {}
            
        # Sort sectors by returns descending
        sorted_sectors = sorted(avg_returns.items(), key=lambda x: x[1], reverse=True)
        total_sectors = len(sorted_sectors)
        
        ranking = {}
        for rank, (sector, ret) in enumerate(sorted_sectors):
            # Calculate percentile rank: 1.0 is top (best return), 0.0 is bottom
            percentile = 1.0 - (rank / total_sectors) if total_sectors > 1 else 1.0
            
            # Award points based on bands
            # Top 20% of sectors -> 5 pts, Next 20% -> 3, else -> 0
            if percentile >= 0.80:
                points = 5
            elif percentile >= 0.60:
                points = 3
            else:
                points = 0
                
            ranking[sector] = {
                "return_20d": ret,
                "rank": rank + 1,
                "percentile": round(percentile * 100, 2),
                "points": points
            }
            
        return ranking
