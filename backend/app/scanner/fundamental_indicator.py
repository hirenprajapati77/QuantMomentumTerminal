def calculate_fundamental_score(data: dict) -> dict:
    """
    Calculate Fundamental Filter score (10 points max) and gate status.
    data: dict containing the fundamental ratios:
        - sales_growth_qoq (float)
        - sales_growth_yoy (float)
        - profit_growth_yoy (float)
        - roce (float)
        - roe (float)
        - debt_to_equity (float)
        - institutional_holding_qoq_change (float)
    """
    sales_qoq_pass = float(data.get("sales_growth_qoq", 0.0)) > 10.0
    sales_yoy_pass = float(data.get("sales_growth_yoy", 0.0)) > 15.0
    profit_yoy_pass = float(data.get("profit_growth_yoy", 0.0)) > 15.0
    roce_pass = float(data.get("roce", 0.0)) > 18.0
    roe_pass = float(data.get("roe", 0.0)) > 15.0
    debt_pass = float(data.get("debt_to_equity", 999.0)) < 0.5
    inst_pass = float(data.get("institutional_holding_qoq_change", 0.0)) > 0.0

    all_pass = all([
        sales_qoq_pass,
        sales_yoy_pass,
        profit_yoy_pass,
        roce_pass,
        roe_pass,
        debt_pass,
        inst_pass
    ])

    return {
        "score": 10 if all_pass else 0,
        "passes_gate": all_pass,
        "details": {
            "sales_growth_qoq_pass": sales_qoq_pass,
            "sales_growth_yoy_pass": sales_yoy_pass,
            "profit_growth_yoy_pass": profit_yoy_pass,
            "roce_pass": roce_pass,
            "roe_pass": roe_pass,
            "debt_to_equity_pass": debt_pass,
            "institutional_holding_qoq_change_pass": inst_pass
        }
    }
