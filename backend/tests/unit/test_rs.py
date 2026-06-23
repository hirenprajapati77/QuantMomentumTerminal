import pytest
import pandas as pd
from app.scanner.rs import calculate_raw_rs, score_universe_rs

def create_synthetic_rs_df(length=101, close_start=100.0, close_end=120.0):
    # Create a simple series where start value is close_start and end is close_end.
    # To control return precisely, we can set index 0, -21, -51, -101 to specific values.
    closes = [close_start] * length
    # Last value (index -1):
    closes[-1] = close_end
    # Set index -21 (20 days ago), -51 (50 days ago), -101 (100 days ago) to close_start
    closes[-21] = close_start
    closes[-51] = close_start
    closes[-101] = close_start
    return pd.DataFrame({"close": closes})

def test_rs_raw_calculations():
    # Stock return over 20d: (120/100)-1 = 0.20
    # Sector return over 20d: (110/100)-1 = 0.10
    # Relative return 20d = 0.20 - 0.10 = 0.10
    # Let's align all periods (20, 50, 100) to check out as:
    # Stock return = 0.20, Sector return = 0.10 -> relative = 0.10
    stock_df = create_synthetic_rs_df(length=101, close_start=100.0, close_end=120.0)
    sector_df = create_synthetic_rs_df(length=101, close_start=100.0, close_end=110.0)
    
    res = calculate_raw_rs(stock_df, sector_df)
    assert res["rel_20"] == pytest.approx(0.10, abs=1e-4)
    assert res["rel_50"] == pytest.approx(0.10, abs=1e-4)
    assert res["rel_100"] == pytest.approx(0.10, abs=1e-4)

def test_rs_score_universe_top():
    # Case 2.4.A: Stock A is top in all periods. We have 5 stocks in the universe.
    # Stock A has rel_20=0.10, rel_50=0.10, rel_100=0.10
    # Stock B has rel_20=0.05, rel_50=0.05, rel_100=0.05
    # Stock C has rel_20=0.00, ...
    raw_map = {
        "A": {"rel_20": 0.10, "rel_50": 0.10, "rel_100": 0.10},
        "B": {"rel_20": 0.05, "rel_50": 0.05, "rel_100": 0.05},
        "C": {"rel_20": 0.00, "rel_50": 0.00, "rel_100": 0.00},
        "D": {"rel_20": -0.05, "rel_50": -0.05, "rel_100": -0.05},
        "E": {"rel_20": -0.10, "rel_50": -0.10, "rel_100": -0.10}
    }
    scores = score_universe_rs(raw_map)
    # Stock A is highest (rank 5/5 -> PR = 1.0)
    assert scores["A"]["pr_20"] == pytest.approx(1.0, abs=1e-4)
    assert scores["A"]["score"] == pytest.approx(15.0, abs=1e-4)

def test_rs_score_universe_median():
    # Case 2.4.B: Stock C is median in all periods. We have 5 stocks.
    # Stock C has rank 3/5 -> PR = 0.60
    raw_map = {
        "A": {"rel_20": 0.10, "rel_50": 0.10, "rel_100": 0.10},
        "B": {"rel_20": 0.05, "rel_50": 0.05, "rel_100": 0.05},
        "C": {"rel_20": 0.00, "rel_50": 0.00, "rel_100": 0.00},
        "D": {"rel_20": -0.05, "rel_50": -0.05, "rel_100": -0.05},
        "E": {"rel_20": -0.10, "rel_50": -0.10, "rel_100": -0.10}
    }
    scores = score_universe_rs(raw_map)
    assert scores["C"]["pr_20"] == pytest.approx(0.60, abs=1e-4)
    # 15 * (0.5 * 0.6 + 0.3 * 0.6 + 0.2 * 0.6) = 15 * 0.6 = 9.0
    assert scores["C"]["score"] == pytest.approx(9.0, abs=1e-4)

def test_rs_score_universe_bottom():
    raw_map = {
        "A": {"rel_20": 0.10, "rel_50": 0.10, "rel_100": 0.10},
        "B": {"rel_20": 0.05, "rel_50": 0.05, "rel_100": 0.05},
        "C": {"rel_20": 0.00, "rel_50": 0.00, "rel_100": 0.00},
        "D": {"rel_20": -0.05, "rel_50": -0.05, "rel_100": -0.05},
        "E": {"rel_20": -0.10, "rel_50": -0.10, "rel_100": -0.10}
    }
    scores = score_universe_rs(raw_map)
    # Stock E is lowest (rank 1/5 -> PR = 0.20)
    assert scores["E"]["pr_20"] == pytest.approx(0.20, abs=1e-4)
    # 15 * 0.20 = 3.0
    assert scores["E"]["score"] == pytest.approx(3.0, abs=1e-4)

def test_rs_raw_insufficient_data():
    stock_df = pd.DataFrame({"close": [100.0] * 50})
    sector_df = pd.DataFrame({"close": [100.0] * 50})
    res = calculate_raw_rs(stock_df, sector_df)
    assert res["rel_20"] == 0.0
    assert res["rel_50"] == 0.0
    assert res["rel_100"] == 0.0

def test_rs_score_single_stock():
    raw_map = {
        "A": {"rel_20": 0.10, "rel_50": 0.10, "rel_100": 0.10}
    }
    scores = score_universe_rs(raw_map)
    assert scores["A"]["pr_20"] == 1.0
    assert scores["A"]["score"] == 15.0

def test_rs_score_duplicate_values():
    # duplicate values should return average ranks
    # A=10, B=10 (ranks 1.5, 1.5 out of 2) -> PR = 1.5/2 = 0.75
    raw_map = {
        "A": {"rel_20": 0.10, "rel_50": 0.10, "rel_100": 0.10},
        "B": {"rel_20": 0.10, "rel_50": 0.10, "rel_100": 0.10}
    }
    scores = score_universe_rs(raw_map)
    assert scores["A"]["pr_20"] == 0.75
    assert scores["B"]["pr_20"] == 0.75

def test_rs_score_empty_map():
    assert score_universe_rs({}) == {}
