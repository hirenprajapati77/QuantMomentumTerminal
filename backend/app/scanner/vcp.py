import pandas as pd
import numpy as np

def calculate_atr(df: pd.DataFrame, period: int = 10) -> pd.Series:
    """Calculate Average True Range (ATR)"""
    high = df['high']
    low = df['low']
    close = df['close']
    
    # Calculate True Range (TR)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Standard ATR is SMA of TR
    atr = tr.rolling(period).mean()
    return atr

def calculate_vcp_score(df: pd.DataFrame) -> dict:
    """
    Calculate VCP pattern score (20 points max).
    df: DataFrame containing close, high, low, open, and volume columns.
    Sorted by date ascending.
    """
    default_failed = {
        "quality": "None",
        "contraction_count": 0,
        "contraction_ratios": [],
        "score": 0,
        "status": "failed",
        "remarks": "No valid VCP pattern found"
    }

    if len(df) < 30:
        return default_failed

    # Calculate ATR(10) and Daily Range Percentage
    df = df.copy()
    df['atr10'] = calculate_atr(df, period=10)
    df['daily_range_pct'] = (df['high'] - df['low']) / df['close'] * 100

    # 1. Find raw swing points using 5-bar fractal
    extrema = []
    n = len(df)
    for t in range(2, n - 2):
        h_t = df['high'].iloc[t]
        if h_t > df['high'].iloc[t-1] and h_t > df['high'].iloc[t-2] and \
           h_t > df['high'].iloc[t+1] and h_t > df['high'].iloc[t+2]:
            extrema.append((t, 'high', float(h_t)))

        l_t = df['low'].iloc[t]
        if l_t < df['low'].iloc[t-1] and l_t < df['low'].iloc[t-2] and \
           l_t < df['low'].iloc[t+1] and l_t < df['low'].iloc[t+2]:
            extrema.append((t, 'low', float(l_t)))

    extrema.sort(key=lambda x: x[0])

    # 2. Keep alternating extrema
    alternating = []
    for item in extrema:
        if not alternating:
            alternating.append(item)
        else:
            last = alternating[-1]
            if last[1] == item[1]:
                # Keep more extreme one
                if last[1] == 'high' and item[2] > last[2]:
                    alternating[-1] = item
                elif last[1] == 'low' and item[2] < last[2]:
                    alternating[-1] = item
            else:
                alternating.append(item)

    # Contractions must start with a High and end with a Low
    while alternating and alternating[0][1] == 'low':
        alternating.pop(0)
    while alternating and alternating[-1][1] == 'high':
        alternating.pop()

    if len(alternating) < 4:  # At least 2 pairs of High-Low
        return default_failed

    # Group into contractions (High -> Low legs)
    raw_contractions = []
    for i in range(0, len(alternating), 2):
        if i + 1 < len(alternating):
            h_pt = alternating[i]
            l_pt = alternating[i+1]
            pct = (h_pt[2] - l_pt[2]) / h_pt[2] * 100
            raw_contractions.append({
                "high_idx": h_pt[0],
                "high_val": h_pt[2],
                "low_idx": l_pt[0],
                "low_val": l_pt[2],
                "pct": pct
            })

    # We only care about the last 2 to 4 contractions for the VCP pattern
    # Let's check subsets of the end of raw_contractions (from size 4 down to 2)
    best_vcp = None
    
    for count in [4, 3, 2]:
        if len(raw_contractions) < count:
            continue
            
        # Get the trailing 'count' contractions
        candidate = raw_contractions[-count:]
        
        # Verify Higher Lows: swing_low[i] >= swing_low[i-1]
        higher_lows = True
        for i in range(1, count):
            if candidate[i]['low_val'] < candidate[i-1]['low_val']:
                higher_lows = False
                break
        if not higher_lows:
            continue

        # Verify Volatility Contraction: contraction_pct strictly smaller than prior
        declining_pcts = True
        ratios = []
        for i in range(1, count):
            prior = candidate[i-1]['pct']
            curr = candidate[i]['pct']
            if curr >= prior or prior == 0:
                declining_pcts = False
                break
            ratios.append(curr / prior)
        if not declining_pcts:
            continue

        # Verify Declining ATR: ATR at pattern end <= ATR at pattern start
        start_idx = candidate[0]['high_idx']
        end_idx = candidate[-1]['low_idx']
        
        atr_start = df['atr10'].iloc[start_idx]
        atr_end = df['atr10'].iloc[end_idx]
        
        # Avoid NaN values if ATR wasn't calculated (e.g., at very start of series)
        if pd.isna(atr_start) or pd.isna(atr_end) or atr_end > atr_start:
            # We relax the strict ATR check if start index is too early and NaN, but otherwise check it
            if not (pd.isna(atr_start) or pd.isna(atr_end)):
                continue

        # Verify Tight Candles: Avg daily range in final contraction <= 50% of first contraction
        first_contraction_range = df['daily_range_pct'].iloc[candidate[0]['high_idx']:candidate[0]['low_idx']+1].mean()
        final_contraction_range = df['daily_range_pct'].iloc[candidate[-1]['high_idx']:candidate[-1]['low_idx']+1].mean()
        
        if final_contraction_range > 0.50 * first_contraction_range:
            continue

        # If we reached here, the pattern is valid!
        # Determine the score based on contraction count and ratios
        score = 0
        quality = "Normal"
        
        if count == 4:
            if all(r <= 0.70 for r in ratios):
                score = 20
                quality = "Elite"
            else:
                score = 5
                quality = "Looser"
        elif count == 3:
            if all(r <= 0.75 for r in ratios):
                score = 16
                quality = "High"
            elif all(r <= 0.80 for r in ratios):
                score = 10
                quality = "Normal"
            else:
                score = 5
                quality = "Looser"
        elif count == 2:
            if all(r <= 0.80 for r in ratios):
                score = 10
                quality = "Normal"
            elif all(r <= 0.95 for r in ratios):
                score = 5
                quality = "Looser"
            else:
                score = 5
                quality = "Looser"

        # Save this pattern if it has a higher score than any previously found candidate
        pattern_info = {
            "quality": quality,
            "contraction_count": count,
            "contraction_ratios": [float(r) for r in ratios],
            "score": score,
            "status": "passed",
            "remarks": f"Valid VCP with {count} contractions",
            "start_idx": int(start_idx),
            "end_idx": int(end_idx)
        }
        
        if best_vcp is None or pattern_info['score'] > best_vcp['score']:
            best_vcp = pattern_info

    if best_vcp is not None:
        return best_vcp

    return default_failed
