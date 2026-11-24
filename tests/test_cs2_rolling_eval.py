"""
Tests for CS-2b rolling evaluation (synthetic data only).
No real data files are read; no 2026 data is loaded.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from energy_futures.experiments.cs2_rolling_eval import (
    METHODS,
    _sanity_check,
    evaluate,
)


# ---------------------------------------------------------------------------
# Synthetic data fixture
# ---------------------------------------------------------------------------

def _make_synth(n_days: int = 95, seed: int = 99, nan_y_indices: list[int] | None = None):
    """Return (raw_q, y, temp_proxy, obs_temp_daily) for 2023-01-01 + n_days.

    n_days=95 covers 2023-Q1 (90 days) + 5 days of 2023-Q2.
    nan_y_indices: list of integer positions in y to set to NaN.
    """
    rng = np.random.default_rng(seed)
    n = n_days * 48
    index = pd.date_range("2023-01-01", periods=n, freq="30min", tz="UTC")

    base = rng.uniform(5_000.0, 10_000.0, size=(n, 1))
    deltas = rng.uniform(50.0, 200.0, size=(n, 6))
    cum = np.hstack([np.zeros((n, 1)), np.cumsum(deltas, axis=1)])
    raw_q = pd.DataFrame(
        (base + cum).astype(float),
        columns=["q05", "q10", "q25", "q50", "q75", "q90", "q95"],
        index=index,
    )

    y_arr = rng.uniform(raw_q["q05"].values * 0.9, raw_q["q95"].values * 1.1)
    if nan_y_indices:
        y_arr[nan_y_indices] = np.nan
    y = pd.Series(y_arr, index=index)

    local = index.tz_convert("Europe/London")
    unique_dates = sorted(set(local.date))
    temp_proxy = pd.Series(
        {d: 1.0 if i % 7 == 0 else 15.0 for i, d in enumerate(unique_dates)},
        dtype=float,
    )
    obs_temp_daily = pd.Series({d: 15.0 for d in unique_dates}, dtype=float)
    return raw_q, y, temp_proxy, obs_temp_daily


# ---------------------------------------------------------------------------
# (1) Smoke test: files written and return dict well-formed
# ---------------------------------------------------------------------------

def test_evaluate_smoke(tmp_path):
    """evaluate() on synthetic data writes expected output files and returns valid dict."""
    raw_q, y, temp_proxy, obs_temp = _make_synth(n_days=95)
    result = evaluate(raw_q, y, temp_proxy, obs_temp, out_dir=tmp_path)

    # Stage 2b file names (nan_proxy_counts.csv renamed to data_quality_counts.csv)
    for fname in [
        "metrics_by_quarter.csv",
        "metrics_pooled.csv",
        "data_quality_counts.csv",
        "fallback_report.csv",
    ]:
        assert (tmp_path / fname).exists(), f"Missing output file: {fname}"

    # selection.txt is NOT written by evaluate() — only by run() after sanity check
    assert not (tmp_path / "selection.txt").exists(), (
        "selection.txt must not be written by evaluate(); only by run() after sanity check"
    )

    for key in ["selected_method", "metrics_df", "quarter_df", "pooled_df",
                "data_quality_df", "fallback_df", "select_input", "sanity_data"]:
        assert key in result, f"Missing key: {key}"

    assert result["selected_method"] in METHODS
    df = result["metrics_df"]
    assert set(df["method"].unique()) == set(METHODS)
    assert "2023-Q1" in df["quarter"].values
    assert "pooled" in df["quarter"].values

    # select_input has baseline entry
    base = result["select_input"]["baseline"]
    for key in ["coverage_90_all", "coverage_90_cold", "coverage_90_high", "width_90", "winkler"]:
        assert key in base


# ---------------------------------------------------------------------------
# (2) NaN proxy days counted correctly
# ---------------------------------------------------------------------------

def test_evaluate_nan_proxy_counted(tmp_path):
    """data_quality_df reports correct NaN-proxy day count per quarter."""
    raw_q, y, _, obs_temp = _make_synth(n_days=95)
    local = raw_q.index.tz_convert("Europe/London")
    unique_dates = sorted(set(local.date))
    nan_dates = set(unique_dates[:3])
    temp_proxy = pd.Series(
        {d: float("nan") if d in nan_dates else 15.0 for d in unique_dates}, dtype=float
    )

    result = evaluate(raw_q, y, temp_proxy, obs_temp, out_dir=tmp_path)
    dq = result["data_quality_df"]
    q1 = dq[dq["quarter"] == "2023-Q1"]
    assert len(q1) == len(METHODS)
    assert (q1["n_nan_proxy_days"] == 3).all()


# ---------------------------------------------------------------------------
# (a) NaN y dropped before metrics
# ---------------------------------------------------------------------------

def test_nan_y_dropped_before_metrics(tmp_path):
    """Half-hours with missing actual demand are dropped; count reported in data_quality_df."""
    # Set first 96 half-hours (2 full days) of 2023-Q1 to NaN
    nan_indices = list(range(96))
    raw_q, y, temp_proxy, obs_temp = _make_synth(n_days=95, nan_y_indices=nan_indices)

    result = evaluate(raw_q, y, temp_proxy, obs_temp, out_dir=tmp_path)
    dq = result["data_quality_df"]
    q1 = dq[dq["quarter"] == "2023-Q1"]

    # 96 NaN half-hours in 2023-Q1 (all methods see the same y)
    assert (q1["n_nan_y_dropped"] == 96).all(), (
        f"Expected 96 NaN y dropped in 2023-Q1; got:\n{q1[['method','n_nan_y_dropped']]}"
    )

    # Metrics must still exist and be finite (not polluted by NaN y)
    pooled = result["pooled_df"]
    base_cov = pooled[
        (pooled["method"] == "baseline") &
        (pooled["condition_key"] == "all") &
        (pooled["metric"] == "covered_90")
    ]["mean"]
    assert len(base_cov) == 1
    assert np.isfinite(base_cov.iloc[0]), "Coverage must be finite after dropping NaN y"


def test_nan_y_no_effect_when_zero(tmp_path):
    """When y has no NaN, n_nan_y_dropped should be 0 for all quarters and methods."""
    raw_q, y, temp_proxy, obs_temp = _make_synth(n_days=95)
    result = evaluate(raw_q, y, temp_proxy, obs_temp, out_dir=tmp_path)
    dq = result["data_quality_df"]
    assert (dq["n_nan_y_dropped"] == 0).all()


# ---------------------------------------------------------------------------
# (b) Sanity check
# ---------------------------------------------------------------------------

def test_sanity_check_passes(tmp_path):
    """_sanity_check writes sanity_check.txt and does not raise when values are on target."""
    sanity_data = {"cov_2023": 92.3, "cov_2024_25": 90.4}
    _sanity_check(sanity_data, out_dir=tmp_path, ref_2024_25=90.5, ref_2023=92.5, tol=0.5)
    assert (tmp_path / "sanity_check.txt").exists()
    text = (tmp_path / "sanity_check.txt").read_text()
    assert "PASS" in text


def test_sanity_check_fails_on_large_deviation(tmp_path):
    """_sanity_check raises ValueError when 2024-25 coverage is off by >0.5 pp."""
    sanity_data = {"cov_2023": 92.5, "cov_2024_25": 88.0}  # diff = -2.5 pp
    with pytest.raises(ValueError, match="Sanity check FAILED"):
        _sanity_check(sanity_data, out_dir=tmp_path, ref_2024_25=90.5, ref_2023=92.5, tol=0.5)
    # sanity_check.txt is written even on failure (for debugging)
    assert (tmp_path / "sanity_check.txt").exists()
    text = (tmp_path / "sanity_check.txt").read_text()
    assert "FAIL" in text


def test_sanity_check_2023_not_a_failure(tmp_path):
    """Large 2023 deviation alone must NOT raise (only 2024-25 is a failure condition)."""
    sanity_data = {"cov_2023": 85.0, "cov_2024_25": 90.4}  # 2023 is way off, 2024-25 is fine
    _sanity_check(sanity_data, out_dir=tmp_path, ref_2024_25=90.5, ref_2023=92.5, tol=0.5)
    # Must not raise


def test_sanity_check_nan_raises(tmp_path):
    """NaN 2024-25 coverage raises ValueError (data missing for that period)."""
    sanity_data = {"cov_2023": 92.5, "cov_2024_25": float("nan")}
    with pytest.raises(ValueError, match="NaN"):
        _sanity_check(sanity_data, out_dir=tmp_path)


def test_sanity_data_in_result(tmp_path):
    """evaluate() returns sanity_data with cov_2023 and cov_2024_25 keys."""
    raw_q, y, temp_proxy, obs_temp = _make_synth(n_days=95)
    result = evaluate(raw_q, y, temp_proxy, obs_temp, out_dir=tmp_path)
    sd = result["sanity_data"]
    # With only 2023 data, cov_2023 should be finite; cov_2024_25 may be NaN
    assert "cov_2023" in sd
    assert "cov_2024_25" in sd
    assert np.isfinite(sd["cov_2023"]), "cov_2023 must be finite"


# ---------------------------------------------------------------------------
# (c) Fallback report
# ---------------------------------------------------------------------------

def test_fallback_report_exists(tmp_path):
    """fallback_report.csv is written and has the expected columns."""
    raw_q, y, temp_proxy, obs_temp = _make_synth(n_days=95)
    result = evaluate(raw_q, y, temp_proxy, obs_temp, out_dir=tmp_path)

    assert (tmp_path / "fallback_report.csv").exists()
    fb = result["fallback_df"]
    for col in ["quarter", "stratum", "total_days",
                "mondrian_fallback_days", "mondrian_fallback_share_pct",
                "mondrian_ext_fallback_days", "mondrian_ext_fallback_share_pct"]:
        assert col in fb.columns, f"Missing column: {col}"


def test_fallback_shares_in_range(tmp_path):
    """Fallback share percentages must be in [0, 100]."""
    raw_q, y, temp_proxy, obs_temp = _make_synth(n_days=95)
    result = evaluate(raw_q, y, temp_proxy, obs_temp, out_dir=tmp_path)
    fb = result["fallback_df"]
    for col in ["mondrian_fallback_share_pct", "mondrian_ext_fallback_share_pct"]:
        assert (fb[col] >= 0).all() and (fb[col] <= 100).all(), (
            f"{col} out of [0, 100] range"
        )


def test_fallback_extended_cold_le_mondrian_cold(tmp_path):
    """mondrian_ext_fallback_days ≤ mondrian_fallback_days for cold stratum
    (extended window can only equal or reduce fallbacks vs standard window)."""
    raw_q, y, temp_proxy, obs_temp = _make_synth(n_days=95)
    result = evaluate(raw_q, y, temp_proxy, obs_temp, out_dir=tmp_path)
    fb = result["fallback_df"]
    cold = fb[fb["stratum"] == "cold"]
    if len(cold) > 0:
        assert (cold["mondrian_ext_fallback_days"] <= cold["mondrian_fallback_days"]).all(), (
            "mondrian_extended should fall back no more than mondrian for cold stratum"
        )


# ---------------------------------------------------------------------------
# High-demand threshold consistency (unchanged from original)
# ---------------------------------------------------------------------------

def test_evaluate_high_demand_threshold_consistent(tmp_path):
    """High-demand n_days is identical across methods for the same quarter."""
    raw_q, y, temp_proxy, obs_temp = _make_synth(n_days=95)
    result = evaluate(raw_q, y, temp_proxy, obs_temp, out_dir=tmp_path)
    df = result["quarter_df"]
    for quarter in df["quarter"].unique():
        q = df[df["quarter"] == quarter]
        hd = q[(q["condition_key"] == "high_demand") & (q["metric"] == "covered_90")]
        if len(hd) > 0:
            n_per_method = hd["n_days"].values
            assert np.all(n_per_method == n_per_method[0]), (
                f"High-demand n_days differs across methods in {quarter}: {n_per_method}"
            )
