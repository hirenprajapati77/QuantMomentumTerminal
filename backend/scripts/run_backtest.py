import os
import sys
import datetime
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from backend.app.storage.database import SessionLocal
from backend.app.services.market_data import MarketDataService
from backend.app.analytics.composite import calculate_raw_signals, compute_composite_scores
from backend.app.backtest.engine import BacktestEngine
from backend.app.models.fundamental import CompanyFundamental
from backend.app.models.candle import DailyCandle

def get_safe_float(val, default=0.0):
    if val is None or pd.isna(val):
        return default
    try:
        return float(val)
    except:
        return default

def execute_single_backtest_run(
    df_dict: dict, 
    market_avg_map: dict, 
    market_avg: pd.DataFrame, 
    active_symbols: list, 
    fundamentals_map: dict, 
    score_threshold: float, 
    time_stop_days: int, 
    run_name: str
) -> dict:
    """Helper to run a backtest with a specific entry score threshold and time stop duration."""
    
    unique_dates = sorted(list(market_avg_map.keys()))
    
    # Initialize signals series (all False)
    signals_dict = {}
    for sym in active_symbols:
        if sym in df_dict:
            signals_dict[sym] = pd.Series(False, index=df_dict[sym].index)
            
    print(f"\n[{run_name}] Simulating daily scoring with Entry Score >= {score_threshold} and Time Stop = {time_stop_days} days...")
    
    # Daily signal calculation loop
    for t_idx, date in enumerate(unique_dates):
        if t_idx < 101:
            continue  # Warmup
            
        # 1. Find symbols that meet basic breakout candle parameters today
        candidates = []
        for sym in active_symbols:
            if sym not in df_dict:
                continue
            sym_df = df_dict[sym]
            if date not in sym_df.index:
                continue
                
            row = sym_df.loc[date]
            # Fast filter checks
            if row['volume_ratio'] >= 2.0 and row['close_pct'] >= 0.85 and row['upper_wick_pct'] <= 0.15:
                # Ensure they have enough history
                loc_idx = sym_df.index.get_loc(date)
                if loc_idx >= 100:
                    candidates.append((sym, loc_idx))
                    
        if not candidates:
            continue
            
        # 2. Gather raw relative strength and 20d returns for all symbols on this date
        day_signals = {}
        for sym in active_symbols:
            if sym not in df_dict:
                continue
            sym_df = df_dict[sym]
            if date not in sym_df.index:
                continue
                
            row = sym_df.loc[date]
            m_row = market_avg_map.get(date, {})
            
            # Compute or fetch precalculated raw RS returns
            rel_20 = row['return_20d'] - m_row.get('return_20d', 0.0) if not pd.isna(row['return_20d']) else 0.0
            rel_50 = row['return_50d'] - m_row.get('return_50d', 0.0) if not pd.isna(row['return_50d']) else 0.0
            rel_100 = row['return_100d'] - m_row.get('return_100d', 0.0) if not pd.isna(row['return_100d']) else 0.0
            
            # Pack all indicators (mocked/zeros first, filled only for candidates)
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
            
        # 3. Run expensive indicator calculations ONLY for candidates
        for sym, loc_idx in candidates:
            sym_df = df_dict[sym]
            slice_df = sym_df.iloc[:loc_idx+1].reset_index()
            
            # Sliced market average
            m_slice = market_avg.iloc[:market_avg[market_avg['date'] <= date].index[-1]+1]
            
            fund_data = fundamentals_map.get(sym, {})
            sector_name = fund_data.get('sector', 'Unknown')
            
            # Compute actual indicators
            raw_sig = calculate_raw_signals(slice_df, m_slice, fund_data, sector_name)
            
            # Merge computed raw indicators into day_signals
            day_signals[sym].update(raw_sig)
            
        # 4. Compute composite scores across the universe
        day_results = compute_composite_scores(day_signals)
        
        # Check if entry triggered for any candidate
        for sym, loc_idx in candidates:
            if sym in day_results:
                res = day_results[sym]
                sig = day_signals[sym]
                
                # Check individual criteria
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
                    print(f"  -> SIGNAL TRIGGERED: {date} | {sym} | Total Score: {total_score:.2f} | Vol Ratio: {breakout_vol_ratio:.2f} | Sector: {sig['sector']}")
                    
    # Run Simulator
    print(f"[{run_name}] Running Backtest Portfolio Simulator...")
    engine_df_dict = {sym: df_dict[sym].copy() for sym in df_dict}
    engine = BacktestEngine(initial_capital=1000000.0, time_stop_days=time_stop_days)
    metrics = engine.run(engine_df_dict, signals_dict)
    
    # Save Trade Log
    trade_log_list = metrics.get("trade_log", [])
    if trade_log_list:
        trades_df = pd.DataFrame(trade_log_list)
        output_dir = project_root / "data"
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / f"trade_log_{run_name.lower().replace(' ', '_')}.csv"
        trades_df.to_csv(csv_path, index=False)
        print(f"  Saved {len(trades_df)} trade logs to {csv_path}")
        
        # Default trade_log.csv gets the primary strategy run
        if run_name == "Strategy Backtest":
            trades_df.to_csv(output_dir / "trade_log.csv", index=False)
    else:
        print("  No trades executed.")
        
    return metrics

