"""
Tests for CS-1 coverage diagnostics helpers.
Uses synthetic data only — no real data files needed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from energy_futures.experiments.coverage_diagnostics import (
    bootstrap_coverage,
    compute_condition_table,
    compute_group_table,
    stats_row,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _synthetic_df(n_days: int = 10, demand_val: float = 25_000.0, seed: int = 0) -> pd.DataFrame:
    """Return a minimal period DataFrame matching the shape built_period_df produces.

    Intervals: 50% = [24000, 26000], 80% = [23000, 27000], 90% = [22000, 28000].
    demand_val is constant, so coverage is 100% for all intervals when demand is 25000.
    """
    n = n_days * 48
    idx = pd.date_range("2023-01-02", periods=n, freq="30min", tz="UTC")
    local = idx.tz_convert("Europe/London")

    df = pd.DataFrame(
        {
            "underlying_demand": np.full(n, demand_val),
            "temperature_2m_gb_mean": np.full(n, 5.0),  # warm: obs >= 3 C
            "q05": np.full(n, 22_000.0),
            "q10": np.full(n, 23_000.0),
            "q25": np.full(n, 24_000.0),
            "q50": np.full(n, 25_000.0),
            "q75": np.full(n, 26_000.0),
            "q90": np.full(n, 27_000.0),
            "q95": np.full(n, 28_000.0),
        },
        index=idx,
    )

    df["slot"] = (local.hour * 2 + local.minute // 30).astype(int)
    df["month"] = local.month.astype(int)
    df["year"] = local.year
    df["date"] = local.date
    df["is_holiday"] = False
    df["is_xmas"] = False
    df["is_winter"] = df["month"].isin([12, 1, 2])
    df["cold_obs"] = False      # temp = 5 C, all warm
    df["cold_fcast"] = np.nan   # simulate 2023-style (no forecast temp)
    df["is_high_demand"] = False

    df["covered_50%"] = (df["underlying_demand"] >= df["q25"]) & (df["underlying_demand"] <= df["q75"])
    df["covered_80%"] = (df["underlying_demand"] >= df["q10"]) & (df["underlying_demand"] <= df["q90"])
    df["covered_90%"] = (df["underlying_demand"] >= df["q05"]) & (df["underlying_demand"] <= df["q95"])
    df["width_50%"] = df["q75"] - df["q25"]
    df["width_80%"] = df["q90"] - df["q10"]
    df["width_90%"] = df["q95"] - df["q05"]
    df["period"] = "2023"
    return df


# ---------------------------------------------------------------------------
# bootstrap_coverage tests
# ---------------------------------------------------------------------------

def test_bootstrap_all_ones():
    """Perfect coverage: all days covered, CI collapses to [1.0, 1.0]."""
    rng = np.random.default_rng(0)
    vals = np.ones(50)
    mean, lo, hi = bootstrap_coverage(vals, n_boot=200, rng=rng)
    assert mean == pytest.approx(1.0)
    assert lo == pytest.approx(1.0)
    assert hi == pytest.approx(1.0)


def test_bootstrap_all_zeros():
    """Zero coverage: CI collapses to [0.0, 0.0]."""
    rng = np.random.default_rng(0)
    vals = np.zeros(50)
    mean, lo, hi = bootstrap_coverage(vals, n_boot=200, rng=rng)
    assert mean == pytest.approx(0.0)
    assert lo == pytest.approx(0.0)
    assert hi == pytest.approx(0.0)


def test_bootstrap_empty():
    """Empty input returns three nans."""
    mean, lo, hi = bootstrap_coverage(np.array([]))
    assert np.isnan(mean)
    assert np.isnan(lo)
    assert np.isnan(hi)


def test_bootstrap_ci_ordered():
    """CI bounds satisfy lo <= mean <= hi for any realistic input."""
    rng = np.random.default_rng(42)
    vals = rng.uniform(0.4, 0.9, 100)
    mean, lo, hi = bootstrap_coverage(vals, n_boot=500, rng=rng)
    assert lo <= mean
    assert mean <= hi


def test_bootstrap_wider_ci_for_higher_variance():
    """Higher variance across days should produce a wider CI."""
    low_var = np.full(60, 0.8)
    high_var = np.concatenate([np.zeros(30), np.ones(30)])  # 50% zero, 50% one
    rng1 = np.random.default_rng(1)
    rng2 = np.random.default_rng(1)
    _, lo1, hi1 = bootstrap_coverage(low_var, n_boot=500, rng=rng1)
    _, lo2, hi2 = bootstrap_coverage(high_var, n_boot=500, rng=rng2)
    assert (hi2 - lo2) > (hi1 - lo1)


# ---------------------------------------------------------------------------
# stats_row tests
# ---------------------------------------------------------------------------

def test_stats_row_perfect_coverage():
    """demand=25000 inside [24000, 26000]: 100% coverage, width=2000 MW."""
    rng = np.random.default_rng(0)
    df = _synthetic_df(n_days=5, demand_val=25_000.0)
    result = stats_row(df, "50%", rng)
    assert result["coverage_pct"] == pytest.approx(100.0)
    assert result["ci_low_pct"] == pytest.approx(100.0)
    assert result["ci_high_pct"] == pytest.approx(100.0)
    assert result["width_mean_mw"] == pytest.approx(2_000.0, abs=0.2)
    assert result["n_days"] == 5
    assert result["n_halfhours"] == 5 * 48


def test_stats_row_zero_coverage():
    """demand=30000 outside [24000, 26000]: 0% coverage."""
    rng = np.random.default_rng(0)
    df = _synthetic_df(n_days=5, demand_val=30_000.0)
    df["covered_50%"] = False  # explicitly set to match the demand change
    result = stats_row(df, "50%", rng)
    assert result["coverage_pct"] == pytest.approx(0.0)


def test_stats_row_half_coverage():
    """50% of half-hours covered: coverage should be close to 50%."""
    n = 10 * 48
    rng_seed = np.random.default_rng(99)
    idx = pd.date_range("2023-02-01", periods=n, freq="30min", tz="UTC")
    local = idx.tz_convert("Europe/London")
    df = pd.DataFrame(
        {
            "covered_50%": np.tile([True, False], n // 2),
            "width_50%": np.full(n, 2_000.0),
            "date": local.date,
        },
        index=idx,
    )
    result = stats_row(df, "50%", rng_seed)
    assert result["coverage_pct"] == pytest.approx(50.0, abs=1.0)


# ---------------------------------------------------------------------------
# Coverage flag tests
# ---------------------------------------------------------------------------

def test_coverage_flag_boundary():
    """Exact boundary values: demand == lo and demand == hi should be covered."""
    lo, hi = 20_000.0, 30_000.0
    demands = np.array([lo, hi, lo - 1, hi + 1, 25_000.0])
    flags = (demands >= lo) & (demands <= hi)
    assert flags.tolist() == [True, True, False, False, True]


def test_cold_day_classification():
    """Daily mean obs temp < 3 C → cold_obs = True."""
    idx = pd.date_range("2023-01-01", periods=96, freq="30min", tz="UTC")
    local = idx.tz_convert("Europe/London")
    # Jan 1: temps 2.0 and 2.5 (alternating) → mean 2.25 → cold
    # Jan 2: temps 5.0 (all) → mean 5.0 → warm
    temps = np.where(local.date == local.date[0], 2.25, 5.0)
    df = pd.DataFrame(
        {"temperature_2m_gb_mean": temps, "date": local.date},
        index=idx,
    )
    daily_mean = df.groupby("date")["temperature_2m_gb_mean"].mean()
    cold_flags = df["date"].map(daily_mean) < 3.0
    # First 48 half-hours are Jan 1 (cold); next 48 are Jan 2 (warm)
    assert cold_flags.iloc[:48].all()
    assert not cold_flags.iloc[48:].any()


# ---------------------------------------------------------------------------
# compute_condition_table / compute_group_table smoke tests
# ---------------------------------------------------------------------------

def test_condition_table_shape():
    """compute_condition_table: every non-empty condition gets exactly 3 interval rows."""
    rng = np.random.default_rng(0)
    df = _synthetic_df(n_days=10)
    result = compute_condition_table(df, rng)
    assert len(result) > 0
    assert set(result["interval"].unique()) == {"50%", "80%", "90%"}
    assert "All" in result["condition"].values
    # Every (condition, period) group must have exactly 3 rows (one per interval)
    for cond, grp in result.groupby("condition"):
        assert len(grp) == 3, f"Condition '{cond}' has {len(grp)} rows, expected 3"


def test_group_table_months():
    """compute_group_table on 'month' should return one row per month × interval."""
    rng = np.random.default_rng(0)
    df = _synthetic_df(n_days=10)
    result = compute_group_table(df, "month", rng)
    months_present = df["month"].nunique()
    assert len(result) == months_present * 3  # 3 intervals


def test_group_table_slot_coverage_sums():
    """With perfect coverage, every slot should report coverage_pct == 100.0."""
    rng = np.random.default_rng(0)
    df = _synthetic_df(n_days=10, demand_val=25_000.0)
    result = compute_group_table(df, "slot", rng)
    sub = result[result["interval"] == "50%"]
    assert (sub["coverage_pct"] == 100.0).all()
