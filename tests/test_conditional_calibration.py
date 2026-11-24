"""
Tests for CS-2a conditional calibration helpers.
Uses synthetic data only — no real data files needed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from energy_futures.experiments.conditional_calibration import (
    assign_stratum,
    calibrate_baseline,
    calibrate_mondrian,
    calibrate_width_normalised,
    select_method,
    apply_calibration_daily,
    load_development_data,
)
from energy_futures.uncertainty.calibration import rolling_cqr
from energy_futures.forecast import task


# ---------------------------------------------------------------------------
# assign_stratum tests
# ---------------------------------------------------------------------------

def test_assign_stratum_cold():
    """Temperature < 3°C → 'cold', regardless of demand level."""
    assert assign_stratum(None, temp_proxy=2.9, max_q50=50_000.0, threshold_95=20_000.0) == "cold"
    assert assign_stratum(None, temp_proxy=-5.0, max_q50=50_000.0, threshold_95=20_000.0) == "cold"
    # Cold overrides high-demand — priority rule
    assert assign_stratum(None, temp_proxy=2.9, max_q50=99_999.0, threshold_95=20_000.0) == "cold"


def test_assign_stratum_high_demand():
    """Temperature ≥ 3°C and max_q50 ≥ threshold_95 → 'high_demand'."""
    assert assign_stratum(None, temp_proxy=3.0, max_q50=20_000.0, threshold_95=20_000.0) == "high_demand"
    assert assign_stratum(None, temp_proxy=10.0, max_q50=25_000.0, threshold_95=20_000.0) == "high_demand"


def test_assign_stratum_normal():
    """Temperature ≥ 3°C and max_q50 < threshold_95 → 'normal'."""
    assert assign_stratum(None, temp_proxy=3.0, max_q50=19_999.0, threshold_95=20_000.0) == "normal"
    assert assign_stratum(None, temp_proxy=15.0, max_q50=10_000.0, threshold_95=20_000.0) == "normal"


# ---------------------------------------------------------------------------
# calibrate_baseline tests
# ---------------------------------------------------------------------------

def test_calibrate_baseline_level():
    """With n=9 scores and alpha=0.1: level = 0.9*10/9 = 1.0, so correction = max(scores)."""
    scores = np.arange(1.0, 10.0)  # [1, 2, ..., 9], n=9
    c = calibrate_baseline(scores, alpha=0.1)
    assert c == pytest.approx(9.0)

    # With n=99: level = 0.9 * 100/99 — verify via numpy directly
    scores2 = np.arange(1.0, 100.0)
    c2 = calibrate_baseline(scores2, alpha=0.1)
    expected_level = min(1.0, 0.9 * 100 / 99)
    assert c2 == pytest.approx(float(np.quantile(scores2, expected_level)), abs=1e-6)


# ---------------------------------------------------------------------------
# calibrate_mondrian tests
# ---------------------------------------------------------------------------

def test_calibrate_mondrian_uses_stratum_scores():
    """When stratum has ≥ min_days, correction uses only that stratum's scores."""
    # 20 "normal" days × 48 HH = 960 entries with score 10
    # 20 "cold"   days × 48 HH = 960 entries with score 100
    n_per_stratum = 20 * 48
    scores_norm = np.full(n_per_stratum, 10.0)
    scores_cold = np.full(n_per_stratum, 100.0)
    scores = np.concatenate([scores_norm, scores_cold])
    strata = np.array(["normal"] * n_per_stratum + ["cold"] * n_per_stratum)

    c = calibrate_mondrian(scores, strata, "cold", min_days=10, alpha=0.1)
    # Cold scores are all 100 → correction should be 100
    assert c == pytest.approx(100.0, abs=0.01)


def test_calibrate_mondrian_fallback_on_few_days():
    """When stratum has < min_days calendar days, fall back to global baseline."""
    # 4 "cold" days × 48 = 192 entries (~9% of total), cold score = 100
    # 40 "normal" days × 48 = 1920 entries (~91% of total), normal score = 10
    # Cold fraction < 10%, so global 90th percentile stays in the "normal" range (≈10).
    n_cold = 4 * 48
    n_norm = 40 * 48
    scores_cold = np.full(n_cold, 100.0)
    scores_norm = np.full(n_norm, 10.0)
    scores = np.concatenate([scores_norm, scores_cold])
    strata = np.array(["normal"] * n_norm + ["cold"] * n_cold)

    # 4 cold days (192 // 48 = 4) < min_days=5 → fallback to global (≈10)
    c = calibrate_mondrian(scores, strata, "cold", min_days=5, alpha=0.1)
    expected = calibrate_baseline(scores, alpha=0.1)
    assert c == pytest.approx(expected, abs=1e-6)
    assert c == pytest.approx(10.0, abs=0.1)  # global baseline ≈ 10

    # Confirm it would NOT fall back with min_days=3 (4 ≥ 3) → uses cold scores (≈100)
    c_no_fallback = calibrate_mondrian(scores, strata, "cold", min_days=3, alpha=0.1)
    assert c_no_fallback == pytest.approx(100.0, abs=0.01)
    assert c_no_fallback != pytest.approx(expected, abs=1.0)


