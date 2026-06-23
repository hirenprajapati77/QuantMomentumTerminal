import datetime
import json
import logging
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from backend.app.models.universe import UniverseStock
from backend.app.models.fundamental import CompanyFundamental
from backend.app.models.candle import DailyCandle
from backend.app.models.scan_result import ScanResult
from backend.app.analytics.composite import calculate_raw_signals, compute_composite_scores
from backend.app.config.settings import settings

logger = logging.getLogger("nse_scanner.scanner")

# ---------------------------------------------------------------------------
# Redis client — lazy-initialised, fails gracefully if Redis is unavailable
# ---------------------------------------------------------------------------
_redis_client = None

def _get_redis():
    """Return a Redis client, or None if Redis is unavailable."""
    global _redis_client
    if _redis_client is False:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        _redis_client = client
        logger.info("Redis cache connected: %s", settings.REDIS_URL)
    except Exception as exc:
        logger.warning("Redis unavailable — caching disabled: %s", exc)
        _redis_client = False
    return _redis_client if _redis_client else None


def _cache_key(symbol: str, date: datetime.date) -> str:
    return f"scanner:signals:{symbol}:{date.isoformat()}"


def _read_cache(symbol: str, date: datetime.date):
    """Return cached raw signals dict for (symbol, date), or None on miss/error."""
    client = _get_redis()
    if client is None:
        return None
    try:
        raw = client.get(_cache_key(symbol, date))
        if raw:
            logger.debug("Cache HIT  %s %s", symbol, date)
            return json.loads(raw)
        logger.debug("Cache MISS %s %s", symbol, date)
    except Exception as exc:
        logger.warning("Redis read error for %s %s: %s", symbol, date, exc)
    return None


def _write_cache(symbol: str, date: datetime.date, signals: dict, ttl_seconds: int = 86400):
    """Persist raw signals to Redis with TTL. Silently swallows errors."""
    client = _get_redis()
    if client is None:
        return
    try:
        client.setex(_cache_key(symbol, date), ttl_seconds, json.dumps(signals))
    except Exception as exc:
        logger.warning("Redis write error for %s %s: %s", symbol, date, exc)

def get_safe_float(val, default=0.0):
    if val is None or pd.isna(val):
        return default
    try:
        return float(val)
    except:
        return default

