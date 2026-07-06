from app.scanner.fundamental_indicator import calculate_fundamental_score

def get_base_valid_data():
    """Helper to return a valid dictionary that passes all 7 screens."""
    return {
        "sales_growth_qoq": 12.0,
        "sales_growth_yoy": 18.0,
        "profit_growth_yoy": 25.0,
        "roce": 22.0,
        "roe": 17.0,
        "debt_to_equity": 0.2,
        "institutional_holding_qoq_change": 0.5
    }

def test_fundamental_all_pass():
    # All 7 available, 7 pass -> gate passes, score 10
    data = get_base_valid_data()
    res = calculate_fundamental_score(data)
    assert res["score"] == 10
    assert res["passes_gate"] is True
    assert res["details"]["criteria_available"] == 7
    assert res["details"]["criteria_passed"] == 7

def test_fundamental_5_pass_2_fail():
    # All 7 available, 5 pass / 2 fail -> gate passes (5/7 ≈ 71%)
    data = get_base_valid_data()
    data["roce"] = 12.0  # fail
    data["roe"] = 14.0   # fail
    res = calculate_fundamental_score(data)
    assert res["score"] == 10
    assert res["passes_gate"] is True
    assert res["details"]["criteria_available"] == 7
    assert res["details"]["criteria_passed"] == 5

def test_fundamental_4_pass_3_fail():
    # All 7 available, 4 pass / 3 fail -> gate fails (4/7 ≈ 57%)
    data = get_base_valid_data()
    data["roce"] = 12.0  # fail
    data["roe"] = 14.0   # fail
    data["debt_to_equity"] = 0.6  # fail
    res = calculate_fundamental_score(data)
    assert res["score"] == 0
    assert res["passes_gate"] is False
    assert res["details"]["criteria_available"] == 7
    assert res["details"]["criteria_passed"] == 4

def test_fundamental_5_available_4_pass():
    # 5 available (2 None), 4 of 5 pass -> gate passes (80%)
    data = get_base_valid_data()
    data["sales_growth_qoq"] = None
    data["sales_growth_yoy"] = None
    data["roce"] = 12.0  # fail
    res = calculate_fundamental_score(data)
    assert res["score"] == 10
    assert res["passes_gate"] is True
    assert res["details"]["criteria_available"] == 5
    assert res["details"]["criteria_passed"] == 4

def test_fundamental_insufficient_data():
    # 2 available (5 None) -> gate fails regardless of pass rate (insufficient data)
    data = {
        "sales_growth_qoq": None,
        "sales_growth_yoy": None,
        "profit_growth_yoy": None,
        "roce": None,
        "roe": None,
        "debt_to_equity": 0.2,                          # pass
        "institutional_holding_qoq_change": 0.5         # pass
    }
    res = calculate_fundamental_score(data)
    assert res["score"] == 0
    assert res["passes_gate"] is False
    assert res["details"]["criteria_available"] == 2

def test_fundamental_all_fail():
    # A stock with real (non-None) failing values on every metric still fails
    data = {
        "sales_growth_qoq": 5.0,
        "sales_growth_yoy": 5.0,
        "profit_growth_yoy": 5.0,
        "roce": 5.0,
        "roe": 5.0,
        "debt_to_equity": 2.0,
        "institutional_holding_qoq_change": -0.5
    }
    res = calculate_fundamental_score(data)
    assert res["score"] == 0
    assert res["passes_gate"] is False
    assert res["details"]["criteria_available"] == 7
    assert res["details"]["criteria_passed"] == 0
