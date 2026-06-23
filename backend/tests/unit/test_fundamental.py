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
    # Case 2.9.A: All screens pass -> 10 pts, passes_gate = True
    data = get_base_valid_data()
    res = calculate_fundamental_score(data)
    assert res["score"] == 10
    assert res["passes_gate"] is True

def test_fundamental_roce_fail():
    # Case 2.9.B: ROCE = 12.0 fails (> 18.0 required) -> 0 pts, passes_gate = False
    data = get_base_valid_data()
    data["roce"] = 12.0
    res = calculate_fundamental_score(data)
    assert res["score"] == 0
    assert res["passes_gate"] is False
    assert res["details"]["roce_pass"] is False
    assert res["details"]["roe_pass"] is True

def test_fundamental_roe_fail():
    # ROE = 14.0 fails (> 15.0 required)
    data = get_base_valid_data()
    data["roe"] = 14.0
    res = calculate_fundamental_score(data)
    assert res["score"] == 0
    assert res["passes_gate"] is False

def test_fundamental_debt_fail():
    # Debt/Equity = 0.6 fails (< 0.5 required)
    data = get_base_valid_data()
    data["debt_to_equity"] = 0.6
    res = calculate_fundamental_score(data)
    assert res["score"] == 0
    assert res["passes_gate"] is False

def test_fundamental_sales_qoq_fail():
    # sales_growth_qoq = 8.0 fails (> 10.0 required)
    data = get_base_valid_data()
    data["sales_growth_qoq"] = 8.0
    res = calculate_fundamental_score(data)
    assert res["score"] == 0
    assert res["passes_gate"] is False

def test_fundamental_sales_yoy_fail():
    # sales_growth_yoy = 12.0 fails (> 15.0 required)
    data = get_base_valid_data()
    data["sales_growth_yoy"] = 12.0
    res = calculate_fundamental_score(data)
    assert res["score"] == 0
    assert res["passes_gate"] is False

def test_fundamental_profit_yoy_fail():
    # profit_growth_yoy = 10.0 fails (> 15.0 required)
    data = get_base_valid_data()
    data["profit_growth_yoy"] = 10.0
    res = calculate_fundamental_score(data)
    assert res["score"] == 0
    assert res["passes_gate"] is False

def test_fundamental_inst_fail():
    # institutional_holding_qoq_change = -0.5 fails (> 0.0 required)
    data = get_base_valid_data()
    data["institutional_holding_qoq_change"] = -0.5
    res = calculate_fundamental_score(data)
    assert res["score"] == 0
    assert res["passes_gate"] is False
