import pandas as pd
import numpy as np

from app.scanner.trend import calculate_trend_score
from app.scanner.vcp import calculate_vcp_score
from app.scanner.vdu import calculate_vdu_score
from app.scanner.rs import calculate_raw_rs, score_universe_rs
from app.scanner.volume import calculate_volume_expansion
from app.scanner.breakout import calculate_breakout_quality
from app.scanner.sector_indicator import score_sectors
from app.scanner.cpr import calculate_cpr_score
from app.scanner.fundamental_indicator import calculate_fundamental_score

def calculate_raw_signals(stock_df: pd.DataFrame, sector_df: pd.DataFrame, fundamental_data: dict, sector_name: str) -> dict:
    """
    Compute raw indicators for a single stock.
    Returns a dictionary of raw metrics that do not require universe-wide context.
    """
    # 1. Trend Structure
    trend_res = calculate_trend_score(stock_df)
    
    # 2. VCP Engine
    vcp_res = calculate_vcp_score(stock_df)
    
    # 3. VDU Engine
    vdu_res = {
        "dryup_ratio": 1.0,
        "score": 0,
        "baseline_vol": 0.0,
        "recent_vol": 0.0
    }
    if vcp_res["status"] == "passed" and vcp_res["contraction_count"] > 0:
        # VCP detected, we use the shifted swing indices from VCP check
        # Wait, the VCP score returns indices on the shifted/aligned df.
        # Let's find first swing high index and last swing low index
        # We need the relative indexes since vcp_score works on stock_df
        # Since vcp_score shifts indices by 20 offset, we can calculate start and end.
        # Let's search raw_contractions inside VCP.
        # Wait! To make it robust, we can adjust shifted indexes.
        # Shifted High 1 index and Shifted Low N index are stored in best VCP candidate.
        # Let's adjust back by subtracting offset if needed, or VDU can use the shifted ones
        # if it receives the same df. Yes, vdu uses the same df, so shifted indexes are correct!
        # Let's construct swing points or read raw swing points from VCP output.
        # Wait, let's look at what calculate_vcp_score returns.
        # In our implementation, it returns:
        # {"quality": q, "contraction_count": c, "contraction_ratios": r, "score": s, "status": "passed"}
        # Wait! It didn't return the start and end indexes!
        # Let's modify calculate_vcp_score to return "start_idx" and "end_idx" of the pattern!
        # That is extremely helpful so VDU doesn't have to re-derive them!
        # Wait, does calculate_vcp_score return start_idx and end_idx?
        # Yes, we can update vcp.py to return them, or we can look for them here.
        # Actually, let's update vcp.py to return start_idx and end_idx.
        # Let's check how calculate_vcp_score was written.
        # It had:
        # pattern_info = {
        #     "quality": quality,
        #     "contraction_count": count,
        #     "contraction_ratios": [float(r) for r in ratios],
        #     "score": score,
        #     "status": "passed",
        #     "remarks": f"Valid VCP with {count} contractions"
        # }
        # Let's add "start_idx": candidate[0]["high_idx"] and "end_idx": candidate[-1]["low_idx"]
        # to pattern_info!
        pass

    # For now, let's write the wrapper. If VCP is passed, we get its start_idx and end_idx
    # which we will add to VCP output.
    start_idx = vcp_res.get("start_idx")
    end_idx = vcp_res.get("end_idx")
    if start_idx is not None and end_idx is not None:
        vdu_res = calculate_vdu_score(stock_df, start_idx, end_idx)
    else:
        # Fallback if VCP failed, VDU is 0
        vdu_res = {
            "dryup_ratio": 1.0,
            "score": 0,
            "baseline_vol": 0.0,
            "recent_vol": 0.0
        }

    # 4. Relative Strength (Raw)
    rs_raw = calculate_raw_rs(stock_df, sector_df)
    
    # 5. Volume Expansion
    vol_res = calculate_volume_expansion(stock_df)
    
    # 6. Breakout Quality
    breakout_res = calculate_breakout_quality(stock_df)
    
    # 7. CPR Engine
    cpr_res = calculate_cpr_score(stock_df)
    
    # 8. Fundamental Gate
    fundamental_res = calculate_fundamental_score(fundamental_data)
    
    # Calculate 20d return of stock for sector return aggregation
    return_20d = 0.0
    if len(stock_df) >= 21:
        return_20d = float((stock_df['close'].iloc[-1] / stock_df['close'].iloc[-21]) - 1.0)

    return {
        "sector": sector_name,
        "return_20d": return_20d,
        "trend": trend_res,
        "vcp": vcp_res,
        "vdu": vdu_res,
        "rs_raw": rs_raw,
        "volume": vol_res,
        "breakout": breakout_res,
        "cpr": cpr_res,
        "fundamental": fundamental_res
    }

