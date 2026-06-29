import pytest
import pandas as pd
import numpy as np
from app.analytics.composite import compute_composite_scores
from app.backtest.engine import BacktestEngine, precalculate_confirmed_swing_lows

def test_composite_scoring_and_entry_triggers():
    # 1. Test when all conditions align -> entry_triggered is True
    universe_signals = {
        "TEST_SYM": {
            "sector": "IT",
            "return_20d": 0.10,
            "trend": {"score": 15, "status": "passed"},
            "vcp": {"score": 20, "status": "passed", "start_idx": 10, "end_idx": 40},
            "vdu": {"score": 15},
            "rs_raw": {"rel_20": 0.05, "rel_50": 0.10, "rel_100": 0.15},
            "volume": {"score": 10, "ratio": 2.5},
            "breakout": {"score": 10, "close_pct_of_range": 0.90, "upper_wick_pct": 0.05},
            "cpr": {"score": 5},
            "fundamental": {"score": 10, "passes_gate": True}
        }
    }
    
    # We need to construct universe inputs to get RS score and Sector score of 5
    # Since rs_scores and sector_scores are computed inside compute_composite_scores,
    # let's provide a single-symbol universe where it defaults to top rank, or multiple.
    # In compute_composite_scores:
    # score_sectors will rank sectors. With 1 stock, ratio is 1/1 = 1.0, which gives sector score 0 (since ratio > 0.40).
    # To get sector score 5, we need at least 5 different sectors or we can add dummy stocks to force ranking.
    # Let's add dummy stocks to make sure "TEST_SYM" ends up in top 20% of sectors and has top RS score.
    
    # Let's create a universe with 5 stocks in different sectors to test the ranking logic
    universe_signals = {
        "SYM_1": { # Top sector, top RS
            "sector": "SEC_1",
            "return_20d": 0.50,
            "trend": {"score": 15, "status": "passed"},
            "vcp": {"score": 20, "status": "passed", "start_idx": 10, "end_idx": 40},
            "vdu": {"score": 15},
            "rs_raw": {"rel_20": 0.50, "rel_50": 0.50, "rel_100": 0.50},
            "volume": {"score": 10, "ratio": 3.0},
            "breakout": {"score": 10, "close_pct_of_range": 0.95, "upper_wick_pct": 0.02},
            "cpr": {"score": 5},
            "fundamental": {"score": 10, "passes_gate": True}
        },
        "SYM_2": {
            "sector": "SEC_2",
            "return_20d": 0.30,
            "trend": {"score": 15, "status": "passed"},
            "vcp": {"score": 20, "status": "passed", "start_idx": 10, "end_idx": 40},
            "vdu": {"score": 15},
            "rs_raw": {"rel_20": 0.30, "rel_50": 0.30, "rel_100": 0.30},
            "volume": {"score": 10, "ratio": 1.5}, # fails volume ratio
            "breakout": {"score": 10, "close_pct_of_range": 0.90, "upper_wick_pct": 0.05},
            "cpr": {"score": 5},
            "fundamental": {"score": 10, "passes_gate": True}
        },
        "SYM_3": {
            "sector": "SEC_3",
            "return_20d": 0.20,
            "trend": {"score": 15, "status": "passed"},
            "vcp": {"score": 20, "status": "passed", "start_idx": 10, "end_idx": 40},
            "vdu": {"score": 15},
            "rs_raw": {"rel_20": 0.20, "rel_50": 0.20, "rel_100": 0.20},
            "volume": {"score": 10, "ratio": 2.5},
            "breakout": {"score": 10, "close_pct_of_range": 0.50, "upper_wick_pct": 0.30}, # fails breakout close_pct
            "cpr": {"score": 5},
            "fundamental": {"score": 10, "passes_gate": True}
        },
        "SYM_4": {
            "sector": "SEC_4",
            "return_20d": 0.10,
            "trend": {"score": 0, "status": "failed"}, # fails trend status
            "vcp": {"score": 20, "status": "passed", "start_idx": 10, "end_idx": 40},
            "vdu": {"score": 15},
            "rs_raw": {"rel_20": 0.10, "rel_50": 0.10, "rel_100": 0.10},
            "volume": {"score": 10, "ratio": 2.5},
            "breakout": {"score": 10, "close_pct_of_range": 0.90, "upper_wick_pct": 0.05},
            "cpr": {"score": 5},
            "fundamental": {"score": 10, "passes_gate": True}
        },
        "SYM_5": {
            "sector": "SEC_5",
            "return_20d": 0.05,
            "trend": {"score": 15, "status": "passed"},
            "vcp": {"score": 20, "status": "passed", "start_idx": 10, "end_idx": 40},
            "vdu": {"score": 15},
            "rs_raw": {"rel_20": 0.05, "rel_50": 0.05, "rel_100": 0.05},
            "volume": {"score": 10, "ratio": 2.5},
            "breakout": {"score": 10, "close_pct_of_range": 0.90, "upper_wick_pct": 0.05},
            "cpr": {"score": 5},
            "fundamental": {"score": 10, "passes_gate": False} # fails fundamental gate (should cap grade to Watch, and total score might be high but grade is Watch)
        }
    }
    
    results = compute_composite_scores(universe_signals)
    
    # SYM_1 should trigger entry because:
    # 1. Total score is 100 >= 85
    # 2. breakout_vol_ratio = 3.0 >= 2.0
    # 3. trend_status is passed
    # 4. SEC_1 is top sector (return 0.50, rank 1 of 5 -> ratio 0.20 -> score 5)
    # 5. close_pct_of_range = 0.95 >= 0.85 and upper_wick_pct = 0.02 <= 0.15
    assert results["SYM_1"]["entry_triggered"] is True
    assert results["SYM_1"]["grade"] == "Elite"
    
    # SYM_2 fails because breakout_vol_ratio = 1.5 < 2.0
    assert results["SYM_2"]["entry_triggered"] is False
    
    # SYM_3 fails because close_pct_of_range = 0.50 < 0.85 and upper_wick_pct = 0.30 > 0.15
    assert results["SYM_3"]["entry_triggered"] is False
    
    # SYM_4 fails because trend_status is failed
    assert results["SYM_4"]["entry_triggered"] is False
    
    # SYM_5 fails because it is in SEC_5 which has score 0 (ratio 5/5 = 1.0 > 0.40), plus fundamental passes_gate is False so grade capped at Watch
    assert results["SYM_5"]["entry_triggered"] is False
    assert results["SYM_5"]["grade"] == "Watch"