def main():
    print("=" * 80)
    print(" NSE Momentum Scanner - Historical Backtest Executor ")
    print("=" * 80)
    
    db = SessionLocal()
    
    # 1. Load active symbols
    conn = sqlite3.connect(str(project_root / "data" / "scanner.db"))
    cursor = conn.cursor()
    cursor.execute("SELECT symbol FROM universe_stocks WHERE is_active = 1")
    active_symbols = [r[0] for r in cursor.fetchall()]
    print(f"Loaded {len(active_symbols)} active universe symbols.")
    
    # 2. Load fundamentals
    fundamentals_df = pd.read_sql_query("SELECT * FROM company_fundamentals", conn)
    conn.close()
    
    fundamentals_map = {}
    for _, row in fundamentals_df.iterrows():
        sym = row['symbol']
        fundamentals_map[sym] = {
            "sales_growth_qoq": get_safe_float(row.get('sales_growth_qoq')),
            "sales_growth_yoy": get_safe_float(row.get('sales_growth_yoy')),
            "profit_growth_yoy": get_safe_float(row.get('profit_growth_yoy')),
            "roce": get_safe_float(row.get('roce')),
            "roe": get_safe_float(row.get('roe')),
            "debt_to_equity": get_safe_float(row.get('debt_to_equity'), 999.0),
            "institutional_holding_qoq_change": get_safe_float(row.get('institutional_holding_qoq_change')),
            "sector": row.get('sector', 'Unknown')
        }
        
    # 3. Load all candles
    print("Loading historical candles...")
    candles_query = db.query(DailyCandle).filter(DailyCandle.symbol.in_(active_symbols)).order_by(DailyCandle.date.asc()).all()
    
    # Convert to DataFrame
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
    print(f"Loaded {len(df_all)} daily candles.")
    
    # Group by symbol
    candles_by_symbol = {}
    for sym, group in df_all.groupby('symbol'):
        candles_by_symbol[sym] = group.sort_values('date').reset_index(drop=True)
        
    # 4. Create market average series for RS index
    market_avg = df_all.groupby('date')['close'].mean().reset_index()
    market_avg = market_avg.sort_values('date').reset_index(drop=True)
    
    # Precompute market returns
    market_avg['return_20d'] = market_avg['close'].pct_change(20)
    market_avg['return_50d'] = market_avg['close'].pct_change(50)
    market_avg['return_100d'] = market_avg['close'].pct_change(100)
    market_avg_map = market_avg.set_index('date').to_dict('index')
    
    # 5. Precompute indicator metrics for each symbol
    print("Precalculating metrics...")
    df_dict = {}
    
    for sym in active_symbols:
        if sym not in candles_by_symbol:
            continue
            
        df = candles_by_symbol[sym].copy()
        
        # Calculate breakout candle criteria vectorized
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
        
    # ==========================================================================
    # RUN 1: Strategy Backtest (Real Parameters: score >= 85, time-stop = 30d)
    # ==========================================================================
    metrics_strat = execute_single_backtest_run(
        df_dict=df_dict,
        market_avg_map=market_avg_map,
        market_avg=market_avg,
        active_symbols=active_symbols,
        fundamentals_map=fundamentals_map,
        score_threshold=85.0,
        time_stop_days=30,
        run_name="Strategy Backtest"
    )
    
    # ==========================================================================
    # RUN 2: Mechanism Test (Relaxed Parameters: score >= 60, time-stop = 5d)
    # ==========================================================================
    metrics_mech = execute_single_backtest_run(
        df_dict=df_dict,
        market_avg_map=market_avg_map,
        market_avg=market_avg,
        active_symbols=active_symbols,
        fundamentals_map=fundamentals_map,
        score_threshold=60.0,
        time_stop_days=5,
        run_name="Mechanism Test"
    )
    
    # 6. Output Performance Summaries
    print("\n" + "=" * 50)
    print(" PERFORMANCE SUMMARY: STRATEGY BACKTEST (Real Parameters: 85/30) ")
    print("=" * 50)
    print(f"Total Trades:     {metrics_strat['total_trades']}")
    print(f"Win Rate:         {metrics_strat['win_rate']:.2f}%")
    print(f"Total Profit/Loss: Rs. {metrics_strat['total_pnl']:,.2f}")
    print(f"CAGR:             {metrics_strat['cagr']:.2f}%")
    print(f"Sharpe Ratio:     {metrics_strat['sharpe']:.2f}")
    print(f"Max Drawdown:     {metrics_strat['max_drawdown']:.2f}%")
    print(f"Expectancy:       Rs. {metrics_strat['expectancy']:,.2f}")
    print("=" * 50)
    
    print("\n" + "=" * 50)
    print(" PERFORMANCE SUMMARY: MECHANISM TEST (Relaxed Parameters: 60/5) ")
    print("=" * 50)
    print(f"Total Trades:     {metrics_mech['total_trades']}")
    print(f"Win Rate:         {metrics_mech['win_rate']:.2f}%")
    print(f"Total Profit/Loss: Rs. {metrics_mech['total_pnl']:,.2f}")
    print(f"CAGR:             {metrics_mech['cagr']:.2f}%")
    print(f"Sharpe Ratio:     {metrics_mech['sharpe']:.2f}")
    print(f"Max Drawdown:     {metrics_mech['max_drawdown']:.2f}%")
    print(f"Expectancy:       Rs. {metrics_mech['expectancy']:,.2f}")
    print("=" * 50)
    
    # 7. Print Audit Log for Strategy Run (if trades exist)
    if metrics_strat["total_trades"] > 0:
        trades_df = pd.DataFrame(metrics_strat["trade_log"])
        print("\n" + "=" * 80)
        print(" 10-TRADE AUDIT LOG: STRATEGY BACKTEST (Real Parameters) ")
        print("=" * 80)
        sells_final = trades_df[trades_df['direction'] == 'SELL_FINAL']
        sample_sells = sells_final.head(10)
        
        has_loss = (trades_df['direction'] == 'SELL_FINAL') & (trades_df['pnl'] < 0)
        has_time_stop = (trades_df['direction'] == 'SELL_FINAL') & (trades_df['reason'] == 'Time Stop')
        
        print(f"Sample has loss trade: {trades_df[has_loss]['symbol'].tolist()[:3] if has_loss.any() else 'None'}")
        print(f"Sample has time-stop: {trades_df[has_time_stop]['symbol'].tolist()[:3] if has_time_stop.any() else 'None'}")
        print("-" * 80)
        
        for idx, (_, row) in enumerate(sample_sells.iterrows()):
            sym = row['symbol']
            entry_d = row['entry_date']
            sym_trades = trades_df[(trades_df['symbol'] == sym) & (trades_df['entry_date'] == entry_d)].sort_values('exit_date', na_position='first')
            entry_d_str = entry_d.strftime('%Y-%m-%d') if hasattr(entry_d, 'strftime') else str(entry_d)
            
            print(f"Trade #{idx+1}: {sym}")
            for _, t in sym_trades.iterrows():
                exit_d_str = t['exit_date'].strftime('%Y-%m-%d') if hasattr(t['exit_date'], 'strftime') and pd.notna(t['exit_date']) else str(t['exit_date'])
                if t['direction'] == 'BUY':
                    print(f"  -> BUY  on {entry_d_str}: Price: Rs. {t['entry_price']:.2f} | Qty: {t['qty']}")
                elif t['direction'] == 'SELL_PARTIAL':
                    print(f"  -> PARTIAL SELL on {exit_d_str}: Price: Rs. {t['exit_price']:.2f} | Qty: {t['qty']} | PnL: Rs. {t['pnl']:.2f} | Reason: {t['reason']}")
                elif t['direction'] == 'SELL_FINAL':
                    print(f"  -> FINAL SELL   on {exit_d_str}: Price: Rs. {t['exit_price']:.2f} | Qty: {t['qty']} | PnL: Rs. {t['pnl']:.2f} | Reason: {t['reason']}")
            print("-" * 80)
            
    # 8. Print Audit Log for Mechanism Run
    if metrics_mech["total_trades"] > 0:
        trades_df = pd.DataFrame(metrics_mech["trade_log"])
        print("\n" + "=" * 80)
        print(" 10-TRADE AUDIT LOG: MECHANISM TEST (Relaxed Parameters) ")
        print("=" * 80)
        sells_final = trades_df[trades_df['direction'] == 'SELL_FINAL']
        sample_sells = sells_final.head(10)
        
        has_loss = (trades_df['direction'] == 'SELL_FINAL') & (trades_df['pnl'] < 0)
        has_time_stop = (trades_df['direction'] == 'SELL_FINAL') & (trades_df['reason'] == 'Time Stop')
        
        print(f"Sample has loss trade: {trades_df[has_loss]['symbol'].tolist()[:3] if has_loss.any() else 'None'}")
        print(f"Sample has time-stop: {trades_df[has_time_stop]['symbol'].tolist()[:3] if has_time_stop.any() else 'None'}")
        print("-" * 80)
        
        for idx, (_, row) in enumerate(sample_sells.iterrows()):
            sym = row['symbol']
            entry_d = row['entry_date']
            sym_trades = trades_df[(trades_df['symbol'] == sym) & (trades_df['entry_date'] == entry_d)].sort_values('exit_date', na_position='first')
            entry_d_str = entry_d.strftime('%Y-%m-%d') if hasattr(entry_d, 'strftime') else str(entry_d)
            
            print(f"Trade #{idx+1}: {sym}")
            for _, t in sym_trades.iterrows():
                exit_d_str = t['exit_date'].strftime('%Y-%m-%d') if hasattr(t['exit_date'], 'strftime') and pd.notna(t['exit_date']) else str(t['exit_date'])
                if t['direction'] == 'BUY':
                    print(f"  -> BUY  on {entry_d_str}: Price: Rs. {t['entry_price']:.2f} | Qty: {t['qty']}")
                elif t['direction'] == 'SELL_PARTIAL':
                    print(f"  -> PARTIAL SELL on {exit_d_str}: Price: Rs. {t['exit_price']:.2f} | Qty: {t['qty']} | PnL: Rs. {t['pnl']:.2f} | Reason: {t['reason']}")
                elif t['direction'] == 'SELL_FINAL':
                    print(f"  -> FINAL SELL   on {exit_d_str}: Price: Rs. {t['exit_price']:.2f} | Qty: {t['qty']} | PnL: Rs. {t['pnl']:.2f} | Reason: {t['reason']}")
            print("-" * 80)
            
    db.close()

if __name__ == "__main__":
    main()
