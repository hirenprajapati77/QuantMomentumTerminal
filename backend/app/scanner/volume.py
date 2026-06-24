import pandas as pd

def calculate_volume_expansion(df: pd.DataFrame) -> dict:
    """
    Calculate Volume Expansion score (10 points max).
    df: DataFrame containing at least 'volume' column, sorted by date ascending.
    """
    default_failed = {
        "score": 0,
        "status": "failed",
        "ratio": 0.0,
        "breakout_vol": 0.0,
        "ma_vol": 0.0
    }

    if len(df) < 51:
        # We need at least 50 days of history prior to the breakout day (the last day)
        return default_failed

    breakout_vol = float(df['volume'].iloc[-1])
    # Compute 50-day average volume ending on the day BEFORE the breakout day
    ma50_vol = float(df['volume'].iloc[-51:-1].mean())

    if ma50_vol == 0:
        return default_failed

    ratio = breakout_vol / ma50_vol

    if ratio < 2.0:
        score = 0
        status = "failed"
    elif ratio <= 3.0:
        score = 10
        status = "passed"
    elif ratio <= 5.0:
        # Exhaustion/climactic volume — still valid but penalised
        score = 7
        status = "passed"
    else:
        # >5x is a climax top — hard reject
        score = 0
        status = "failed"

    return {
        "score": score,
        "status": status,
        "ratio": ratio,
        "breakout_vol": breakout_vol,
        "ma_vol": ma50_vol
    }