def test_fundamental_gate_blocks_entry():
    # Setup a 5-stock universe to ensure SYM_1 ranks in the top sector and top RS (scoring 100 technically),
    # but fails the fundamental gate (passes_gate = False).
    # Under the old buggy code, entry_triggered would be True.
    # After the fix, entry_triggered must be False and grade capped at Watch.
    universe_signals = {
        "SYM_1": { # Top sector, top RS, passes all technicals, but fails fundamental gate
            "sector": "SEC_1",
            "return_20d": 0.50,
            "trend": {"score": 15, "status": "passed"},
            "vcp": {"score": 20, "status": "passed", "start_idx": 10, "end_idx": 40},
            "vdu": {"score": 15},
            "rs_raw": {"rel_20": 0.50, "rel_50": 0.50, "rel_100": 0.50},
            "volume": {"score": 10, "ratio": 3.0},
            "breakout": {"score": 10, "close_pct_of_range": 0.95, "upper_wick_pct": 0.02},
            "cpr": {"score": 5},
            "fundamental": {"score": 0, "passes_gate": False} # Fails gate (score = 0 in production when gate fails)
        },
        "SYM_2": {
            "sector": "SEC_2",
            "return_20d": 0.30,
            "trend": {"score": 15, "status": "passed"},
            "vcp": {"score": 20, "status": "passed", "start_idx": 10, "end_idx": 40},
            "vdu": {"score": 15},
            "rs_raw": {"rel_20": 0.30, "rel_50": 0.30, "rel_100": 0.30},
            "volume": {"score": 10, "ratio": 2.5},
            "breakout": {"score": 10, "close_pct_of_range": 0.90, "upper_wick_pct": 0.05},
            "cpr": {"score": 5},
            "fundamental": {"score": 10, "passes_gate": True}
        },
        "SYM_3": {
            "sector": "SEC_3",
            "return_20d": 0.20,
            "trend": {"score": 15, "status": "passed"},
            "vcp": {"score": 20, "status": "passed", "start_idx": 10, "end_idx": 40},
            "vdu": {"score": 15},
            "rs_raw": {"rel_20": 0.20, "rel_50": 0.20, "rel_100": 0.20},
            "volume": {"score": 10, "ratio": 2.5},
            "breakout": {"score": 10, "close_pct_of_range": 0.90, "upper_wick_pct": 0.05},
            "cpr": {"score": 5},
            "fundamental": {"score": 10, "passes_gate": True}
        },
        "SYM_4": {
            "sector": "SEC_4",
            "return_20d": 0.10,
            "trend": {"score": 15, "status": "passed"},
            "vcp": {"score": 20, "status": "passed", "start_idx": 10, "end_idx": 40},
            "vdu": {"score": 15},
            "rs_raw": {"rel_20": 0.10, "rel_50": 0.10, "rel_100": 0.10},
            "volume": {"score": 10, "ratio": 2.5},
            "breakout": {"score": 10, "close_pct_of_range": 0.90, "upper_wick_pct": 0.05},
            "cpr": {"score": 5},
            "fundamental": {"score": 10, "passes_gate": True}
        },
        "SYM_5": {
            "sector": "SEC_5",
            "return_20d": 0.05,
            "trend": {"score": 15, "status": "passed"},
            "vcp": {"score": 20, "status": "passed", "start_idx": 10, "end_idx": 40},
            "vdu": {"score": 15},
            "rs_raw": {"rel_20": 0.05, "rel_50": 0.05, "rel_100": 0.05},
            "volume": {"score": 10, "ratio": 2.5},
            "breakout": {"score": 10, "close_pct_of_range": 0.90, "upper_wick_pct": 0.05},
            "cpr": {"score": 5},
            "fundamental": {"score": 10, "passes_gate": True}
        }
    }
    
    results = compute_composite_scores(universe_signals)
    
    assert results["SYM_1"]["grade"] == "Watch"  # Capped due to fundamental gate
    assert results["SYM_1"]["entry_triggered"] is False  # Blocked by fundamental gate


