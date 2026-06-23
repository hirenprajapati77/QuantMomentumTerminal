import pandas as pd
import numpy as np

def score_sectors(universe_data: dict[str, dict]) -> dict[str, dict]:
    """
    Rank sectors by their average 20-day returns and assign scores.
    universe_data: dict mapping symbol (str) to {"sector": sector_name, "return_20d": return_20d}
    Returns: dict mapping symbol to {
        "sector": sector_name,
        "sector_return": float,
        "score": int
    }
    """
    if not universe_data:
        return {}

    # Group returns by sector
    sector_returns = {}
    for sym, data in universe_data.items():
        sec = data.get("sector")
        ret = data.get("return_20d", 0.0)
        if sec:
            if sec not in sector_returns:
                sector_returns[sec] = []
            sector_returns[sec].append(ret)

    # Compute average return per sector
    sector_avg = {}
    for sec, rets in sector_returns.items():
        sector_avg[sec] = float(np.mean(rets))

    # Sort sectors descending by return
    sorted_sectors = sorted(sector_avg.items(), key=lambda x: x[1], reverse=True)
    k = len(sorted_sectors)

    # Determine thresholds
    sector_scores = {}
    for idx, (sec, avg_ret) in enumerate(sorted_sectors):
        rank_1based = idx + 1
        ratio = rank_1based / k if k > 0 else 1.0

        if ratio <= 0.20:
            score = 5
        elif ratio <= 0.40:
            score = 3
        else:
            score = 0
            
        sector_scores[sec] = {
            "sector_return": avg_ret,
            "score": score
        }

    # Map back to symbols
    symbol_scores = {}
    for sym, data in universe_data.items():
        sec = data.get("sector")
        if sec in sector_scores:
            symbol_scores[sym] = {
                "sector": sec,
                "sector_return": sector_scores[sec]["sector_return"],
                "score": sector_scores[sec]["score"]
            }
        else:
            symbol_scores[sym] = {
                "sector": sec or "Unknown",
                "sector_return": 0.0,
                "score": 0
            }

    return symbol_scores
