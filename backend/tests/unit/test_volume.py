import pytest
import pandas as pd
from app.scanner.volume import calculate_volume_expansion

def create_synthetic_volume_df(baseline_val, breakout_val, length=51):
    # Create volume series of length `length`.
    # Last day gets breakout_val.
    # Previous length-1 days get baseline_val.
    # MA50_vol will be baseline_val since all preceding days have that value.
    vols = [baseline_val] * length
    vols[-1] = breakout_val
    return pd.DataFrame({"volume": vols})

def test_volume_expansion_pass():
    # Case 2.5.A: Breakout = 2.5M, MA = 1.0M -> ratio = 2.5 -> score = 10, status = passed
    df = create_synthetic_volume_df(1000000, 2500000)
    res = calculate_volume_expansion(df)
    assert res["score"] == 10
    assert res["status"] == "passed"
    assert res["ratio"] == pytest.approx(2.5, abs=1e-4)

def test_volume_expansion_exhaustion():
    # Case 2.5.B: Breakout = 4.0M, MA = 1.0M -> ratio = 4.0 -> score = 7, status = passed
    df = create_synthetic_volume_df(1000000, 4000000)
    res = calculate_volume_expansion(df)
    assert res["score"] == 7
    assert res["status"] == "passed"
    assert res["ratio"] == pytest.approx(4.0, abs=1e-4)

def test_volume_expansion_gate_fail():
    # Case 2.5.C: Breakout = 1.5M, MA = 1.0M -> ratio = 1.5 -> score = 0, status = failed (REJECT)
    df = create_synthetic_volume_df(1000000, 1500000)
    res = calculate_volume_expansion(df)
    assert res["score"] == 0
    assert res["status"] == "failed"
    assert res["ratio"] == pytest.approx(1.5, abs=1e-4)

def test_volume_expansion_insufficient_data():
    # Length < 51
    df = create_synthetic_volume_df(1000000, 2500000, length=45)
    res = calculate_volume_expansion(df)
    assert res["score"] == 0
    assert res["status"] == "failed"

def test_volume_expansion_exact_boundary_lower():
    # ratio = 2.0 -> score = 10
    df = create_synthetic_volume_df(1000000, 2000000)
    res = calculate_volume_expansion(df)
    assert res["score"] == 10
    assert res["status"] == "passed"

def test_volume_expansion_exact_boundary_upper():
    # ratio = 3.0 -> score = 10
    df = create_synthetic_volume_df(1000000, 3000000)
    res = calculate_volume_expansion(df)
    assert res["score"] == 10
    assert res["status"] == "passed"

def test_volume_expansion_boundary_exhaustion():
    # ratio = 3.01 -> score = 7
    df = create_synthetic_volume_df(1000000, 3010000)
    res = calculate_volume_expansion(df)
    assert res["score"] == 7
    assert res["status"] == "passed"

def test_volume_expansion_zero_volume_baseline():
    df = create_synthetic_volume_df(0, 2500000)
    res = calculate_volume_expansion(df)
    assert res["score"] == 0
    assert res["status"] == "failed"
