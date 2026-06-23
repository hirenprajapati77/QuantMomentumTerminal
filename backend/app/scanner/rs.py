import pandas as pd
import numpy as np

def calculate_raw_rs(stock_df: pd.DataFrame, sector_df: pd.DataFrame) -> dict:
    """
    Calculate raw relative strength returns for 20, 50, and 100 day periods.
    stock_df: DataFrame with close column, sorted by date ascending.
    sector_df: DataFrame with close column (sector index), sorted by date ascending.
    Returns: {
        "rel_20": float,
        "rel_50": float,
        "rel_100": float
    }
    """
    default_vals = {"rel_20": 0.0, "rel_50": 0.0, "rel_100": 0.0}
    
    if len(stock_df) < 101 or len(sector_df) < 101:
        return default_vals

    stock_close = stock_df['close']
    sector_close = sector_df['close']

    # We assume both series are aligned chronologically and we use their last entries
    stock_p20_ret = (stock_close.iloc[-1] / stock_close.iloc[-21]) - 1.0
    stock_p50_ret = (stock_close.iloc[-1] / stock_close.iloc[-51]) - 1.0
    stock_p100_ret = (stock_close.iloc[-1] / stock_close.iloc[-101]) - 1.0

    sector_p20_ret = (sector_close.iloc[-1] / sector_close.iloc[-21]) - 1.0
    sector_p50_ret = (sector_close.iloc[-1] / sector_close.iloc[-51]) - 1.0
    sector_p100_ret = (sector_close.iloc[-1] / sector_close.iloc[-101]) - 1.0

    return {
        "rel_20": float(stock_p20_ret - sector_p20_ret),
        "rel_50": float(stock_p50_ret - sector_p50_ret),
        "rel_100": float(stock_p100_ret - sector_p100_ret)
    }

def score_universe_rs(raw_rs_map: dict[str, dict]) -> dict[str, dict]:
    """
    Compute relative strength scores for a universe of stocks by percentile-ranking
    their raw RS returns.
    raw_rs_map: dict mapping symbol (str) to raw RS dict ({"rel_20": x, "rel_50": y, "rel_100": z})
    Returns: dict mapping symbol (str) to score dict:
        {
            "score": float,
            "pr_20": float,
            "pr_50": float,
            "pr_100": float
        }
    """
    if not raw_rs_map:
        return {}

    symbols = list(raw_rs_map.keys())
    n = len(symbols)

    rel_20_list = [raw_rs_map[sym]["rel_20"] for sym in symbols]
    rel_50_list = [raw_rs_map[sym]["rel_50"] for sym in symbols]
    rel_100_list = [raw_rs_map[sym]["rel_100"] for sym in symbols]

    # Convert to pandas Series and calculate percentile ranks
    # Default behavior is method='average', which handles duplicate values gracefully
    s_20 = pd.Series(rel_20_list)
    s_50 = pd.Series(rel_50_list)
    s_100 = pd.Series(rel_100_list)

    if n > 1:
        # standard pandas rank(pct=True) maps ranks to [1/N, 1.0] range
        pr_20 = s_20.rank(pct=True)
        pr_50 = s_50.rank(pct=True)
        pr_100 = s_100.rank(pct=True)
    else:
        # single stock defaults to percentile rank 1.0
        pr_20 = pd.Series([1.0])
        pr_50 = pd.Series([1.0])
        pr_100 = pd.Series([1.0])

    scores_map = {}
    for idx, sym in enumerate(symbols):
        p20 = float(pr_20.iloc[idx])
        p50 = float(pr_50.iloc[idx])
        p100 = float(pr_100.iloc[idx])
        
        # Weighted blend formula: 0.5 * p20 + 0.3 * p50 + 0.2 * p100
        score = 15.0 * (0.5 * p20 + 0.3 * p50 + 0.2 * p100)
        
        scores_map[sym] = {
            "score": score,
            "pr_20": p20,
            "pr_50": p50,
            "pr_100": p100
        }
        
    return scores_map
