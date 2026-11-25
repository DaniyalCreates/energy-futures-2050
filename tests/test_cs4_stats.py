"""
Tests for cs4_stats.py: DM test and Holm correction helpers.
Uses synthetic data only — no real data files required.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from energy_futures.experiments.cs4_stats import (
    dm_test,
    holm_correction,
    newey_west_variance,
    approx_pvalue_from_ci,
)


# ---------------------------------------------------------------------------
# Newey-West variance
# ---------------------------------------------------------------------------

def test_newey_west_variance_lag0_equals_sample_variance():
    """lag=0 Newey-West is just the sample mean-square (γ₀)."""
    rng = np.random.default_rng(0)
    d = rng.normal(0, 1, 100)
    nw = newey_west_variance(d, 0)
    expected = float(np.sum((d - d.mean()) ** 2) / len(d))
    assert abs(nw - expected) < 1e-10


def test_newey_west_variance_iid_converges():
    """For large iid data, NW variance should be close to sample variance."""
    rng = np.random.default_rng(42)
    d = rng.normal(5.0, 2.0, 1000)
    nw = newey_west_variance(d, 1)
    sample_var = float(np.var(d, ddof=0))
    # Should be within 10% for large n
    assert abs(nw - sample_var) / sample_var < 0.10


# ---------------------------------------------------------------------------
# DM test
# ---------------------------------------------------------------------------

def _make_dm_df(e_model, e_bench, n_days=100):
    """Create a minimal DataFrame matching the dm_test interface."""
    hh_per_day = 48
    total = n_days * hh_per_day
    idx = pd.date_range("2024-01-01", periods=total, freq="30min", tz="UTC")
    actual = np.zeros(total)
    model = np.tile(e_model[:hh_per_day], n_days)[:total] + actual
    bench = np.tile(e_bench[:hh_per_day], n_days)[:total] + actual
    return pd.DataFrame({"model_col": model, "bench_col": bench, "actual": actual}, index=idx)


def test_dm_identical_forecasts_stat_near_zero():
    """When both forecasts are identical, DM statistic should be ~0."""
    rng = np.random.default_rng(1)
    forecast = rng.normal(1000, 50, 48)
    df = _make_dm_df(forecast, forecast, n_days=100)
    result = dm_test(df, "model_col", "bench_col", lag=1)
    # d_t = 0 everywhere, so DM = 0/0 = nan, or if handled, near 0
    # Accept either nan or small value
    if np.isfinite(result["dm_stat"]):
        assert abs(result["dm_stat"]) < 1e-6
    else:
        assert np.isnan(result["dm_stat"])


def test_dm_clearly_better_forecast_significant():
    """A clearly better model (small noise) vs large-bias benchmark → highly significant DM."""
    rng = np.random.default_rng(99)
    n_days = 300
    total = n_days * 48
    actual = np.ones(total) * 30_000.0
    # model: small noise (1 MW); bench: large fixed bias (500 MW) + small noise
    noise = rng.normal(0, 1.0, total)
    idx = pd.date_range("2024-01-01", periods=total, freq="30min", tz="UTC")
    df = pd.DataFrame(
        {
            "model_col": actual + noise,
            "bench_col": actual + 500.0 + noise,
            "actual": actual,
        },
        index=idx,
    )
    result = dm_test(df, "model_col", "bench_col", lag=1)
    # d_t = |model_error| - |bench_error| ≈ 1 - 500 < 0 → DM strongly negative
    assert result["dm_stat"] < -10.0, f"Expected DM < -10, got {result['dm_stat']}"
    assert result["p_value"] < 0.001, f"Expected p < 0.001, got {result['p_value']}"
    assert result["n_days"] == n_days


def test_dm_clearly_worse_forecast_positive_stat():
    """Model with large bias vs accurate benchmark → strongly positive DM."""
    rng = np.random.default_rng(100)
    n_days = 300
    total = n_days * 48
    actual = np.ones(total) * 30_000.0
    noise = rng.normal(0, 1.0, total)
    idx = pd.date_range("2024-01-01", periods=total, freq="30min", tz="UTC")
    df = pd.DataFrame(
        {
            "model_col": actual + 500.0 + noise,
            "bench_col": actual + noise,
            "actual": actual,
        },
        index=idx,
    )
    result = dm_test(df, "model_col", "bench_col", lag=1)
    assert result["dm_stat"] > 10.0
    assert result["p_value"] < 0.001


def test_dm_returns_correct_mae():
    """MAE values should equal the analytical values."""
    n_days = 10
    total = n_days * 48
    actual = np.zeros(total)
    idx = pd.date_range("2024-01-01", periods=total, freq="30min", tz="UTC")
    df = pd.DataFrame(
        {"model_col": actual + 100.0, "bench_col": actual + 300.0, "actual": actual},
        index=idx,
    )
    result = dm_test(df, "model_col", "bench_col", lag=1)
    assert abs(result["mae_model_mw"] - 100.0) < 0.1
    assert abs(result["mae_benchmark_mw"] - 300.0) < 0.1


# ---------------------------------------------------------------------------
# Holm correction — hand-worked example
# ---------------------------------------------------------------------------

def test_holm_hand_worked_3_tests():
    """Hand-worked Holm example with m=3, α=0.05.

    p = [0.01, 0.03, 0.08] (sorted: 0.01, 0.03, 0.08)
    thresholds: 0.05/3=0.0167, 0.05/2=0.025, 0.05/1=0.05
    - rank 1: 0.01 < 0.0167 → reject ✓
    - rank 2: 0.03 > 0.025  → stop, accept all remaining
    Expected: [True, False, False]
    """
    p_values = [0.01, 0.03, 0.08]
    result = holm_correction(p_values, alpha=0.05)
    assert result == [True, False, False], f"Got {result}"


def test_holm_all_significant():
    """When all p-values easily survive, all should be rejected."""
    p_values = [0.001, 0.002, 0.003]
    result = holm_correction(p_values, alpha=0.05)
    assert result == [True, True, True]


def test_holm_none_significant():
    """When all p-values fail, none should be rejected."""
    p_values = [0.10, 0.20, 0.30]
    result = holm_correction(p_values, alpha=0.05)
    assert result == [False, False, False]


def test_holm_single_test():
    """Single test reduces to ordinary α threshold."""
    assert holm_correction([0.04], alpha=0.05) == [True]
    assert holm_correction([0.06], alpha=0.05) == [False]


def test_holm_order_independence():
    """Holm result should not depend on input order."""
    # Same p-values, different input orders
    r1 = holm_correction([0.01, 0.03, 0.08])
    r2 = holm_correction([0.08, 0.01, 0.03])
    # r1: [True, False, False] for indices 0,1,2
    # r2: for index 1 (p=0.01) → True; indices 0,2 (p=0.08, 0.03) → False
    # Count of True rejections must be the same
    assert sum(r1) == sum(r2)


# ---------------------------------------------------------------------------
# approx_pvalue_from_ci
# ---------------------------------------------------------------------------

def test_approx_pvalue_ci_excludes_zero_gives_low_p():
    """CI that clearly excludes zero should give small p-value."""
    p = approx_pvalue_from_ci(diff=-100.0, lo=-200.0, hi=-20.0)
    assert p < 0.05, f"Expected p < 0.05 for CI excluding zero, got {p}"


def test_approx_pvalue_ci_includes_zero_gives_large_p():
    """CI that includes zero should give large p-value."""
    p = approx_pvalue_from_ci(diff=-20.0, lo=-300.0, hi=200.0)
    assert p > 0.5, f"Expected p > 0.5 for CI including zero, got {p}"


def test_approx_pvalue_matches_known_case():
    """Historical 2024-25 mean: diff=-68.73, lo=-124.86, hi=-24.59 → p ≈ 0.007."""
    p = approx_pvalue_from_ci(diff=-68.73, lo=-124.859077, hi=-24.593169)
    assert abs(p - 0.007) < 0.002, f"Expected p ≈ 0.007, got {p:.4f}"
