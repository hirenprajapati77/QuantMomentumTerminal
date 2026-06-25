import uuid
import datetime
import logging
import traceback
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from backend.app.storage.database import SessionLocal
from backend.app.models.backtest import BacktestJob, BacktestTrade
from backend.app.models.universe import UniverseStock
from backend.app.models.fundamental import CompanyFundamental
from backend.app.models.candle import DailyCandle
from backend.app.analytics.composite import calculate_raw_signals, compute_composite_scores
from backend.app.backtest.engine import BacktestEngine
from backend.app.core.utils import get_safe_float

logger = logging.getLogger("nse_scanner.backtest_service")



def run_backtest_background_task(job_id: str, score_threshold: float, time_stop_days: int, initial_capital: float):
    logger.info(f"Starting background backtest job {job_id}...")
    db = SessionLocal()
    try:
        # Update job status to RUNNING
        job = db.query(BacktestJob).filter(BacktestJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found in DB.")
            return
        job.status = "RUNNING"
        db.commit()

        # 1. Load active symbols
        active_stocks = db.query(UniverseStock).filter(UniverseStock.is_active == True).all()
        active_symbols = [s.symbol for s in active_stocks]
        if not active_symbols:
            raise Exception("No active symbols found in universe_stocks database.")
        
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

        # 3. Load all candles
        candles_query = db.query(DailyCandle).filter(DailyCandle.symbol.in_(active_symbols)).order_by(DailyCandle.symbol.asc(), DailyCandle.date.asc()).all()
        if not candles_query:
            raise Exception("No candles found in database. Please run validation or ingestion first.")
            
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
        
        # Group by symbol
        candles_by_symbol = {}
        for sym, group in df_all.groupby('symbol'):
            candles_by_symbol[sym] = group.sort_values('date').reset_index(drop=True)

        # 4. Create market average series for RS index
        # Return-based benchmark: mean of daily pct_change across all symbols
        # Prevents high-priced stocks from dominating the benchmark
        df_all_copy = df_all.copy()
        df_all_copy['daily_ret'] = df_all_copy.groupby('symbol')['close'].pct_change()
        market_avg = (
            df_all_copy.groupby('date')['daily_ret']
            .mean()
            .reset_index()
            .rename(columns={'daily_ret': 'market_ret'})
        )
        # Convert mean daily returns to a cumulative index starting at 1.0
        market_avg = market_avg.sort_values('date').reset_index(drop=True)
        market_avg['market_close'] = (1 + market_avg['market_ret'].fillna(0)).cumprod()
        market_avg['return_20d'] = market_avg['market_close'].pct_change(20)
        market_avg['return_50d'] = market_avg['market_close'].pct_change(50)
        market_avg['return_100d'] = market_avg['market_close'].pct_change(100)
        market_avg['close'] = market_avg['market_close']  # alias for rs.py sector_df compatibility
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

        # 6. Run daily signal generation loop
        unique_dates = sorted(list(market_avg_map.keys()))
        signals_dict = {sym: pd.Series(False, index=df_dict[sym].index) for sym in df_dict}

        for t_idx, date in enumerate(unique_dates):
            if t_idx < 101:
                continue # Warmup
                
            candidates = []
            for sym in active_symbols:
                if sym not in df_dict:
                    continue
                sym_df = df_dict[sym]
                if date not in sym_df.index:
                    continue
                row = sym_df.loc[date]
                if row['volume_ratio'] >= 2.0 and row['close_pct'] >= 0.85 and row['upper_wick_pct'] <= 0.15:
                    loc_idx = sym_df.index.get_loc(date)
                    if loc_idx >= 100:
                        candidates.append((sym, loc_idx))
                        
            if not candidates:
                continue

            day_signals = {}
            for sym in active_symbols:
                if sym not in df_dict:
                    continue
                sym_df = df_dict[sym]
                if date not in sym_df.index:
                    continue
                    
                row = sym_df.loc[date]
                m_row = market_avg_map.get(date, {})
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

            for sym, loc_idx in candidates:
                sym_df = df_dict[sym]
                slice_df = sym_df.iloc[:loc_idx+1].reset_index()
                m_slice = market_avg.iloc[:market_avg[market_avg['date'] <= date].index[-1]+1]
                fund_data = fundamentals_map.get(sym, {})
                sector_name = fund_data.get('sector', 'Unknown')
                
                raw_sig = calculate_raw_signals(slice_df, m_slice, fund_data, sector_name)
                day_signals[sym].update(raw_sig)

            day_results = compute_composite_scores(day_signals)

            for sym, loc_idx in candidates:
                if sym in day_results:
                    res = day_results[sym]
                    sig = day_signals[sym]
                    
                    total_score = res["final_score"]
                    breakout_vol_ratio = sig["volume"]["ratio"]
                    trend_passed = sig["trend"]["status"] == "passed"
                    sector_passed = res["sector_score"] == 5
                    
                    close_pct = sig["breakout"]["close_pct_of_range"]
                    upper_wick = sig["breakout"]["upper_wick_pct"]
                    breakout_candles_passed = (close_pct >= 0.85) and (upper_wick <= 0.15)
                    
                    entry_triggered = (
                        (total_score >= score_threshold) and
                        (breakout_vol_ratio >= 2.0) and
                        trend_passed and
                        sector_passed and
                        breakout_candles_passed
                    )
                    if entry_triggered:
                        signals_dict[sym].loc[date] = True

        # 7. Run Backtest Portfolio Simulator
        engine_df_dict = {sym: df_dict[sym].copy() for sym in df_dict}
        engine = BacktestEngine(initial_capital=initial_capital, time_stop_days=time_stop_days)
        metrics = engine.run(engine_df_dict, signals_dict)

        # 8. Persist Trades to Database
        trade_log = metrics.get("trade_log", [])
        for t in trade_log:
            entry_d = t.get("entry_date")
            exit_d = t.get("exit_date")
            
            if isinstance(entry_d, pd.Timestamp):
                entry_d = entry_d.date()
            if isinstance(exit_d, pd.Timestamp):
                exit_d = exit_d.date()
                
            trade_obj = BacktestTrade(
                job_id=job_id,
                symbol=t.get("symbol"),
                direction=t.get("direction"),
                entry_date=entry_d,
                exit_date=exit_d,
                entry_price=float(t.get("entry_price")),
                exit_price=float(t.get("exit_price")) if t.get("exit_price") is not None else None,
                qty=float(t.get("qty")),
                pnl=float(t.get("pnl")) if t.get("pnl") is not None else None,
                reason=t.get("reason")
            )
            db.add(trade_obj)

        # 9. Format equity curve & metrics
        equity_curve_clean = []
        for eq in metrics.get("equity_curve", []):
            d_val = eq.get("date")
            if isinstance(d_val, (datetime.date, pd.Timestamp)):
                d_str = d_val.strftime("%Y-%m-%d")
            else:
                d_str = str(d_val)
            equity_curve_clean.append({
                "date": d_str,
                "equity": float(eq.get("equity"))
            })

        metrics_json = {
            "total_trades": int(metrics.get("total_trades", 0)),
            "win_rate": float(metrics.get("win_rate", 0.0)),
            "total_pnl": float(metrics.get("total_pnl", 0.0)),
            "cagr": float(metrics.get("cagr", 0.0)),
            "sharpe": float(metrics.get("sharpe", 0.0)),
            "max_drawdown": float(metrics.get("max_drawdown", 0.0)),
            "expectancy": float(metrics.get("expectancy", 0.0)),
            "equity_curve": equity_curve_clean
        }

        # Query job again and update metrics
        job = db.query(BacktestJob).filter(BacktestJob.id == job_id).first()
        job.status = "COMPLETED"
        job.metrics = metrics_json
        job.completed_at = datetime.datetime.utcnow()
        db.commit()
        logger.info(f"Background backtest job {job_id} completed successfully!")
    except Exception as e:
        logger.error(f"Error running backtest job {job_id}: {e}", exc_info=True)
        db.rollback()
        job = db.query(BacktestJob).filter(BacktestJob.id == job_id).first()
        if job:
            job.status = "FAILED"
            job.error_message = f"{str(e)}\n{traceback.format_exc()}"
            job.completed_at = datetime.datetime.utcnow()
            db.commit()
    finally:
        db.close()