def create_base_df(n_rows=70, base_price=100.0, base_vol=10000.0):
    """Helper to create a standard DataFrame with flat prices and volume."""
    dates = pd.date_range(start="2026-01-01", periods=n_rows, freq="D")
    df = pd.DataFrame({
        "open": [base_price] * n_rows,
        "high": [base_price] * n_rows,
        "low": [base_price] * n_rows,
        "close": [base_price] * n_rows,
        "volume": [base_vol] * n_rows
    }, index=dates)
    return df


def test_backtest_stop_loss():
    # Setup flat data, trigger buy on day 49, enter at open of day 50 (price 100.0).
    # On day 51, price drops below 94.0.
    df = create_base_df(60)
    # Day 51: low spikes down to 93.0
    df.loc[df.index[51], "low"] = 93.0
    df.loc[df.index[51], "close"] = 95.0
    
    signals = pd.Series([False] * len(df), index=df.index)
    signals.iloc[49] = True # buy signal triggered at t-1 (day 49) -> enter on day 50
    
    engine = BacktestEngine(initial_capital=100000.0)
    res = engine.run({"TEST": df}, {"TEST": signals})
    
    # Check that trade log contains buy and sell
    trade_log = res["trade_log"]
    assert len(trade_log) == 2
    assert trade_log[0]["direction"] == "BUY"
    assert trade_log[1]["direction"] == "SELL_FINAL"
    assert trade_log[1]["reason"] == "Stop Loss"
    assert trade_log[1]["exit_price"] == 94.0 # entry * 0.94


def test_backtest_structure_failure():
    # Close < 50-DMA on volume > 2 * 50-DMA volume
    df = create_base_df(60)
    # Day 51: Close drops to 95.0 (SMA50 is 100.0) and volume spikes to 25000 (SMA50_vol is 10000)
    df.loc[df.index[51], "close"] = 95.0
    df.loc[df.index[51], "volume"] = 25000
    
    signals = pd.Series([False] * len(df), index=df.index)
    signals.iloc[49] = True
    
    engine = BacktestEngine(initial_capital=100000.0)
    res = engine.run({"TEST": df}, {"TEST": signals})
    
    trade_log = res["trade_log"]
    assert len(trade_log) == 2
    assert trade_log[1]["direction"] == "SELL_FINAL"
    assert trade_log[1]["reason"] == "Structure Failure"
    assert trade_log[1]["exit_price"] == 95.0


