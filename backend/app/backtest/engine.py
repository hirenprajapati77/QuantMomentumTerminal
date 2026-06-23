import pandas as pd
import numpy as np
from app.scanner.vcp import calculate_atr

def precalculate_confirmed_swing_lows(df: pd.DataFrame) -> pd.Series:
    """
    Precalculate the most recent confirmed swing low for each day t.
    A swing low at index i requires i+1 and i+2 to be higher, so it is only
    confirmed and tradeable starting at index i+2.
    """
    n = len(df)
    swing_lows_series = pd.Series([np.nan] * n, index=df.index)
    
    # 1. Find all raw fractal swing lows
    raw_lows = []
    for t in range(2, n - 2):
        l_t = df['low'].iloc[t]
        if l_t < df['low'].iloc[t-1] and l_t < df['low'].iloc[t-2] and \
           l_t < df['low'].iloc[t+1] and l_t < df['low'].iloc[t+2]:
            raw_lows.append((t, float(l_t)))
            
    # 2. Keep alternating/zigzag lows (optional, or just use raw fractal lows)
    # The spec says "re-using the exact 5-bar fractal swing-low definition".
    # For trailing stop, the most recent confirmed fractal swing low is sufficient.
    # We populate the series: at each index t, look for the most recent low confirmed at or before t.
    # Since confirmation happens at index i+2, the low at index i is visible at t >= i+2.
    current_low = np.nan
    low_idx_ptr = 0
    
    for t in range(n):
        # Check if any swing low is confirmed at t (meaning its index was t-2)
        # We can scan raw_lows to find the latest low whose index i is <= t-2
        while low_idx_ptr < len(raw_lows) and raw_lows[low_idx_ptr][0] <= t - 2:
            current_low = raw_lows[low_idx_ptr][1]
            low_idx_ptr += 1
        swing_lows_series.iloc[t] = current_low
        
    return swing_lows_series

