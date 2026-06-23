import pandas as pd

def calculate_breakout_quality(df: pd.DataFrame) -> dict:
    """
    Calculate Breakout Quality score (10 points max).
    df: DataFrame containing open, high, low, close, volume, sorted by date ascending.
    """
    default_failed = {
        "score": 0.0,
        "base_score": 0.0,
        "gap_pct": 0.0,
        "gap_bonus": 0.0,
        "close_pct_of_range": 0.0,
        "upper_wick_pct": 0.0
    }

    if len(df) < 2:
        return default_failed

    today = df.iloc[-1]
    prior = df.iloc[-2]

    o = float(today['open'])
    h = float(today['high'])
    l = float(today['low'])
    c = float(today['close'])
    v = float(today['volume'])
    prior_c = float(prior['close'])

    range_val = h - l
    if range_val == 0:
        close_pct_of_range = 0.0
        upper_wick_pct = 0.0
    else:
        close_pct_of_range = (c - l) / range_val
        upper_wick_pct = (h - max(c, o)) / range_val

    base_score = 10.0 * close_pct_of_range * (1.0 - upper_wick_pct)

    # Gap bonus check
    gap_pct = 0.0
    gap_bonus = 0.0
    if prior_c > 0:
        gap_pct = (o - prior_c) / prior_c * 100.0
        
    # Check volume for gap bonus (volume > 2 * SMA(volume, 50))
    if len(df) >= 51:
        ma50_vol = df['volume'].iloc[-51:-1].mean()
        if ma50_vol > 0 and gap_pct > 3.0 and v > 2.0 * ma50_vol:
            gap_bonus = 2.0

    total_score = min(10.0, base_score + gap_bonus)

    return {
        "score": float(total_score),
        "base_score": float(base_score),
        "gap_pct": float(gap_pct),
        "gap_bonus": float(gap_bonus),
        "close_pct_of_range": float(close_pct_of_range),
        "upper_wick_pct": float(upper_wick_pct)
    }