# ---------------------------------------------------------------------------
# calibrate_width_normalised tests
# ---------------------------------------------------------------------------

def test_calibrate_width_normalised_level():
    """Width-normalised correction uses the same (1-alpha)(n+1)/n quantile formula."""
    n = 10
    norm_scores = np.linspace(0.1, 1.0, n)  # 0.1, 0.2, ..., 1.0
    c = calibrate_width_normalised(norm_scores, alpha=0.1)
    expected_level = min(1.0, 0.9 * (n + 1) / n)
    assert c == pytest.approx(float(np.quantile(norm_scores, expected_level)), abs=1e-10)


# ---------------------------------------------------------------------------
# select_method tests
# ---------------------------------------------------------------------------

def test_select_method_picks_best_candidate():
    """Selects candidate with best conditional coverage balance; tie-breaks by Winkler."""
    results = {
        "baseline": {
            "coverage_90_all": 90.5,
            "coverage_90_cold": 80.3,
            "coverage_90_high": 82.5,
            "width_90": 5000.0,
            "winkler": 4000.0,
        },
        "mondrian": {
            # Passes all 4 guards; worst conditional distance = max(|90-90|, |86.5-90|) = 3.5
            "coverage_90_all": 90.0,
            "coverage_90_cold": 90.0,   # +9.7 pp over baseline ✓
            "coverage_90_high": 86.5,   # +4.0 pp ✓
            "width_90": 5200.0,         # < 1.25*5000=6250 ✓
            "winkler": 3900.0,
        },
        "width_normalised": {
            # Passes all 4 guards; worst conditional distance = max(|89-90|, |85.5-90|) = 4.5
            "coverage_90_all": 89.5,
            "coverage_90_cold": 89.0,   # +8.7 pp ✓
            "coverage_90_high": 85.5,   # +3.0 pp ✓ (exactly at threshold)
            "width_90": 5100.0,
            "winkler": 3800.0,
        },
    }
    winner = select_method(results)
    # mondrian has better worst-case conditional coverage (3.5 < 4.5)
    assert winner == "mondrian"


def test_select_method_no_passing_candidates_returns_baseline():
    """When no candidate passes all four guards, return 'baseline'."""
    results = {
        "baseline": {
            "coverage_90_all": 90.5,
            "coverage_90_cold": 80.3,
            "coverage_90_high": 82.5,
            "width_90": 5000.0,
            "winkler": 4000.0,
        },
        "mondrian": {
            # Fails rule 2: cold improvement only +2.2 pp (< 3 pp required)
            "coverage_90_all": 91.0,
            "coverage_90_cold": 82.5,
            "coverage_90_high": 86.0,
            "width_90": 5100.0,
            "winkler": 3800.0,
        },
        "width_normalised": {
            # Fails rule 4: width is 1.5× baseline (> 1.25× limit)
            "coverage_90_all": 90.0,
            "coverage_90_cold": 90.0,
            "coverage_90_high": 90.0,
            "width_90": 7500.0,         # 7500 / 5000 = 1.5 > 1.25 ✗
            "winkler": 3500.0,
        },
    }
    assert select_method(results) == "baseline"


# ---------------------------------------------------------------------------
# Helper for apply_calibration_daily tests
# ---------------------------------------------------------------------------

