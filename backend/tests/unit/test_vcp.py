import pytest
import pandas as pd
import numpy as np
from app.scanner.vcp import calculate_vcp_score

def create_synthetic_vcp_df(swing_points, first_avg_range=7.0, final_avg_range=1.5, declining_atr=True):
    """
    Helper to construct a DataFrame with exact fractal swing points.
    swing_points: list of (idx, type, price)
    """
    # Sort swing points by index
    swing_points = sorted(swing_points, key=lambda x: x[0])
    
    # We add an offset of 20 to ensure we have enough preceding candles to calculate
    # ATR(10) and baseline volume.
    offset = 20
    shifted_swings = [(idx + offset, t, price) for idx, t, price in swing_points]
    
    n = shifted_swings[-1][0] + 15
    
    close = [0.0] * n
    
    # Prefix close values (slowly rising to first swing high)
    first_idx, _, first_price = shifted_swings[0]
    for i in range(first_idx):
        close[i] = first_price - 5.0 + (i / first_idx) * 4.0

    # Interpolate close between swing points
    for i in range(len(shifted_swings) - 1):
        idx1, _, p1 = shifted_swings[i]
        idx2, _, p2 = shifted_swings[i+1]
        for t in range(idx1, idx2 + 1):
            close[t] = p1 + (t - idx1) / (idx2 - idx1) * (p2 - p1)
            
    # Suffix close values (flat/slightly rising after last low)
    last_idx, _, last_price = shifted_swings[-1]
    for i in range(last_idx + 1, n):
        close[i] = last_price + 0.5 + (i - last_idx) * 0.1

    high = [0.0] * n
    low = [0.0] * n
    
    first_shifted_start = shifted_swings[0][0]
    final_shifted_end = shifted_swings[-1][0]
    
    for i in range(n):
        if i < first_shifted_start:
            range_pct = 10.0 if declining_atr else 1.0
        elif i > final_shifted_end:
            range_pct = 1.0 if declining_atr else 10.0
        else:
            # Interpolate daily range pct
            fraction = (i - first_shifted_start) / (final_shifted_end - first_shifted_start)
            range_pct = first_avg_range + fraction * (final_avg_range - first_avg_range)
            
        high[i] = close[i] * (1.0 + range_pct / 200.0)
        low[i] = close[i] * (1.0 - range_pct / 200.0)

    for idx, t, price in shifted_swings:
        close[idx] = price

    df = pd.DataFrame({
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "volume": [10000] * n
    })
    return df

def test_vcp_valid_3_contractions():
    # Swing High 1: 100.0 (idx 10)
    # Swing Low 1: 70.0 (idx 15) -> 30% contraction
    # Swing High 2: 95.0 (idx 20)
    # Swing Low 2: 76.0 (idx 25) -> 20% contraction (ratio = 20/30 = 0.667 <= 0.75)
    # Swing High 3: 90.0 (idx 30)
    # Swing Low 3: 81.0 (idx 35) -> 10% contraction (ratio = 10/20 = 0.50 <= 0.75)
    # Swing lows: 70.0 -> 76.0 -> 81.0 (higher lows)
    # Daily range: 7.0% in first, 1.5% in final -> tight candles pass
    swing_points = [
        (10, 'high', 100.0),
        (15, 'low', 70.0),
        (20, 'high', 95.0),
        (25, 'low', 76.0),
        (30, 'high', 90.0),
        (35, 'low', 81.0)
    ]
    df = create_synthetic_vcp_df(swing_points, first_avg_range=7.0, final_avg_range=1.5)
    res = calculate_vcp_score(df)
    
    assert res["status"] == "passed"
    assert res["contraction_count"] == 3
    assert res["score"] == 16
    assert res["quality"] == "High"
    assert len(res["contraction_ratios"]) == 2
    assert res["contraction_ratios"][0] == pytest.approx(0.6748, abs=1e-3)
    assert res["contraction_ratios"][1] == pytest.approx(0.5069, abs=1e-3)

def test_vcp_valid_2_contractions():
    # Swing High 1: 100.0 (idx 10)
    # Swing Low 1: 80.0 (idx 15) -> 20% contraction
    # Swing High 2: 90.0 (idx 20)
    # Swing Low 2: 81.0 -> 10% contraction (ratio = 10/20 = 0.50 <= 0.80)
    # Swing lows: 80.0 -> 81.0 (higher lows)
    swing_points = [
        (10, 'high', 100.0),
        (15, 'low', 80.0),
        (20, 'high', 90.0),
        (25, 'low', 81.0)
    ]
    df = create_synthetic_vcp_df(swing_points, first_avg_range=7.0, final_avg_range=1.5)
    res = calculate_vcp_score(df)
    
    assert res["status"] == "passed"
    assert res["contraction_count"] == 2
    assert res["score"] == 10
    assert res["quality"] == "Normal"
    assert res["contraction_ratios"][0] == pytest.approx(0.4870, abs=1e-3)

def test_vcp_valid_4_contractions_elite():
    # Contractions:
    # 1. 100.0 -> 70.0 (30.0%)
    # 2. 90.0 -> 72.0 (20.0%) -> ratio = 20.0 / 30.0 = 0.667 (<= 0.70)
    # 3. 85.0 -> 73.4 (14.0%) -> ratio = 14.0 / 20.0 = 0.70 (<= 0.70)
    # 4. 80.0 -> 74.2 (8.0%) -> ratio = 8.0 / 14.0 = 0.571 (<= 0.70)
    swing_points = [
        (10, 'high', 100.0),
        (13, 'low', 70.0),
        (16, 'high', 90.0),
        (19, 'low', 72.0),
        (22, 'high', 85.0),
        (25, 'low', 73.4),
        (28, 'high', 80.0),
        (31, 'low', 74.2)
    ]
    df = create_synthetic_vcp_df(swing_points, first_avg_range=8.0, final_avg_range=1.5)
    res = calculate_vcp_score(df)
    
    assert res["status"] == "passed"
    assert res["contraction_count"] == 4
    assert res["score"] == 20
    assert res["quality"] == "Elite"
    assert res["contraction_ratios"][0] == pytest.approx(0.6959, abs=1e-3)
    assert res["contraction_ratios"][1] == pytest.approx(0.6915, abs=1e-3)
    assert res["contraction_ratios"][2] == pytest.approx(0.5362, abs=1e-3)