def compute_composite_scores(universe_signals: dict[str, dict]) -> dict[str, dict]:
    """
    Computes final composite scores and grades across a universe of stocks.
    universe_signals: dict mapping symbol (str) to raw signals dictionary from calculate_raw_signals.
    """
    if not universe_signals:
        return {}

    symbols = list(universe_signals.keys())

    # 1. Score Relative Strength (Percentile-rank raw RS returns)
    raw_rs_map = {}
    for sym in symbols:
        raw_rs_map[sym] = universe_signals[sym]["rs_raw"]
    rs_scores = score_universe_rs(raw_rs_map)

    # 2. Score Sectors (Rank sectors and score constituent symbols)
    sector_input = {}
    for sym in symbols:
        sector_input[sym] = {
            "sector": universe_signals[sym]["sector"],
            "return_20d": universe_signals[sym]["return_20d"]
        }
    sector_scores = score_sectors(sector_input)

    # 3. Assemble composite scores and check entry signals
    results = {}
    for sym in symbols:
        sig = universe_signals[sym]
        
        # Pull individual indicator scores
        score_trend = sig["trend"]["score"]         # Max 15
        score_vcp = sig["vcp"]["score"]             # Max 20
        score_vdu = sig["vdu"]["score"]             # Max 15
        score_rs = rs_scores[sym]["score"]          # Max 15
        score_volume = sig["volume"]["score"]       # Max 10
        score_breakout = sig["breakout"]["score"]   # Max 10
        score_sector = sector_scores[sym]["score"]  # Max 5
        score_cpr = sig["cpr"]["score"]             # Max 5
        score_fundamental = sig["fundamental"]["score"] # Max 10

        # Composite score calculation (sums to 100)
        total_score = (
            score_trend + score_vcp + score_vdu + score_rs +
            score_volume + score_breakout + score_sector +
            score_cpr + score_fundamental
        )

        # Fundamental Gate check
        passes_fundamental_gate = sig["fundamental"]["passes_gate"]

        # Assign grades
        if total_score >= 90:
            grade = "Elite"
        elif total_score >= 85:
            grade = "A+"
        elif total_score >= 80:
            grade = "A"
        elif total_score >= 70:
            grade = "Watch"
        else:
            grade = "Reject"

        # Apply fundamental gate cap
        if not passes_fundamental_gate and grade in ["Elite", "A+", "A"]:
            grade = "Watch"

        # Check Entry Signal: All must be true simultaneously
        # 1. Total score >= 85
        # 2. breakout_vol_ratio >= 2.0
        # 3. Trend gate passed
        # 4. Sector in top 20% (score == 5)
        # 5. Breakout candle close in top 15% of range
        breakout_vol_ratio = sig["volume"]["ratio"]
        trend_passed = sig["trend"]["status"] == "passed"
        sector_passed = sector_scores[sym]["score"] == 5
        
        # Breakout candle close check
        close_pct = sig["breakout"]["close_pct_of_range"]
        upper_wick = sig["breakout"]["upper_wick_pct"]
        breakout_candles_passed = (close_pct >= 0.85) and (upper_wick <= 0.15)

        entry_triggered = (
            (total_score >= 85) and
            (breakout_vol_ratio >= 2.0) and
            trend_passed and
            sector_passed and
            breakout_candles_passed
        )

        results[sym] = {
            "symbol": sym,
            "sector": sig["sector"],
            "technical_score": float(total_score - score_fundamental),
            "fundamental_score": float(score_fundamental),
            "final_score": float(total_score),
            "grade": grade,
            "entry_triggered": bool(entry_triggered),
            "breakout_vol_ratio": breakout_vol_ratio,
            "trend_status": sig["trend"]["status"],
            "sector_score": score_sector,
            "close_pct_of_range": close_pct,
            "upper_wick_pct": upper_wick,
            "passes_fundamental": passes_fundamental_gate
        }

    return results
