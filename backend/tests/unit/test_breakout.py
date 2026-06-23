import pytest
import pandas as pd
from app.scanner.breakout import calculate_breakout_quality

def create_synthetic_breakout_df(prior_close, today_open, today_high, today_low, today_close, today_vol=10000, ma50_vol=10000):
    # Construct a DataFrame of length 51 so that MA50_vol is calculated correctly
    # Today's values are at index -1
    # Prior values are at index -2
    n = 51
    vols = [ma50_vol] * n
    vols[-1] = today_vol
    
    closes = [prior_close] * n
    closes[-1] = today_close
    
    highs = [prior_close + 1.0] * n
    highs[-1] = today_high
    
    lows = [prior_close - 1.0] * n
    lows[-1] = today_low
    
    opens = [prior_close] * n
    opens[-1] = today_open
    
    df = pd.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": vols
    })
    return df

def test_breakout_quality_high_close_and_gap():
    # Case 2.6.A: Prior Close = 100.0, Open = 103.5, High = 110.0, Low = 103.0, Close = 109.0
    # Today volume = 25000, MA50 volume = 10000 -> today_vol > 2 * ma50_vol holds
    # Calculations:
    #   close_pct = 6/7 = 0.85714285...
    #   upper_wick = 1/7 = 0.14285714...
    #   base = 10 * (6/7) * (6/7) = 360/49 = 7.3469387...
    #   gap = 3.5% (>3%) -> bonus = 2.0
    #   total = min(10.0, 7.3469387... + 2.0) = 9.3469387...
    df = create_synthetic_breakout_df(
        prior_close=100.0,
        today_open=103.5,
        today_high=110.0,
        today_low=103.0,
        today_close=109.0,
        today_vol=25000,
        ma50_vol=10000
    )
    res = calculate_breakout_quality(df)
    assert res["score"] == pytest.approx(9.3469, abs=1e-4)
    assert res["base_score"] == pytest.approx(7.3469, abs=1e-4)
    assert res["gap_bonus"] == 2.0
    assert res["close_pct_of_range"] == pytest.approx(6.0/7.0, abs=1e-6)
    assert res["upper_wick_pct"] == pytest.approx(1.0/7.0, abs=1e-6)

def test_breakout_quality_perfect():
    # Closed at absolute high, no wicks, no gap
    df = create_synthetic_breakout_df(
        prior_close=100.0,
        today_open=100.0,
        today_high=110.0,
        today_low=100.0,
        today_close=110.0
    )
    res = calculate_breakout_quality(df)
    assert res["score"] == pytest.approx(10.0, abs=1e-4)
    assert res["base_score"] == pytest.approx(10.0, abs=1e-4)
    assert res["gap_bonus"] == 0.0

def test_breakout_quality_flat_line():
    # high == low, should handle division by zero safely
    df = create_synthetic_breakout_df(
        prior_close=100.0,
        today_open=100.0,
        today_high=100.0,
        today_low=100.0,
        today_close=100.0
    )
    res = calculate_breakout_quality(df)
    assert res["score"] == 0.0
    assert res["base_score"] == 0.0

def test_breakout_quality_gap_bonus_no_volume():
    # Gap > 3% but volume <= 2 * SMA50 -> no gap bonus
    df = create_synthetic_breakout_df(
        prior_close=100.0,
        today_open=105.0,
        today_high=110.0,
        today_low=105.0,
        today_close=110.0,
        today_vol=15000,
        ma50_vol=10000
    )
    res = calculate_breakout_quality(df)
    assert res["base_score"] == pytest.approx(10.0, abs=1e-4)
    assert res["gap_bonus"] == 0.0  # Vol is 1.5x MA, not >2x
    assert res["score"] == pytest.approx(10.0, abs=1e-4)

def test_breakout_quality_cap():
    # base = 9.0, gap = 2.0 -> total capped at 10.0
    df = create_synthetic_breakout_df(
        prior_close=100.0,
        today_open=104.0,
        today_high=110.0,
        today_low=100.0,
        today_close=109.0,
        today_vol=25000,
        ma50_vol=10000
    )
    res = calculate_breakout_quality(df)
    # close_pct = 9/10 = 0.90
    # upper_wick = 1/10 = 0.10
    # base = 10 * 0.90 * (1 - 0.10) = 8.10
    # gap_bonus = 2.0
    # total capped at 10.0
    assert res["base_score"] == pytest.approx(8.10, abs=1e-4)
    assert res["gap_bonus"] == 2.0
    assert res["score"] == 10.0

def test_breakout_quality_zero_base():
    # closed at low -> close_pct = 0.0 -> score = 0.0
    df = create_synthetic_breakout_df(
        prior_close=100.0,
        today_open=105.0,
        today_high=110.0,
        today_low=100.0,
        today_close=100.0
    )
    res = calculate_breakout_quality(df)
    assert res["score"] == 0.0
    assert res["base_score"] == 0.0

def test_breakout_quality_no_prior_close():
    df = pd.DataFrame({"close": [100.0]})
    res = calculate_breakout_quality(df)
    assert res["score"] == 0.0

def test_breakout_quality_moderate_wick():
    # close_pct = 0.90, upper_wick = 0.10 -> base_score = 8.10
    df = create_synthetic_breakout_df(
        prior_close=100.0,
        today_open=102.0,
        today_high=110.0,
        today_low=100.0,
        today_close=109.0
    )
    res = calculate_breakout_quality(df)
    assert res["base_score"] == pytest.approx(8.10, abs=1e-4)