def _make_simple_data(
    n_days: int = 50,
    start: str = "2023-01-01",
    actual: float = 90.0,
    temp_val: float = 10.0,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Return (raw_q, y, temp_series) for apply_calibration_daily tests.

    Quantiles: q05=20, q10=25, q25=35, q50=50, q75=65, q90=75, q95=80 (constant).
    With actual=90 (outside q95=80), the 90% CQR score = max(20-90, 90-80) = 10.
    temp_series uses local date keys (datetime.date).
    """
    n = n_days * 48
    index = pd.date_range(start, periods=n, freq="30min", tz="UTC")
    raw_q = pd.DataFrame(
        {"q05": 20.0, "q10": 25.0, "q25": 35.0, "q50": 50.0,
         "q75": 65.0, "q90": 75.0, "q95": 80.0},
        index=index,
        dtype=float,
    )
    y = pd.Series(actual, index=index)
    local = index.tz_convert("Europe/London")
    temp = pd.Series({d.date(): temp_val for d in local})
    return raw_q, y, temp


# ---------------------------------------------------------------------------
# (a) No look-ahead
# ---------------------------------------------------------------------------

def test_no_lookahead_all_methods():
    """Modifying actuals strictly after the 08:00 D-1 cutoff must not change day D's intervals."""
    raw_q, y, temp = _make_simple_data(n_days=50, actual=90.0, temp_val=10.0)
    days_loc = pd.Series(
        raw_q.index.tz_convert("Europe/London").normalize().tz_localize(None),
        index=raw_q.index,
    )
    D_local = sorted(days_loc.unique())[-1]
    D_rows = raw_q.index[days_loc == D_local]
    # train_cutoff expects a tz-naive timestamp (it localises internally)
    cutoff = task.train_cutoff(pd.Timestamp(D_local))

    for method in ["baseline", "mondrian", "mondrian_extended", "width_normalised"]:
        cal_before = apply_calibration_daily(raw_q, y, temp, method, window_days=30)

        y_mod = y.copy()
        y_mod[y_mod.index > cutoff] = 999_999.0  # wildly different post-cutoff actuals

        cal_after = apply_calibration_daily(raw_q, y_mod, temp, method, window_days=30)

        for col in ["q05", "q95"]:
            np.testing.assert_array_equal(
                cal_before.loc[D_rows, col].values,
                cal_after.loc[D_rows, col].values,
                err_msg=f"method={method!r}, col={col!r}: lookahead detected",
            )


# ---------------------------------------------------------------------------
# (b) Baseline equals existing rolling_cqr
# ---------------------------------------------------------------------------

def test_baseline_matches_rolling_cqr():
    """apply_calibration_daily with method='baseline' reproduces rolling_cqr exactly.

    Uses seeded random quantiles and actuals (varied by half-hour and day), 75 days
    spanning the 2023-03-26 BST spring-forward (clock change), window_days=30.

    Sanity check: window_days=29 (baseline) vs window_days=30 (rolling_cqr) produces
    different output, proving the test is sensitive to the window size.
    """
    rng = np.random.default_rng(42)
    # 75 days starting 2023-02-01 — covers the 26 Mar 2023 BST spring-forward
    n = 75 * 48
    index = pd.date_range("2023-02-01", periods=n, freq="30min", tz="UTC")

    # Monotone quantiles: cumulative increments from a random base
    base = rng.uniform(10_000.0, 20_000.0, size=(n, 1))
    deltas = rng.uniform(50.0, 500.0, size=(n, 6))
    cum = np.hstack([np.zeros((n, 1)), np.cumsum(deltas, axis=1)])  # (n, 7)
    raw_q = pd.DataFrame(
        (base + cum).astype(float),
        columns=["q05", "q10", "q25", "q50", "q75", "q90", "q95"],
        index=index,
    )

    # Actuals vary by half-hour; some fall outside the interval to produce nonzero scores
    y = pd.Series(
        rng.uniform(raw_q["q05"].values * 0.85, raw_q["q95"].values * 1.15),
        index=index,
    )

    # Warm temp proxy (not used by baseline, but required by apply_calibration_daily)
    local = index.tz_convert("Europe/London")
    temp = pd.Series({d.date(): 10.0 for d in pd.DatetimeIndex(pd.unique(local))})

    # apply_from is ≥30 days after start → 30-day window is fully populated
    apply_from = "2023-03-10"

    # --- Main assertion: outputs are identical ---
    cal_b = apply_calibration_daily(
        raw_q, y, temp, "baseline", window_days=30, apply_from=apply_from
    )
    cal_cqr = rolling_cqr(y, raw_q, apply_from=apply_from, window_days=30)

    for lo, hi in [("q05", "q95"), ("q10", "q90"), ("q25", "q75")]:
        np.testing.assert_array_almost_equal(
            cal_b[lo].values, cal_cqr[lo].values, decimal=8,
            err_msg=f"Mismatch on {lo}: baseline vs rolling_cqr",
        )
        np.testing.assert_array_almost_equal(
            cal_b[hi].values, cal_cqr[hi].values, decimal=8,
            err_msg=f"Mismatch on {hi}: baseline vs rolling_cqr",
        )

    # --- Sanity check: window_days=29 (baseline) must differ from window_days=30 (rolling_cqr) ---
    # This proves the test can detect a window-size bug.
    cal_b_29 = apply_calibration_daily(
        raw_q, y, temp, "baseline", window_days=29, apply_from=apply_from
    )
    any_diff = any(
        not np.allclose(cal_b_29[col].values, cal_cqr[col].values)
        for col in ["q05", "q95", "q10", "q90", "q25", "q75"]
    )
    assert any_diff, (
        "Sanity check failed: window_days=29 (baseline) produced the same output as "
        "window_days=30 (rolling_cqr) — the test cannot distinguish a wrong window size"
    )


# ---------------------------------------------------------------------------
# (c) Candidate C extended cold window
# ---------------------------------------------------------------------------

def test_mondrian_extended_uses_and_falls_back():
    """Candidate C uses extended cold scores when ≥20 past cold days exist; falls back otherwise."""
    WD = 30  # small window to keep test fast
    n_warm = WD + 5  # more warm days than WD so the standard window is fully populated

    for n_cold, expect_fallback in [(25, False), (10, True)]:
        n_total = n_cold + n_warm + 1  # +1 for the cold target day D
        n = n_total * 48
        index = pd.date_range("2022-01-01", periods=n, freq="30min", tz="UTC")
        days_loc = pd.Series(
            index.tz_convert("Europe/London").normalize().tz_localize(None),
            index=index,
        )
        unique_days = sorted(days_loc.unique())
        cold_start_days = set(unique_days[:n_cold])
        target_day = unique_days[-1]

        raw_q = pd.DataFrame(
            {"q05": 20.0, "q10": 25.0, "q25": 35.0, "q50": 50.0,
             "q75": 65.0, "q90": 75.0, "q95": 80.0},
            index=index, dtype=float,
        )

        # actual=90 on cold days → 90% score = max(20-90, 90-80) = 10
        # actual=50 on warm days → 90% score = max(20-50, 50-80) = -30
        actual_arr = np.where(days_loc.isin(cold_start_days), 90.0, 50.0)
        actual_arr[days_loc == target_day] = 90.0  # target day also cold
        y = pd.Series(actual_arr.astype(float), index=index)

        temp = pd.Series({
            d.date(): 2.0 if (d in cold_start_days or d == target_day) else 10.0
            for d in unique_days
        })

        target_rows = raw_q.index[days_loc == target_day]

        cal_ext = apply_calibration_daily(raw_q, y, temp, "mondrian_extended", window_days=WD)
        cal_mon = apply_calibration_daily(raw_q, y, temp, "mondrian", window_days=WD)

        q95_ext = cal_ext.loc[target_rows, "q95"].iloc[0]
        q95_mon = cal_mon.loc[target_rows, "q95"].iloc[0]

        if expect_fallback:
            # < 20 past cold days: both fall back to the same global (warm) correction
            assert q95_ext == pytest.approx(q95_mon, abs=0.01), (
                f"n_cold={n_cold}: extended should fall back to same correction as mondrian"
            )
        else:
            # ≥ 20 past cold days: extended uses cold scores (c≈10 → q95≈90)
            assert q95_ext == pytest.approx(90.0, abs=1.0), (
                f"n_cold={n_cold}: extended should use cold scores from outside the window"
            )
            # mondrian: 0 cold days in standard window → falls back to global warm (c≈−30 → q95≈50)
            assert q95_mon == pytest.approx(50.0, abs=1.0), (
                f"n_cold={n_cold}: mondrian should fall back to global (warm) correction"
            )


# ---------------------------------------------------------------------------
# (d) 2026 guard
# ---------------------------------------------------------------------------

def test_load_development_data_2026_guard(monkeypatch):
    """load_development_data raises ValueError when any quantile timestamp is after 2025."""
    idx_2026 = pd.date_range("2026-01-01", periods=48, freq="30min", tz="UTC")
    fake_q = pd.DataFrame(
        {c: 50.0 for c in ["q05", "q10", "q25", "q50", "q75", "q90", "q95"]},
        index=idx_2026,
    )
    monkeypatch.setattr(pd, "read_parquet", lambda path, **kw: fake_q)

    with pytest.raises(ValueError, match="2026"):
        load_development_data()


# ---------------------------------------------------------------------------
# (e) NaN temperature proxy is never cold
# ---------------------------------------------------------------------------

def test_nan_temp_proxy_never_cold():
    """NaN temp proxy must not be classified as 'cold' (NaN < 3 is False in IEEE 754)."""
    # NaN with low demand → "normal"
    result = assign_stratum(None, temp_proxy=np.nan, max_q50=1_000.0, threshold_95=20_000.0)
    assert result == "normal"
    assert result != "cold"

    # NaN with high demand → "high_demand"
    result_high = assign_stratum(None, temp_proxy=np.nan, max_q50=25_000.0, threshold_95=20_000.0)
    assert result_high == "high_demand"
    assert result_high != "cold"

    # float("nan") behaves identically to np.nan
    assert assign_stratum(None, temp_proxy=float("nan"), max_q50=1_000.0, threshold_95=20_000.0) != "cold"
