"""
End-to-end smoke tests for CS-2b rolling evaluation (synthetic data only).
No real data files are read; no 2026 data is loaded.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from energy_futures.experiments.cs2_rolling_eval import METHODS, evaluate


# ---------------------------------------------------------------------------
# Synthetic data fixture
# ---------------------------------------------------------------------------

def _make_synth(n_days: int = 95, seed: int = 99):
    """Return (raw_q, y, temp_proxy, obs_temp_daily) covering 2023-Q1 and part of Q2.

    n_days=95 gives 90 days of 2023-Q1 (Jan–Mar 31) plus 5 days of Q2 (Apr 1–5),
    so both "2023-Q1" and "2023-Q2" appear in the evaluation output.
    """
    rng = np.random.default_rng(seed)
    n = n_days * 48
    index = pd.date_range("2023-01-01", periods=n, freq="30min", tz="UTC")

    # Monotone quantiles via cumulative increments
    base = rng.uniform(5_000.0, 10_000.0, size=(n, 1))
    deltas = rng.uniform(50.0, 200.0, size=(n, 6))
    cum = np.hstack([np.zeros((n, 1)), np.cumsum(deltas, axis=1)])
    raw_q = pd.DataFrame(
        (base + cum).astype(float),
        columns=["q05", "q10", "q25", "q50", "q75", "q90", "q95"],
        index=index,
    )

    # Actuals: some inside, some outside the 90% interval → nonzero CQR scores
    y = pd.Series(
        rng.uniform(raw_q["q05"].values * 0.9, raw_q["q95"].values * 1.1),
        index=index,
    )

    local = index.tz_convert("Europe/London")
    unique_dates = sorted(set(local.date))

    # Mix of cold (every 7th day) and warm days for stratification variety
    temp_proxy = pd.Series(
        {d: 1.0 if i % 7 == 0 else 15.0 for i, d in enumerate(unique_dates)},
        dtype=float,
    )
    obs_temp_daily = pd.Series({d: 15.0 for d in unique_dates}, dtype=float)

    return raw_q, y, temp_proxy, obs_temp_daily


# ---------------------------------------------------------------------------
# (1) Smoke test: files are written and return dict is well-formed
# ---------------------------------------------------------------------------

def test_evaluate_smoke(tmp_path):
    """evaluate() on synthetic data writes all expected output files and returns valid dict."""
    raw_q, y, temp_proxy, obs_temp = _make_synth(n_days=95)
    result = evaluate(raw_q, y, temp_proxy, obs_temp, out_dir=tmp_path)

    # Output files exist
    for fname in ["metrics_by_quarter.csv", "metrics_pooled.csv", "nan_proxy_counts.csv", "selection.txt"]:
        assert (tmp_path / fname).exists(), f"Missing output file: {fname}"

    # Return dict has expected keys
    for key in ["selected_method", "metrics_df", "quarter_df", "pooled_df", "nan_proxy_df", "select_input"]:
        assert key in result, f"Missing key in result: {key}"

    # selected_method is a valid method name
    assert result["selected_method"] in METHODS

    df = result["metrics_df"]
    # All 4 methods appear in the output
    assert set(df["method"].unique()) == set(METHODS)
    # At least 2023-Q1 appears (covered by our 95-day dataset)
    assert "2023-Q1" in df["quarter"].values
    # Pooled rows exist
    assert "pooled" in df["quarter"].values
    # Expected metric columns
    for col in ["quarter", "method", "condition_key", "metric", "mean", "ci_low_95", "ci_high_95", "n_days"]:
        assert col in df.columns

    # select_input has baseline entry with the required keys
    assert "baseline" in result["select_input"]
    base = result["select_input"]["baseline"]
    for key in ["coverage_90_all", "coverage_90_cold", "coverage_90_high", "width_90", "winkler"]:
        assert key in base, f"Missing key in select_input['baseline']: {key}"


# ---------------------------------------------------------------------------
# (2) NaN proxy days are counted correctly
# ---------------------------------------------------------------------------

def test_evaluate_nan_proxy_counted(tmp_path):
    """evaluate() reports the correct number of NaN-proxy days per quarter."""
    raw_q, y, _, obs_temp = _make_synth(n_days=95)

    local = raw_q.index.tz_convert("Europe/London")
    unique_dates = sorted(set(local.date))

    # First 3 days have NaN proxy; rest are warm
    nan_dates = set(unique_dates[:3])
    temp_proxy = pd.Series(
        {d: float("nan") if d in nan_dates else 15.0 for d in unique_dates},
        dtype=float,
    )

    result = evaluate(raw_q, y, temp_proxy, obs_temp, out_dir=tmp_path)
    nan_df = result["nan_proxy_df"]

    # 2023-Q1 starts 2023-01-01, so the first 3 days are in Q1
    q1_rows = nan_df[nan_df["quarter"] == "2023-Q1"]
    assert len(q1_rows) == len(METHODS), "Expected one row per method for 2023-Q1"
    # All methods see the same proxy, so NaN count should be 3 for all
    assert (q1_rows["n_nan_proxy_days"] == 3).all(), (
        f"Expected 3 NaN proxy days in 2023-Q1; got:\n{q1_rows[['method','n_nan_proxy_days']]}"
    )

    # Other quarters that have data should have 0 NaN proxy days
    q2_rows = nan_df[nan_df["quarter"] == "2023-Q2"]
    if len(q2_rows) > 0:
        assert (q2_rows["n_nan_proxy_days"] == 0).all()


# ---------------------------------------------------------------------------
# (3) High-demand flag uses full-window raw q50 (threshold is consistent)
# ---------------------------------------------------------------------------

def test_evaluate_high_demand_threshold_consistent(tmp_path):
    """High-demand flag is computed from raw q50 over the full eval window (all methods same)."""
    raw_q, y, temp_proxy, obs_temp = _make_synth(n_days=95)
    result = evaluate(raw_q, y, temp_proxy, obs_temp, out_dir=tmp_path)

    df = result["quarter_df"]
    # Number of high-demand days should be the same across methods for the same quarter
    for quarter in df["quarter"].unique():
        q = df[df["quarter"] == quarter]
        hd_rows = q[(q["condition_key"] == "high_demand") & (q["metric"] == "covered_90")]
        if len(hd_rows) > 0:
            n_days_per_method = hd_rows["n_days"].values
            assert np.all(n_days_per_method == n_days_per_method[0]), (
                f"High-demand n_days differs across methods in {quarter}: {n_days_per_method}"
            )
