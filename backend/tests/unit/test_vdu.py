import pytest
import pandas as pd
from app.scanner.vdu import calculate_vdu_score

def create_synthetic_vdu_df(baseline_vols, recent_vols):
    # baseline_vols is a list of 20 volumes
    # recent_vols is a list of 7 volumes
    # We construct a dataframe with 27 elements
    vols = list(baseline_vols) + list(recent_vols)
    df = pd.DataFrame({"volume": vols})
    return df

def test_vdu_strong_dryup():
    # Case 2.3.A: Baseline = 100000, Recent = 45000 -> ratio = 0.45 -> 15 pts
    df = create_synthetic_vdu_df([100000] * 20, [45000] * 7)
    res = calculate_vdu_score(df, contraction_start_idx=20, contraction_end_idx=26)
    assert res["score"] == 15
    assert res["dryup_ratio"] == pytest.approx(0.45, abs=1e-4)

def test_vdu_moderate_dryup():
    # Case 2.3.B: Baseline = 100000, Recent = 65000 -> ratio = 0.65 -> 10 pts
    df = create_synthetic_vdu_df([100000] * 20, [65000] * 7)
    res = calculate_vdu_score(df, contraction_start_idx=20, contraction_end_idx=26)
    assert res["score"] == 10
    assert res["dryup_ratio"] == pytest.approx(0.65, abs=1e-4)

def test_vdu_no_dryup():
    # Baseline = 100000, Recent = 80000 -> ratio = 0.80 -> 0 pts
    df = create_synthetic_vdu_df([100000] * 20, [80000] * 7)
    res = calculate_vdu_score(df, contraction_start_idx=20, contraction_end_idx=26)
    assert res["score"] == 0
    assert res["dryup_ratio"] == pytest.approx(0.80, abs=1e-4)

def test_vdu_invalid_start_index():
    # start index < 20 (fails/returns 0)
    df = create_synthetic_vdu_df([100000] * 20, [45000] * 7)
    res = calculate_vdu_score(df, contraction_start_idx=10, contraction_end_idx=26)
    assert res["score"] == 0
    assert res["dryup_ratio"] == 1.0

def test_vdu_end_index_out_of_bounds():
    df = create_synthetic_vdu_df([100000] * 20, [45000] * 7)
    res = calculate_vdu_score(df, contraction_start_idx=20, contraction_end_idx=35)
    assert res["score"] == 0

def test_vdu_start_greater_than_end():
    df = create_synthetic_vdu_df([100000] * 20, [45000] * 7)
    res = calculate_vdu_score(df, contraction_start_idx=25, contraction_end_idx=20)
    assert res["score"] == 0

def test_vdu_short_window():
    # Contraction window is only 4 bars (less than 7)
    # Volumes: baseline = 10000, recent (4 bars) = 4000 -> ratio = 0.40 -> 15 pts
    df = create_synthetic_vdu_df([10000] * 20, [4000] * 4)
    res = calculate_vdu_score(df, contraction_start_idx=20, contraction_end_idx=23)
    assert res["score"] == 15
    assert res["dryup_ratio"] == pytest.approx(0.40, abs=1e-4)

def test_vdu_zero_volume_baseline():
    df = create_synthetic_vdu_df([0] * 20, [45000] * 7)
    res = calculate_vdu_score(df, contraction_start_idx=20, contraction_end_idx=26)
    assert res["score"] == 0
    assert res["dryup_ratio"] == 1.0