class BacktestEngine:
    def __init__(self, initial_capital: float = 1000000.0, slippage: float = 0.0015, time_stop_days: int = 30):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.slippage = slippage # 0.15% per side
        self.time_stop_days = time_stop_days

        
        # Positions track:
        # {symbol: {"entry_price": p, "qty": q, "entry_date": d, "holding_days": h, "target1_hit": b, "distribution_days": []}}
        self.positions = {}
        self.trade_log = []
        self.equity_curve = []
        
    def calculate_commission(self, price: float, qty: float, is_buy: bool) -> float:
        """
        Calculate total transaction costs for NSE delivery trade:
        - Slippage: 0.15% of trade value
        - STT: 0.1% of trade value
        - Exchange Transaction Charge: 0.00345%
        - Stamp Duty: 0.015% (Buy only)
        - SEBI Charges: 0.0001%
        - GST: 18% of (Transaction Charge + SEBI Charge)
        """
        val = price * qty
        slippage_cost = val * self.slippage
        stt_cost = val * 0.0010
        exchange_charge = val * 0.0000345
        stamp_duty = val * 0.00015 if is_buy else 0.0
        sebi_charge = val * 0.000001
        gst = (exchange_charge + sebi_charge) * 0.18
        
        return slippage_cost + stt_cost + exchange_charge + stamp_duty + sebi_charge + gst

    def run(self, df_dict: dict[str, pd.DataFrame], signals_dict: dict[str, pd.Series]) -> dict:
        """
        Run backtest simulator.
        df_dict: dict mapping symbol (str) to OHLCV DataFrame
        signals_dict: dict mapping symbol (str) to boolean Series of entry signals (True at index t means trigger entry)
        """
        # Align all dataframes by date
        # Find all unique dates across all dataframes, sort chronologically
        all_dates = set()
        for df in df_dict.values():
            all_dates.update(df.index)
        sorted_dates = sorted(list(all_dates))
        
        # Precalculate indicators for each dataframe to make simulation fast
        indicators = {}
        for sym, df in df_dict.items():
            df = df.copy()
            df['ema21'] = df['close'].ewm(span=21, adjust=False).mean()
            df['sma50'] = df['close'].rolling(50).mean()
            df['sma50_vol'] = df['volume'].rolling(50).mean()
            df['confirmed_swing_low'] = precalculate_confirmed_swing_lows(df)
            indicators[sym] = df
            
        # Daily simulation loop
        for t_idx, date in enumerate(sorted_dates):
            # 1. Update equity curve
            current_equity = self.capital
            for sym, pos in list(self.positions.items()):
                df = indicators[sym]
                if date in df.index:
                    close_price = df.loc[date, 'close']
                    current_equity += close_price * pos['qty']
                else:
                    current_equity += pos['entry_price'] * pos['qty']
            self.equity_curve.append({"date": date, "equity": current_equity})

            # 2. Check exits for open positions on today's bar
            for sym, pos in list(self.positions.items()):
                df = indicators[sym]
                if date not in df.index:
                    continue
                    
                row = df.loc[date]
                o, h, l, c, v = row['open'], row['high'], row['low'], row['close'], row['volume']
                
                # Check if yesterday's row exists to identify distribution days
                # (distribution day needs comparison with yesterday's close/volume)
                is_distribution_day = False
                loc_idx = df.index.get_loc(date)
                if loc_idx > 0:
                    prior_row = df.iloc[loc_idx - 1]
                    prior_c = prior_row['close']
                    prior_v = prior_row['volume']
                    if c < prior_c * 0.985 and v > prior_v: # close down >1.5% and volume > prior volume
                        is_distribution_day = True
                        
                if is_distribution_day:
                    pos['distribution_days'].append(date)

                # Initialize exit flags
                exit_triggered = False
                exit_price = 0.0
                exit_reason = ""
                shares_to_exit = 0.0

                # Priority Exit Cascade (if/elif/elif decision tree)
                # 1. Hard Stop Loss
                stop_level = pos['entry_price'] * 0.94
                if l <= stop_level:
                    exit_triggered = True
                    exit_price = min(o, stop_level) # exit at open if it gapped below stop
                    exit_reason = "Stop Loss"
                    shares_to_exit = pos['qty']
                    
                # 2. Structure Failure
                elif c < row['sma50'] and v > 2.0 * row['sma50_vol']:
                    exit_triggered = True
                    exit_price = c
                    exit_reason = "Structure Failure"
                    shares_to_exit = pos['qty']
                    
                # 3. Distribution Exit
                elif len(pos['distribution_days']) >= 4:
                    # Count rolling distribution days within the last 25 holding days
                    # Since we only count distribution days after entry, we filter:
                    rolling_dist_days = [d for d in pos['distribution_days'] if (df.index.get_loc(date) - df.index.get_loc(d)) < 25]
                    if len(rolling_dist_days) >= 4:
                        exit_triggered = True
                        exit_price = c
                        exit_reason = "Distribution Exit"
                        shares_to_exit = pos['qty']
                        
                # 4. Target 1 (Partial Target)
                elif not pos['target1_hit'] and h >= pos['entry_price'] * 1.10:
                    target1_level = pos['entry_price'] * 1.10
                    fill_price = max(o, target1_level)
                    
                    # Close 50% of the position
                    partial_qty = pos['qty'] * 0.5
                    comm = self.calculate_commission(fill_price, partial_qty, is_buy=False)
                    self.capital += (fill_price * partial_qty) - comm
                    
                    self.trade_log.append({
                        "symbol": sym,
                        "direction": "SELL_PARTIAL",
                        "entry_date": pos['entry_date'],
                        "exit_date": date,
                        "entry_price": pos['entry_price'],
                        "exit_price": fill_price,
                        "qty": partial_qty,
                        "pnl": (fill_price - pos['entry_price']) * partial_qty - comm,
                        "reason": "Target 1"
                    })
                    
                    pos['qty'] -= partial_qty
                    pos['target1_hit'] = True
                    # Stop evaluation for this bar t. Trailing stop is active on bar t+1
                    exit_triggered = False

                # 5. Target 2 (Final Target)
                elif pos['target1_hit'] and h >= pos['entry_price'] * 1.20:
                    target2_level = pos['entry_price'] * 1.20
                    exit_triggered = True
                    exit_price = max(o, target2_level)
                    exit_reason = "Target 2"
                    shares_to_exit = pos['qty']

                # 6. Trailing Stop
                elif pos['target1_hit']:
                    trail_level = row['ema21']
                    if not pd.isna(row['confirmed_swing_low']):
                        trail_level = max(trail_level, row['confirmed_swing_low'])
                        
                    if c < trail_level:
                        exit_triggered = True
                        exit_price = c
                        exit_reason = "Trailing Stop"
                        shares_to_exit = pos['qty']

                # 7. Time Stop
                elif pos['holding_days'] >= self.time_stop_days:
                    exit_triggered = True
                    exit_price = c
                    exit_reason = "Time Stop"
                    shares_to_exit = pos['qty']

                # Execute full/remaining exit if triggered
                if exit_triggered:
                    comm = self.calculate_commission(exit_price, shares_to_exit, is_buy=False)
                    self.capital += (exit_price * shares_to_exit) - comm
                    
                    self.trade_log.append({
                        "symbol": sym,
                        "direction": "SELL_FINAL",
                        "entry_date": pos['entry_date'],
                        "exit_date": date,
                        "entry_price": pos['entry_price'],
                        "exit_price": exit_price,
                        "qty": shares_to_exit,
                        "pnl": (exit_price - pos['entry_price']) * shares_to_exit - comm,
                        "reason": exit_reason
                    })
                    del self.positions[sym]
                else:
                    # Update holding days counter
                    pos['holding_days'] += 1

            # 3. Check entries (signals generated on yesterday's bar t-1)
            # Allocate equal sizing of 10% of portfolio value per trade
            max_positions = 5
            trade_allocation = self.capital * 0.20 # 20% of capital per position
            
            for sym, signals in signals_dict.items():
                if sym in self.positions or len(self.positions) >= max_positions:
                    continue
                    
                df = indicators[sym]
                if date not in df.index:
                    continue
                    
                # We need to check if a buy signal was triggered yesterday
                loc_idx = df.index.get_loc(date)
                if loc_idx == 0:
                    continue
                    
                prior_date = df.index[loc_idx - 1]
                if prior_date in signals.index and signals.loc[prior_date] == True:
                    # Trigger entry today at Open price
                    o_price = df.loc[date, 'open']
                    
                    # Compute quantity based on allocation
                    qty = np.floor(trade_allocation / o_price)
                    if qty > 0:
                        comm = self.calculate_commission(o_price, qty, is_buy=True)
                        if self.capital >= (o_price * qty) + comm:
                            self.capital -= (o_price * qty) + comm
                            self.positions[sym] = {
                                "entry_price": o_price,
                                "qty": qty,
                                "entry_date": date,
                                "holding_days": 1,
                                "target1_hit": False,
                                "distribution_days": []
                            }
                            
                            self.trade_log.append({
                                "symbol": sym,
                                "direction": "BUY",
                                "entry_date": date,
                                "exit_date": None,
                                "entry_price": o_price,
                                "exit_price": 0.0,
                                "qty": qty,
                                "pnl": 0.0,
                                "reason": "Signal"
                            })

        return self.generate_metrics()

    def generate_metrics(self) -> dict:
        """
        Aggregate trade logs to generate performance statistics.
        """
        trades_df = pd.DataFrame(self.trade_log)
        if trades_df.empty:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "cagr": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
                "expectancy": 0.0
            }

        # Sells final represent closed trades P&L
        closed_trades = trades_df[trades_df['direction'] == 'SELL_FINAL']
        # We need to map partial exits back to compute exact trade P&L
        # Let's group trade P&L by symbol and entry_date
        pnl_by_trade = trades_df.groupby(['symbol', 'entry_date'])['pnl'].sum().reset_index()
        total_pnl = pnl_by_trade['pnl'].sum()
        
        wins = pnl_by_trade[pnl_by_trade['pnl'] > 0]
        win_rate = len(wins) / len(pnl_by_trade) * 100 if len(pnl_by_trade) > 0 else 0.0
        
        expectancy = pnl_by_trade['pnl'].mean() if len(pnl_by_trade) > 0 else 0.0

        # Calculate CAGR and Sharpe based on equity curve
        eq_df = pd.DataFrame(self.equity_curve)
        cagr = 0.0
        sharpe = 0.0
        max_dd = 0.0
        
        if not eq_df.empty:
            final_eq = eq_df['equity'].iloc[-1]
            start_eq = self.initial_capital
            
            # Holding period in years
            days = len(eq_df)
            years = days / 252.0 if days > 0 else 1.0
            cagr = ((final_eq / start_eq) ** (1.0 / years) - 1.0) * 100 if start_eq > 0 else 0.0
            
            # Daily returns for Sharpe
            eq_df['daily_ret'] = eq_df['equity'].pct_change()
            daily_std = eq_df['daily_ret'].std()
            daily_mean = eq_df['daily_ret'].mean()
            # Risk free rate assumed to be 6% per annum (daily = 6% / 252)
            rf_daily = 0.06 / 252
            
            if daily_std > 0:
                sharpe = (daily_mean - rf_daily) / daily_std * np.sqrt(252)
            else:
                sharpe = 0.0

            # Calculate Max Drawdown
            eq_df['peak'] = eq_df['equity'].cummax()
            eq_df['dd'] = (eq_df['equity'] - eq_df['peak']) / eq_df['peak'] * 100
            max_dd = float(eq_df['dd'].min())

        return {
            "total_trades": len(pnl_by_trade),
            "win_rate": float(win_rate),
            "total_pnl": float(total_pnl),
            "cagr": float(cagr),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_dd),
            "expectancy": float(expectancy),
            "trade_log": self.trade_log,
            "equity_curve": self.equity_curve
        }
