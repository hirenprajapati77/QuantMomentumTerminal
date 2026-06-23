import pytest
import pandas as pd
import numpy as np
from app.scanner.cpr import calculate_cpr_score

def create_synthetic_cpr_df(today_high, today_low, today_close, trailing_widths=None, length=100):
    # Construct a historical DataFrame.
    # Today's levels are based on yesterday's candle, so we inject the test levels
    # on the second-to-last row (yesterday) and also on the last row (today).
    
    if trailing_widths is None:
        # Default trailing widths: a uniform list of width percents from 1.0% to 5.0%
        # We need length - 2 historical widths since we append two test rows at the end
        trailing_widths = list(np.linspace(1.0, 5.0, length - 2))

    highs = []
    lows = []
    closes = []
    
    for w in trailing_widths:
        highs.append(100.0)
        lows.append(100.0 - w)
        closes.append(100.0 + w)

    # Add yesterday's row (which determines today's CPR width and pivots)
    highs.append(today_high)
    lows.append(today_low)
    closes.append(today_close)

    # Add today's row (where today's close is compared against TC)
    highs.append(today_high)
    lows.append(today_low)
    closes.append(today_close)

    df = pd.DataFrame({
        "high": highs,
        "low": lows,
        "close": closes
    })
    return df


def test_cpr_narrow_price_above():
    # Case 2.8.A: Today's High=105.0, Low=95.0, Close=102.0
    # Pivot = 100.667, bc = 100.0, tc = 101.334, width_pct = 1.325%
    # Trailing widths average = 2.5%, 30th percentile = 2.2% -> Narrow = True, price is above tc (102.0 > 101.334) -> 5 pts
    # Let's set trailing widths from 1.0 to 5.0 (99 values).
    # Quantiles of [1.0 ... 5.0] (uniformly distributed):
    #   30th percentile is 1.0 + 0.3 * 4.0 = 2.2%
    #   Today's width is 1.325% which is <= 2.2% -> Narrow.
    #   Average of [1.0...5.0] is 3.0%. Today's width is 1.325% <= 3.0% -> Not expanding.
    df = create_synthetic_cpr_df(today_high=105.0, today_low=95.0, today_close=102.0)
    res = calculate_cpr_score(df)
    
    assert res["score"] == 5
    assert res["status"] == "passed"
    assert res["is_narrow"] is True
    assert res["is_expanding"] is False
    assert res["pivot"] == pytest.approx(100.6667, abs=1e-4)
    assert res["bc"] == pytest.approx(100.0, abs=1e-4)
    assert res["tc"] == pytest.approx(101.3333, abs=1e-4)
    assert res["cpr_width_pct"] == pytest.approx(1.3245, abs=1e-3)

def test_cpr_narrow_price_below():
    # Today's Close = 99.5, High = 105.0, Low = 95.0
    # Pivot = 299.5 / 3 = 99.833
    # bc = 100.0
    # tc = 99.667
    # Close = 99.5 < tc (99.667) -> price inside/below -> 2 pts
    df = create_synthetic_cpr_df(today_high=105.0, today_low=95.0, today_close=99.5)
    res = calculate_cpr_score(df)
    assert res["score"] == 2
    assert res["status"] == "passed"
    assert res["is_narrow"] is True

def test_cpr_expanding_reject():
    # Today's width is 4.5% which is larger than average 3.0% -> expanding -> reject (0 pts, failed)
    # Today: High = 106.0, Low = 94.0, Close = 100.0
    # Pivot = 100.0, bc = 100.0, tc = 100.0, width = 0%? No.
    # Today: High = 104.5, Low = 100.0, Close = 95.5
    # Pivot = 300.0 / 3 = 100.0
    # bc = 102.25
    # tc = 97.75
    # Width = |97.75 - 102.25| / 100 * 100 = 4.50% (Expanding)
    df = create_synthetic_cpr_df(today_high=104.5, today_low=100.0, today_close=95.5)
    res = calculate_cpr_score(df)
    assert res["score"] == 0
    assert res["status"] == "failed"
    assert res["is_expanding"] is True

def test_cpr_normal_pass():
    # Today's width is 2.5% (between 30th percentile 2.2% and average 3.0%) -> 0 pts, passed
    # Today: High = 102.5, Low = 100.0, Close = 97.5
    # Pivot = 300.0 / 3 = 100.0
    # bc = 101.25
    # tc = 98.75
    # Width = 2.50%
    df = create_synthetic_cpr_df(today_high=102.5, today_low=100.0, today_close=97.5)
    res = calculate_cpr_score(df)
    assert res["score"] == 0
    assert res["status"] == "passed"
    assert res["is_narrow"] is False
    assert res["is_expanding"] is False

def test_cpr_insufficient_data():
    df = pd.DataFrame({"high": [105.0] * 50, "low": [95.0] * 50, "close": [100.0] * 50})
    res = calculate_cpr_score(df)
    assert res["score"] == 0
    assert res["status"] == "failed"

def test_cpr_calculations_exact():
    # Verify exact math output
    df = create_synthetic_cpr_df(today_high=105.0, today_low=95.0, today_close=100.0)
    res = calculate_cpr_score(df)
    assert res["pivot"] == pytest.approx(100.0, abs=1e-6)
    assert res["bc"] == pytest.approx(100.0, abs=1e-6)
    assert res["tc"] == pytest.approx(100.0, abs=1e-6)
    assert res["cpr_width_pct"] == 0.0

def test_cpr_exactly_hundred_days():
    df = create_synthetic_cpr_df(today_high=105.0, today_low=95.0, today_close=102.0, length=100)
    res = calculate_cpr_score(df)
    assert res["status"] in ["passed", "failed"]

def test_cpr_width_is_zero():
    # high == low == close
    df = create_synthetic_cpr_df(today_high=100.0, today_low=100.0, today_close=100.0)
    res = calculate_cpr_score(df)
    assert res["cpr_width_pct"] == 0.0
