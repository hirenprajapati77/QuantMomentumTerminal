import pandas as pd
import numpy as np

def calculate_cpr_score(df: pd.DataFrame) -> dict:
    """
    Calculate CPR Score (5 points max).
    df: DataFrame containing close, high, low columns, sorted by date ascending.
    """
    default_failed = {
        "score": 0,
        "status": "failed",
        "cpr_width_pct": 0.0,
        "cpr_avg_width_pct": 0.0,
        "is_narrow": False,
        "is_expanding": True,
        "pivot": 0.0,
        "bc": 0.0,
        "tc": 0.0
    }

    if len(df) < 100:
        # Not enough history to compute trailing 100-day CPR percentile
        return default_failed

    # Calculate CPR values for the history, shifted by 1 day
    # (today's CPR levels are based on yesterday's candle)
    h_prev = df['high'].shift(1)
    l_prev = df['low'].shift(1)
    c_prev = df['close'].shift(1)
    c = df['close']

    pivots = (h_prev + l_prev + c_prev) / 3.0
    bcs = (h_prev + l_prev) / 2.0
    tcs = (pivots - bcs) + pivots
    widths = (tcs - bcs).abs() / pivots * 100.0

    # Get trailing 100 days of widths (including today)
    trailing_widths = widths.iloc[-100:]
    today_width = float(widths.iloc[-1])
    today_close = float(c.iloc[-1])
    today_tc = float(tcs.iloc[-1])
    today_bc = float(bcs.iloc[-1])
    today_pivot = float(pivots.iloc[-1])

    # 100-day average width and 30th percentile
    avg_width = float(trailing_widths.mean())
    pct30_width = float(trailing_widths.quantile(0.30))

    is_narrow = today_width <= pct30_width
    is_expanding = today_width > avg_width

    if is_expanding:
        score = 0
        status = "failed"  # Timing Reject
    elif is_narrow:
        if today_close > today_tc:
            score = 5
            status = "passed"
        else:
            score = 2
            status = "passed"
    else:
        score = 0
        status = "passed"

    return {
        "score": score,
        "status": status,
        "cpr_width_pct": today_width,
        "cpr_avg_width_pct": avg_width,
        "is_narrow": is_narrow,
        "is_expanding": is_expanding,
        "pivot": today_pivot,
        "bc": today_bc,
        "tc": today_tc
    }