def test_backtest_distribution_exit():
    # 4 distribution days within rolling 25 holding days.
    # A distribution day = Close down > 1.5% and volume > prior volume.
    df = create_base_df(60)
    
    # Setup distribution days at days 51, 52, 53, 54
    # Day 51: Close down 2% from 100 -> 98.0, Vol = 15000
    df.loc[df.index[51], "close"] = 98.0
    df.loc[df.index[51], "volume"] = 15000
    
    # Day 52: Close down 2% from 98 -> 96.0, Vol = 16000
    df.loc[df.index[52], "close"] = 96.0
    df.loc[df.index[52], "volume"] = 16000
    
    # Day 53: Close down 2% from 96 -> 94.0, Vol = 17000
    df.loc[df.index[53], "close"] = 94.0
    df.loc[df.index[53], "volume"] = 17000
    
    # Day 54: Close down 2% from 94 -> 92.0, Vol = 18000
    df.loc[df.index[54], "close"] = 92.0
    df.loc[df.index[54], "volume"] = 18000
    
    signals = pd.Series([False] * len(df), index=df.index)
    signals.iloc[49] = True
    
    engine = BacktestEngine(initial_capital=100000.0)
    res = engine.run({"TEST": df}, {"TEST": signals})
    
    trade_log = res["trade_log"]
    assert len(trade_log) == 2
    assert trade_log[1]["direction"] == "SELL_FINAL"
    assert trade_log[1]["reason"] == "Distribution Exit"
    assert trade_log[1]["exit_price"] == 92.0


def test_backtest_target1_and_target2():
    df = create_base_df(60)
    # Day 51: High spikes to 111.0 (>= 110.0 Target 1)
    df.loc[df.index[51], "high"] = 111.0
    # Day 52: High spikes to 121.0 (>= 120.0 Target 2)
    df.loc[df.index[52], "high"] = 121.0
    
    signals = pd.Series([False] * len(df), index=df.index)
    signals.iloc[49] = True
    
    engine = BacktestEngine(initial_capital=100000.0)
    res = engine.run({"TEST": df}, {"TEST": signals})
    
    trade_log = res["trade_log"]
    assert len(trade_log) == 3 # BUY, SELL_PARTIAL, SELL_FINAL
    assert trade_log[1]["direction"] == "SELL_PARTIAL"
    assert trade_log[1]["reason"] == "Target 1"
    assert trade_log[1]["exit_price"] == pytest.approx(110.0)
    
    assert trade_log[2]["direction"] == "SELL_FINAL"
    assert trade_log[2]["reason"] == "Target 2"
    assert trade_log[2]["exit_price"] == pytest.approx(120.0)



def test_backtest_trailing_stop():
    df = create_base_df(65)
    # Day 51: Hit Target 1
    df.loc[df.index[51], "high"] = 111.0
    # Day 52: Close drops below EMA21 (which is 100.0)
    df.loc[df.index[52], "close"] = 99.0
    
    signals = pd.Series([False] * len(df), index=df.index)
    signals.iloc[49] = True
    
    engine = BacktestEngine(initial_capital=100000.0)
    res = engine.run({"TEST": df}, {"TEST": signals})
    
    trade_log = res["trade_log"]
    assert len(trade_log) == 3
    assert trade_log[1]["direction"] == "SELL_PARTIAL"
    assert trade_log[2]["direction"] == "SELL_FINAL"
    assert trade_log[2]["reason"] == "Trailing Stop"
    assert trade_log[2]["exit_price"] == 99.0


def test_backtest_time_stop():
    # Ensure position is held 30 days without any trigger
    df = create_base_df(90)
    
    signals = pd.Series([False] * len(df), index=df.index)
    signals.iloc[49] = True
    
    engine = BacktestEngine(initial_capital=100000.0)
    res = engine.run({"TEST": df}, {"TEST": signals})
    
    trade_log = res["trade_log"]
    assert len(trade_log) == 2
    assert trade_log[1]["direction"] == "SELL_FINAL"
    assert trade_log[1]["reason"] == "Time Stop"
    # Entry on day 50. Exit on day 80 (since holding_days reaches 30 on day 80's exit check).
    # Day 50 (holding_days=1 after day-end increment? No, entry has holding_days=1, day 51 increment to 2, etc.)
    # Let's verify that the exit date is day 80 (which is exactly index 80).
    assert trade_log[1]["exit_date"] == df.index[80]



def test_backtest_exit_priority():
    # If both Stop Loss and Target 1 are hit on the same bar, Stop Loss should trigger.
    df = create_base_df(60)
    # Day 51: Low is 93.0 (Stop Loss) and High is 111.0 (Target 1)
    df.loc[df.index[51], "low"] = 93.0
    df.loc[df.index[51], "high"] = 111.0
    
    signals = pd.Series([False] * len(df), index=df.index)
    signals.iloc[49] = True
    
    engine = BacktestEngine(initial_capital=100000.0)
    res = engine.run({"TEST": df}, {"TEST": signals})
    
    trade_log = res["trade_log"]
    assert len(trade_log) == 2
    assert trade_log[1]["direction"] == "SELL_FINAL"
    assert trade_log[1]["reason"] == "Stop Loss"
    assert trade_log[1]["exit_price"] == 94.0
