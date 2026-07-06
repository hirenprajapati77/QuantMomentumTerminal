def calculate_fundamental_score(data: dict) -> dict:
    """
    Calculate Fundamental Filter score (10 points max) and gate status.

    Each of the 7 criteria is evaluated as one of: pass, fail, or unavailable
    (value is None/missing — common for banks/NBFCs on growth and leverage
    ratios, which are not meaningfully comparable to non-financial companies).

    Gate logic:
      - Unavailable criteria are excluded from both the numerator and
        denominator — they are never counted as a failure.
      - If fewer than 3 criteria have real data, the gate fails outright
        (too little information to make a fundamental call).
      - Otherwise, the gate passes if at least 70% of the AVAILABLE criteria
        pass (e.g. 5/7, 4/5, 3/4 all clear; 2/3 does not).
    """
    def _check(value, comparator):
        if value is None:
            return None  # unavailable
        return comparator(float(value))

    checks = {
        "sales_growth_qoq_pass": _check(data.get("sales_growth_qoq"), lambda v: v > 10.0),
        "sales_growth_yoy_pass": _check(data.get("sales_growth_yoy"), lambda v: v > 15.0),
        "profit_growth_yoy_pass": _check(data.get("profit_growth_yoy"), lambda v: v > 15.0),
        "roce_pass": _check(data.get("roce"), lambda v: v > 18.0),
        "roe_pass": _check(data.get("roe"), lambda v: v > 15.0),
        "debt_to_equity_pass": _check(data.get("debt_to_equity"), lambda v: v < 0.5),
        "institutional_holding_qoq_change_pass": _check(data.get("institutional_holding_qoq_change"), lambda v: v > 0.0),
    }

    available = [v for v in checks.values() if v is not None]
    passed_count = sum(1 for v in available if v)

    if len(available) < 3:
        gate_passed = False
    else:
        gate_passed = (passed_count / len(available)) >= 0.7

    return {
        "score": 10 if gate_passed else 0,
        "passes_gate": gate_passed,
        "details": {
            **checks,
            "criteria_available": len(available),
            "criteria_passed": passed_count
        }
    }
