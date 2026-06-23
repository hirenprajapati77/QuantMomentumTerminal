import pandas as pd
import numpy as np

def calculate_vdu_score(df: pd.DataFrame, contraction_start_idx: int, contraction_end_idx: int) -> dict:
    """
    Calculate Volume Dry-Up (VDU) score (15 points max).
    df: DataFrame containing close, high, low, open, and volume columns.
    contraction_start_idx: start index of the contraction window.
    contraction_end_idx: end index of the contraction window (usually day before breakout).
    """
    default_failed = {
        "dryup_ratio": 1.0,
        "score": 0,
        "baseline_vol": 0.0,
        "recent_vol": 0.0
    }

    # Ensure valid indices and enough history
    if contraction_start_idx < 20 or contraction_end_idx >= len(df) or contraction_start_idx > contraction_end_idx:
        return default_failed

    # Baseline volume: 20 bars before the contraction window
    baseline_start = max(0, contraction_start_idx - 20)
    baseline_end = contraction_start_idx - 1
    baseline_vol = df['volume'].iloc[baseline_start:baseline_end + 1].mean()

    # Recent volume: last 7 bars of the contraction window
    # If the contraction window is shorter than 7 bars, we use all bars in the contraction window
    recent_len = min(7, contraction_end_idx - contraction_start_idx + 1)
    recent_start = contraction_end_idx - recent_len + 1
    recent_vol = df['volume'].iloc[recent_start:contraction_end_idx + 1].mean()

    if pd.isna(baseline_vol) or pd.isna(recent_vol) or baseline_vol == 0:
        return default_failed

    dryup_ratio = float(recent_vol / baseline_vol)

    if dryup_ratio < 0.50:
        score = 15
    elif dryup_ratio < 0.70:
        score = 10
    else:
        score = 0

    return {
        "dryup_ratio": dryup_ratio,
        "score": score,
        "baseline_vol": float(baseline_vol),
        "recent_vol": float(recent_vol)
    }
