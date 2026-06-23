import pytest
from app.scanner.sector_indicator import score_sectors

def test_sector_ranking_case_a():
    # Case 2.7.A: 5 sectors: IT (+8.5%), Infra (+4.2%), Metal (+1.0%), Bank (-1.5%), Pharma (-3.2%)
    # Ranks (1-based):
    #   1. IT -> ratio = 1/5 = 0.20 -> Score = 5
    #   2. Infra -> ratio = 2/5 = 0.40 -> Score = 3
    #   3. Metal -> ratio = 3/5 = 0.60 -> Score = 0
    #   4. Bank -> ratio = 4/5 = 0.80 -> Score = 0
    #   5. Pharma -> ratio = 5/5 = 1.00 -> Score = 0
    universe_data = {
        "sym1": {"sector": "IT", "return_20d": 0.085},
        "sym2": {"sector": "Infra", "return_20d": 0.042},
        "sym3": {"sector": "Metal", "return_20d": 0.010},
        "sym4": {"sector": "Bank", "return_20d": -0.015},
        "sym5": {"sector": "Pharma", "return_20d": -0.032}
    }
    scores = score_sectors(universe_data)
    
    assert scores["sym1"]["score"] == 5
    assert scores["sym2"]["score"] == 3
    assert scores["sym3"]["score"] == 0
    assert scores["sym4"]["score"] == 0
    assert scores["sym5"]["score"] == 0

def test_sector_avg_calculations():
    # Multiple stocks in the same sector
    # IT returns: 0.10 and 0.08 -> average = 0.09
    # Bank returns: 0.02 and -0.04 -> average = -0.01
    universe_data = {
        "A": {"sector": "IT", "return_20d": 0.10},
        "B": {"sector": "IT", "return_20d": 0.08},
        "C": {"sector": "Bank", "return_20d": 0.02},
        "D": {"sector": "Bank", "return_20d": -0.04}
    }
    scores = score_sectors(universe_data)
    assert scores["A"]["sector_return"] == pytest.approx(0.09, abs=1e-4)
    assert scores["C"]["sector_return"] == pytest.approx(-0.01, abs=1e-4)

def test_sector_single_sector():
    universe_data = {
        "sym1": {"sector": "IT", "return_20d": 0.05}
    }
    scores = score_sectors(universe_data)
    # Ratio = 1/1 = 1.0 -> score = 0
    assert scores["sym1"]["score"] == 0

def test_sector_empty_data():
    assert score_sectors({}) == {}

def test_sector_missing_sector_field():
    universe_data = {
        "sym1": {"return_20d": 0.05}  # missing sector
    }
    scores = score_sectors(universe_data)
    assert scores["sym1"]["score"] == 0
    assert scores["sym1"]["sector"] == "Unknown"

def test_sector_duplicate_returns():
    # IT = 0.05, Bank = 0.05
    # Depending on sorting stability, they will be ranked 1st and 2nd.
    # K=2. Ranks 1 and 2. Ratios: 0.50 and 1.0. Both scores 0.
    universe_data = {
        "sym1": {"sector": "IT", "return_20d": 0.05},
        "sym2": {"sector": "Bank", "return_20d": 0.05}
    }
    scores = score_sectors(universe_data)
    assert scores["sym1"]["score"] == 0
    assert scores["sym2"]["score"] == 0

def test_sector_ten_sectors():
    # 10 sectors, average returns: S1=10, S2=9, S3=8, S4=7, S5=6, S6=5, S7=4, S8=3, S9=2, S10=1
    # Ratios: S1: 0.1, S2: 0.2, S3: 0.3, S4: 0.4, S5: 0.5, ...
    universe_data = {}
    for i in range(1, 11):
        universe_data[f"sym{i}"] = {"sector": f"Sec{i}", "return_20d": float(11 - i)}
        
    scores = score_sectors(universe_data)
    assert scores["sym1"]["score"] == 5  # Sec1, ratio 0.1
    assert scores["sym2"]["score"] == 5  # Sec2, ratio 0.2
    assert scores["sym3"]["score"] == 3  # Sec3, ratio 0.3
    assert scores["sym4"]["score"] == 3  # Sec4, ratio 0.4
    assert scores["sym5"]["score"] == 0  # Sec5, ratio 0.5
    assert scores["sym10"]["score"] == 0 # Sec10, ratio 1.0

def test_sector_exactly_two_sectors():
    # K = 2. Sec1=10%, Sec2=5%
    # Ratios: Sec1: 0.50, Sec2: 1.0
    # Both scores 0
    universe_data = {
        "A": {"sector": "Sec1", "return_20d": 0.10},
        "B": {"sector": "Sec2", "return_20d": 0.05}
    }
    scores = score_sectors(universe_data)
    assert scores["A"]["score"] == 0
    assert scores["B"]["score"] == 0
