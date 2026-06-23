import pytest
import pandas as pd
from app.scanner.trend import calculate_trend_score

def create_synthetic_trend_df(close_val, sma_50_val, sma_150_val, sma_200_val, length=200):
    """Helper to construct a DataFrame with specific rolling average values on the last day."""
    # We will build a series of Close values of length `length`.
    # To set the SMA(50), SMA(150), and SMA(200) to exact values on the last day:
    # Let's populate the close array such that:
    # - The last value is close_val
    # - The sum of last 50 close values is 50 * sma_50_val
    # - The sum of last 150 close values is 150 * sma_150_val
    # - The sum of last 200 close values is 200 * sma_200_val
    closes = [100.0] * length
    
    # Set values in blocks
    # Last value:
    closes[-1] = close_val
    
    # Last 50 values (excluding the last one) sum to 50 * sma_50_val - close_val
    # So each of the 49 values is (50 * sma_50_val - close_val) / 49
    val_50 = (50 * sma_50_val - close_val) / 49
    for i in range(length - 50, length - 1):
        closes[i] = val_50
        
    # Values between length-150 and length-50 sum to 150 * sma_150_val - 50 * sma_50_val
    # So each of the 100 values is (150 * sma_150_val - 50 * sma_50_val) / 100
    val_150 = (150 * sma_150_val - 50 * sma_50_val) / 100
    for i in range(length - 150, length - 50):
        closes[i] = val_150
        
    # Values between length-200 and length-150 sum to 200 * sma_200_val - 150 * sma_150_val
    # So each of the 50 values is (200 * sma_200_val - 150 * sma_150_val) / 50
    val_200 = (200 * sma_200_val - 150 * sma_150_val) / 50
    for i in range(length - 200, length - 150):
        closes[i] = val_200
        
    df = pd.DataFrame({"close": closes})
    return df

def test_trend_all_pass():
    # Case 2.1.A: Close = 120, SMA50 = 110, SMA150 = 100, SMA200 = 90
    df = create_synthetic_trend_df(120.0, 110.0, 100.0, 90.0)
    res = calculate_trend_score(df)
    assert res["score"] == 15
    assert res["status"] == "passed"
    assert res["price_above_50dma"] is True
    assert res["sma50_above_150"] is True
    assert res["sma150_above_200"] is True

def test_trend_two_pass_price_fail():
    # Case 2.1.B: Close = 105, SMA50 = 110, SMA150 = 100, SMA200 = 95
    # close < SMA50 (False), SMA50 > SMA150 (True), SMA150 > SMA200 (True)
    df = create_synthetic_trend_df(105.0, 110.0, 100.0, 95.0)
    res = calculate_trend_score(df)
    assert res["score"] == 8
    assert res["status"] == "passed"
    assert res["price_above_50dma"] is False
    assert res["sma50_above_150"] is True
    assert res["sma150_above_200"] is True

def test_trend_two_pass_sma150_fail():
    # Close = 120, SMA50 = 110, SMA150 = 105, SMA200 = 115
    # close > SMA50 (True), SMA50 > SMA150 (True), SMA150 > SMA200 (False)
    df = create_synthetic_trend_df(120.0, 110.0, 105.0, 115.0)
    res = calculate_trend_score(df)
    assert res["score"] == 8
    assert res["status"] == "passed"
    assert res["price_above_50dma"] is True
    assert res["sma50_above_150"] is True
    assert res["sma150_above_200"] is False

def test_trend_two_pass_sma50_fail():
    # Close = 120, SMA50 = 95, SMA150 = 100, SMA200 = 90
    # close > SMA50 (True), SMA50 > SMA150 (False), SMA150 > SMA200 (True)
    df = create_synthetic_trend_df(120.0, 95.0, 100.0, 90.0)
    res = calculate_trend_score(df)
    assert res["score"] == 8
    assert res["status"] == "passed"
    assert res["price_above_50dma"] is True
    assert res["sma50_above_150"] is False
    assert res["sma150_above_200"] is True

def test_trend_one_pass_gate_fail():
    # Case 2.1.C: Close = 98, SMA50 = 105, SMA150 = 100, SMA200 = 102
    # close > SMA50 (False), SMA50 > SMA150 (True), SMA150 > SMA200 (False) -> 1 true
    df = create_synthetic_trend_df(98.0, 105.0, 100.0, 102.0)
    res = calculate_trend_score(df)
    assert res["score"] == 0
    assert res["status"] == "failed"
    assert res["price_above_50dma"] is False
    assert res["sma50_above_150"] is True
    assert res["sma150_above_200"] is False

def test_trend_one_pass_price_only():
    # Close = 120, SMA50 = 115, SMA150 = 118, SMA200 = 122
    # close > SMA50 (True), SMA50 > SMA150 (False), SMA150 > SMA200 (False) -> 1 true
    df = create_synthetic_trend_df(120.0, 115.0, 118.0, 122.0)
    res = calculate_trend_score(df)
    assert res["score"] == 0
    assert res["status"] == "failed"

def test_trend_none_pass():
    # Close = 90, SMA50 = 100, SMA150 = 110, SMA200 = 120
    # All false
    df = create_synthetic_trend_df(90.0, 100.0, 110.0, 120.0)
    res = calculate_trend_score(df)
    assert res["score"] == 0
    assert res["status"] == "failed"
    assert res["price_above_50dma"] is False
    assert res["sma50_above_150"] is False
    assert res["sma150_above_200"] is False

def test_trend_insufficient_data():
    df = pd.DataFrame({"close": [100.0] * 150})
    res = calculate_trend_score(df)
    assert res["score"] == 0
    assert res["status"] == "failed"
    assert res["price_above_50dma"] is False
