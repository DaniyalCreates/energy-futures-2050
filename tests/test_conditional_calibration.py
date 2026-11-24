"""
Tests for CS-2a conditional calibration helpers.
Uses synthetic data only — no real data files needed.
"""

from __future__ import annotations

import numpy as np
import pytest

from energy_futures.experiments.conditional_calibration import (
    assign_stratum,
    calibrate_baseline,
    calibrate_mondrian,
    calibrate_width_normalised,
    select_method,
)


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