def test_vcp_valid_4_contractions_looser():
    # Contractions:
    # 1. High (154.91) to Low (75.0) -> 51.58% contraction
    # 2. High (140.0) to Low (86.8) -> 38.0% contraction (ratio: 0.737)
    # 3. High (130.0) to Low (92.3) -> 29.0% contraction (ratio: 0.763)
    # 4. High (125.0) to Low (97.02) -> 22.38% contraction (ratio: 0.772)
    # All ratios are <= 0.80 but exceed 0.70.
    # Previously, this qualified for the invented High tier (16 pts).
    # Now, it must correctly fall through to Looser (5 pts).
    swing_points = [
        (10, 'high', 150.0),
        (13, 'low', 75.0),
        (16, 'high', 140.0),
        (19, 'low', 86.8),
        (22, 'high', 130.0),
        (25, 'low', 92.3),
        (28, 'high', 125.0),
        (31, 'low', 97.5)
    ]
    df = create_synthetic_vcp_df(swing_points, first_avg_range=8.0, final_avg_range=1.5)
    
    # Adjust daily ranges to shape ATR such that 3-contraction and 2-contraction
    # subsets fail the ATR decline check, forcing the engine to select the 4-contraction candidate.
    for idx in range(len(df)):
        close_val = df.loc[idx, 'close']
        if idx >= 20 and idx <= 32:
            df.loc[idx, 'high'] = close_val * 1.04
            df.loc[idx, 'low'] = close_val * 0.96
        elif idx >= 33 and idx <= 44:
            df.loc[idx, 'high'] = close_val * 1.006
            df.loc[idx, 'low'] = close_val * 0.994
        elif idx >= 45:
            df.loc[idx, 'high'] = close_val * 1.011
            df.loc[idx, 'low'] = close_val * 0.989

    # Keep swing points exact
    offset = 20
    for s_idx, s_type, s_price in swing_points:
        idx = s_idx + offset
        df.loc[idx, 'close'] = s_price
        df.loc[idx, 'open'] = s_price
        if s_type == 'high':
            df.loc[idx, 'high'] = s_price
        else:
            df.loc[idx, 'low'] = s_price

    res = calculate_vcp_score(df)
    
    assert res["status"] == "passed"
    assert res["contraction_count"] == 4
    assert res["score"] == 5  # Verified correction: formerly 16, now 5
    assert res["quality"] == "Looser"

def test_vcp_higher_lows_failure():
    # Swing lows: 70.0 -> 76.0 -> 70.0 (Failure! Low 3 < Low 2)
    swing_points = [
        (10, 'high', 100.0),
        (15, 'low', 70.0),
        (20, 'high', 95.0),
        (25, 'low', 76.0),
        (30, 'high', 90.0),
        (35, 'low', 70.0)
    ]
    df = create_synthetic_vcp_df(swing_points, first_avg_range=7.0, final_avg_range=1.5)
    res = calculate_vcp_score(df)
    assert res["status"] == "failed"
    assert res["score"] == 0

def test_vcp_contraction_size_failure():
    # Contractions:
    # 1. 100.0 -> 90.0 (10.0%)
    # 2. 95.0 -> 76.0 (20.0%) (Failure! Contraction size expanded)
    swing_points = [
        (10, 'high', 100.0),
        (15, 'low', 90.0),
        (20, 'high', 95.0),
        (25, 'low', 76.0)
    ]
    df = create_synthetic_vcp_df(swing_points, first_avg_range=7.0, final_avg_range=1.5)
    res = calculate_vcp_score(df)
    assert res["status"] == "failed"
    assert res["score"] == 0

def test_vcp_atr_failure():
    # ATR increases across the pattern window (declining_atr = False)
    swing_points = [
        (10, 'high', 100.0),
        (15, 'low', 70.0),
        (20, 'high', 95.0),
        (25, 'low', 76.0),
        (30, 'high', 90.0),
        (35, 'low', 81.0)
    ]
    df = create_synthetic_vcp_df(swing_points, first_avg_range=7.0, final_avg_range=1.5, declining_atr=False)
    res = calculate_vcp_score(df)
    assert res["status"] == "failed"
    assert res["score"] == 0

def test_vcp_tightness_failure():
    # Final contraction range is 4.0% and first is 5.0% (4.0 > 0.5 * 5.0 -> tightness fails)
    swing_points = [
        (10, 'high', 100.0),
        (15, 'low', 70.0),
        (20, 'high', 95.0),
        (25, 'low', 76.0),
        (30, 'high', 90.0),
        (35, 'low', 81.0)
    ]
    df = create_synthetic_vcp_df(swing_points, first_avg_range=5.0, final_avg_range=4.0)
    res = calculate_vcp_score(df)
    assert res["status"] == "failed"
    assert res["score"] == 0

def test_vcp_insufficient_data():
    df = pd.DataFrame({"close": [100.0] * 10})
    res = calculate_vcp_score(df)
    assert res["status"] == "failed"
    assert res["score"] == 0