class ScannerService:
    def resolve_pending_entries(self, db: Session):
        """
        Looks up all ScanResult records where entry_status == 'Pending'.
        Checks if a candle for the next chronological trading day exists.
        If yes, recomputes entry, stop, targets, and updates status to 'Filled' or 'Stopped Out'.
        Also updates holding_days for Filled positions.
        """
        pending_results = db.query(ScanResult).filter(ScanResult.entry_status == "Pending").all()
        if pending_results:
            logger.info(f"Checking {len(pending_results)} pending scan results for entry resolution...")
            for r in pending_results:
                next_candle = db.query(DailyCandle).filter(
                    DailyCandle.symbol == r.symbol,
                    DailyCandle.date > r.date
                ).order_by(DailyCandle.date.asc()).first()
                
                if next_candle:
                    entry_price = float(next_candle.open)
                    stop_price = entry_price * 0.94
                    
                    if float(next_candle.low) <= stop_price:
                        r.entry_status = "Stopped Out"
                        r.remarks = (r.remarks or "") + " [Stopped Out on Entry Bar]"
                        r.holding_days = 1
                    else:
                        r.entry_status = "Filled"
                        count = db.query(DailyCandle).filter(
                            DailyCandle.symbol == r.symbol,
                            DailyCandle.date > r.date
                        ).count()
                        r.holding_days = count
                        
                    r.entry = entry_price
                    r.stop = stop_price
                    r.target1 = entry_price * 1.10
                    r.target2 = entry_price * 1.20
                    r.target3 = None
                    db.add(r)
                    logger.info(f"Resolved pending entry for {r.symbol} on {r.date}: entry={entry_price}, status={r.entry_status}")
            db.commit()

        # Also update holding days for already filled positions
        filled_results = db.query(ScanResult).filter(ScanResult.entry_status == "Filled").all()
        if filled_results:
            for r in filled_results:
                count = db.query(DailyCandle).filter(
                    DailyCandle.symbol == r.symbol,
                    DailyCandle.date > r.date
                ).count()
                r.holding_days = count
                db.add(r)
            db.commit()

    def run_daily_scan(self, db: Session, target_date: datetime.date) -> list[ScanResult]:
        """
        Executes composite strategy scoring across the entire active universe for target_date.
        Saves results to the database and returns them.
        """
        logger.info(f"Starting daily scan for {target_date}...")
        self.resolve_pending_entries(db)
        
        # 1. Load active symbols
        active_stocks = db.query(UniverseStock).filter(UniverseStock.is_active == True).all()
        active_symbols = [s.symbol for s in active_stocks]
        if not active_symbols:
            logger.warning("No active symbols found in universe_stocks.")
            return []
            
        logger.info(f"Loaded {len(active_symbols)} active symbols for scan.")
        
        # 2. Load fundamentals
        fundamentals = db.query(CompanyFundamental).all()
        fundamentals_map = {}
        for f in fundamentals:
            fundamentals_map[f.symbol] = {
                "sales_growth_qoq": get_safe_float(f.sales_growth_qoq),
                "sales_growth_yoy": get_safe_float(f.sales_growth_yoy),
                "profit_growth_yoy": get_safe_float(f.profit_growth_yoy),
                "roce": get_safe_float(f.roce),
                "roe": get_safe_float(f.roe),
                "debt_to_equity": get_safe_float(f.debt_to_equity, 999.0),
                "institutional_holding_qoq_change": get_safe_float(f.institutional_holding_qoq_change),
                "sector": f.sector or "Unknown"
            }
            
        # 3. Load all candles up to target_date
        # We need historical candles for moving averages, RS returns etc. (at least 150 candles)
        candles_query = db.query(DailyCandle).filter(
            DailyCandle.symbol.in_(active_symbols),
            DailyCandle.date <= target_date
        ).order_by(DailyCandle.date.asc()).all()
        
        if not candles_query:
            logger.warning(f"No candles found up to {target_date}.")
            return []
            
        all_candles = []
        for c in candles_query:
            all_candles.append({
                "symbol": c.symbol,
                "date": c.date,
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": int(c.volume)
            })
            
        df_all = pd.DataFrame(all_candles)
        
        # Group candles by symbol
        candles_by_symbol = {}
        for sym, group in df_all.groupby('symbol'):
            candles_by_symbol[sym] = group.sort_values('date').reset_index(drop=True)
            
        # 4. Create market average series for RS index
        market_avg = df_all.groupby('date')['close'].mean().reset_index()
        market_avg = market_avg.sort_values('date').reset_index(drop=True)
        market_avg['return_20d'] = market_avg['close'].pct_change(20)
        market_avg['return_50d'] = market_avg['close'].pct_change(50)
        market_avg['return_100d'] = market_avg['close'].pct_change(100)
        market_avg_map = market_avg.set_index('date').to_dict('index')
        
        # 5. Precompute breakout candle parameters
        df_dict = {}
        for sym in active_symbols:
            if sym not in candles_by_symbol:
                continue
                
            df = candles_by_symbol[sym].copy()
            if len(df) < 50:
                continue
                
            volume_ma50 = df['volume'].shift(1).rolling(50).mean()
            df['volume_ratio'] = df['volume'] / volume_ma50
            
            range_val = df['high'] - df['low']
            df['close_pct'] = np.where(range_val > 0, (df['close'] - df['low']) / range_val, 0.0)
            
            upper_wick = df['high'] - df[['open', 'close']].max(axis=1)
            df['upper_wick_pct'] = np.where(range_val > 0, upper_wick / range_val, 0.0)
            
            df['return_20d'] = df['close'].pct_change(20)
            df['return_50d'] = df['close'].pct_change(50)
            df['return_100d'] = df['close'].pct_change(100)
            
            df_dict[sym] = df.set_index('date')
            
        # 6. Run daily scoring for target_date
        # Check candidates (only stocks that actually have data on target_date)
        candidates = []
        for sym in active_symbols:
            if sym not in df_dict:
                continue
            sym_df = df_dict[sym]
            if target_date not in sym_df.index:
                continue
                
            row = sym_df.loc[target_date]
            # Fast filter checks
            if row['volume_ratio'] >= 2.0 and row['close_pct'] >= 0.85 and row['upper_wick_pct'] <= 0.15:
                loc_idx = sym_df.index.get_loc(target_date)
                if loc_idx >= 100:
                    candidates.append((sym, loc_idx))
                    
        # Gather signals for all symbols on this date
        day_signals = {}
        for sym in active_symbols:
            if sym not in df_dict:
                continue
            sym_df = df_dict[sym]
            if target_date not in sym_df.index:
                continue
                
            row = sym_df.loc[target_date]
            m_row = market_avg_map.get(target_date, {})
            
            rel_20 = row['return_20d'] - m_row.get('return_20d', 0.0) if not pd.isna(row['return_20d']) else 0.0
            rel_50 = row['return_50d'] - m_row.get('return_50d', 0.0) if not pd.isna(row['return_50d']) else 0.0
            rel_100 = row['return_100d'] - m_row.get('return_100d', 0.0) if not pd.isna(row['return_100d']) else 0.0
            
            day_signals[sym] = {
                "sector": fundamentals_map.get(sym, {}).get("sector", "Unknown"),
                "return_20d": row['return_20d'] if not pd.isna(row['return_20d']) else 0.0,
                "trend": {"score": 0, "status": "failed"},
                "vcp": {"score": 0, "status": "failed"},
                "vdu": {"score": 0},
                "rs_raw": {"rel_20": rel_20, "rel_50": rel_50, "rel_100": rel_100},
                "volume": {"score": 0, "ratio": row['volume_ratio']},
                "breakout": {"score": 0, "close_pct_of_range": row['close_pct'], "upper_wick_pct": row['upper_wick_pct']},
                "cpr": {"score": 0},
                "fundamental": {"score": 0, "passes_gate": False}
            }
            
        # Run expensive indicator calculations only for candidates
        for sym, loc_idx in candidates:
            # --- Redis cache check (keyed by symbol + date) ---
            cached = _read_cache(sym, target_date)
            if cached is not None:
                day_signals[sym].update(cached)
                continue

            sym_df = df_dict[sym]
            slice_df = sym_df.iloc[:loc_idx+1].reset_index()
            
            # Sliced market average
            m_idx = market_avg[market_avg['date'] <= target_date].index
            if len(m_idx) > 0:
                m_slice = market_avg.iloc[:m_idx[-1]+1]
            else:
                m_slice = market_avg
                
            fund_data = fundamentals_map.get(sym, {})
            sector_name = fund_data.get('sector', 'Unknown')
            
            # Compute actual indicators and cache result
            raw_sig = calculate_raw_signals(slice_df, m_slice, fund_data, sector_name)
            _write_cache(sym, target_date, raw_sig)
            day_signals[sym].update(raw_sig)
            
        if not day_signals:
            logger.info("No active signals calculated for target date.")
            return []
            
        # Compute composite scores
        day_results = compute_composite_scores(day_signals)
        
        # 7. Persist to DB (and overwrite existing records for symbol/date if they exist)
        # Delete old scan results for target_date to avoid duplicates
        db.query(ScanResult).filter(ScanResult.date == target_date).delete()
        
        scan_results = []
        for sym, res in day_results.items():
            # Check if next candle exists (for retrospective runs)
            next_candle = db.query(DailyCandle).filter(
                DailyCandle.symbol == sym,
                DailyCandle.date > target_date
            ).order_by(DailyCandle.date.asc()).first()
            
            # Default values (signal day setup)
            t_candle = db.query(DailyCandle).filter(
                DailyCandle.symbol == sym,
                DailyCandle.date == target_date
            ).first()
            ref_close = float(t_candle.close) if t_candle else 0.0
            
            remarks_suffix = ""
            if next_candle:
                entry_price = float(next_candle.open)
                stop_price = entry_price * 0.94
                if float(next_candle.low) <= stop_price:
                    entry_status = "Stopped Out"
                    remarks_suffix = " [Stopped Out on Entry Bar]"
                    holding_days = 1
                else:
                    entry_status = "Filled"
                    holding_days = db.query(DailyCandle).filter(
                        DailyCandle.symbol == sym,
                        DailyCandle.date > target_date
                    ).count()
            else:
                entry_price = ref_close
                stop_price = entry_price * 0.94
                entry_status = "Pending"
                holding_days = 0
            
            # Confidence based on grade
            grade = res["grade"]
            if grade in ["Elite", "A+"]:
                confidence = "High"
            elif grade == "A":
                confidence = "Medium"
            elif grade == "Watch":
                confidence = "Low"
            else:
                confidence = "None"
                
            # Construct remarks using VCP contraction count
            contraction_count = day_signals.get(sym, {}).get("vcp", {}).get("contraction_count", 0)
            vol_ratio = res["breakout_vol_ratio"]
            close_pct = res["close_pct_of_range"]
            trend_status = res["trend_status"]
            remarks = f"Breakout: Vol Ratio {vol_ratio:.1f}x, Close {close_pct*100:.0f}% of range. VCP Contractions: {contraction_count}. Trend: {trend_status}.{remarks_suffix}"
            
            scan_obj = ScanResult(
                date=target_date,
                symbol=sym,
                technical_score=res["technical_score"],
                fundamental_score=res["fundamental_score"],
                final_score=res["final_score"],
                grade=grade,
                entry_triggered=res["entry_triggered"],
                breakout_vol_ratio=res["breakout_vol_ratio"],
                close_pct_of_range=res["close_pct_of_range"],
                upper_wick_pct=res["upper_wick_pct"],
                passes_fundamental=res["passes_fundamental"],
                
                # Persistence additions
                sector=res["sector"],
                entry=entry_price,
                entry_status=entry_status,
                stop=stop_price,
                target1=entry_price * 1.10,
                target2=entry_price * 1.20,
                target3=None,  # dynamic trailing stop
                confidence=confidence,
                remarks=remarks,
                holding_days=holding_days
            )
            db.add(scan_obj)
            scan_results.append(scan_obj)
            
        db.commit()
        logger.info(f"Daily scan for {target_date} finished. Saved {len(scan_results)} records.")
        return scan_results
