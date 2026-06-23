import pandas as pd

def calculate_trend_score(df: pd.DataFrame) -> dict:
    """
    Calculate Trend Structure score (15 points max).
    df: DataFrame containing at least 'close' column, sorted by date ascending.
    Returns: {
        "score": int,
        "status": str ("passed" or "failed"),
        "price_above_50dma": bool,
        "sma50_above_150": bool,
        "sma150_above_200": bool,
        "close": float,
        "sma_50": float,
        "sma_150": float,
        "sma_200": float
    }
    """
    if len(df) < 200:
        # Not enough data to calculate 200 SMA
        return {
            "score": 0,
            "status": "failed",
            "price_above_50dma": False,
            "sma50_above_150": False,
            "sma150_above_200": False,
            "close": float(df['close'].iloc[-1]) if len(df) > 0 else 0.0,
            "sma_50": 0.0,
            "sma_150": 0.0,
            "sma_200": 0.0
        }

    # Calculate SMAs
    sma_50 = df['close'].rolling(50).mean().iloc[-1]
    sma_150 = df['close'].rolling(150).mean().iloc[-1]
    sma_200 = df['close'].rolling(200).mean().iloc[-1]
    close = df['close'].iloc[-1]

    price_above_50dma = bool(close > sma_50)
    sma50_above_150 = bool(sma_50 > sma_150)
    sma150_above_200 = bool(sma_150 > sma_200)

    true_count = sum([price_above_50dma, sma50_above_150, sma150_above_200])

    if true_count == 3:
        score = 15
        status = "passed"
    elif true_count == 2:
        score = 8
        status = "passed"
    else:
        score = 0
        status = "failed"

    return {
        "score": score,
        "status": status,
        "price_above_50dma": price_above_50dma,
        "sma50_above_150": sma50_above_150,
        "sma150_above_200": sma150_above_200,
        "close": float(close),
        "sma_50": float(sma_50),
        "sma_150": float(sma_150),
        "sma_200": float(sma_200)
    }
