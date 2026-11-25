"""
Tests for cs3_confirmation.py.

Synthetic data only — no real data files are opened.
Tests verify: date guard, coverage_90 metric, _make_verdict logic,
and compute_criteria integration with known synthetic inputs.
"""

from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest

from energy_futures.experiments.cs3_confirmation import (
    HIGH_DEMAND_THRESHOLD_MW,
    _date_guard,
    _make_verdict,
    compute_criteria,
    coverage_90,
)

TZ = "UTC"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_quantiles(
    start: str,
    n_days: int,
    q05: float = 100.0,
    q95: float = 200.0,
    q50: float = 150.0,
    tz: str = "UTC",
) -> pd.DataFrame:
    """Return a minimal quantile DataFrame with n_days × 48 half-hours."""
    idx = pd.date_range(start, periods=n_days * 48, freq="30min", tz=tz)
    return pd.DataFrame(
        {
            "q05": q05,
            "q10": q05 + 10,
            "q25": q05 + 20,
            "q50": q50,
            "q75": q95 - 20,
            "q90": q95 - 10,
            "q95": q95,
        },
        index=idx,
    )


def _make_actuals(idx: pd.Index, value: float = 150.0) -> pd.Series:
    return pd.Series(value, index=idx, dtype=float)


def _make_temp_proxy(dates: list[datetime.date], value: float = 10.0) -> pd.Series:
    return pd.Series({d: value for d in dates}, dtype=float)


# ---------------------------------------------------------------------------
# _date_guard
# ---------------------------------------------------------------------------

class TestDateGuard:
    def test_valid_2026_range_does_not_raise(self):
        """Rows within 2026-01-01..2026-10-31 should pass."""
        q = _make_quantiles("2026-01-01", n_days=10)
        _date_guard(q)  # should not raise

    def test_no_2026_rows_does_not_raise(self):
        """Data with no 2026 rows at all should pass."""
        q = _make_quantiles("2025-01-01", n_days=10)
        _date_guard(q)

    def test_november_2026_raises(self):
        """Rows in November 2026 are outside the allowed window."""
        q = _make_quantiles("2026-11-01", n_days=5)
        with pytest.raises(ValueError, match="date guard"):
            _date_guard(q)

    def test_december_2025_plus_valid_2026_passes(self):
        """Historical rows from 2025 combined with valid 2026 rows should pass."""
        q_hist = _make_quantiles("2025-12-01", n_days=31)
        q_2026 = _make_quantiles("2026-01-01", n_days=10)
        q = pd.concat([q_hist, q_2026]).sort_index()
        _date_guard(q)

    def test_mixed_valid_and_invalid_2026_raises(self):
        """If any 2026 row is outside the window, raise."""
        q_valid = _make_quantiles("2026-01-01", n_days=304)
        q_bad = _make_quantiles("2026-11-01", n_days=2)
        q = pd.concat([q_valid, q_bad]).sort_index()
        with pytest.raises(ValueError, match="date guard"):
            _date_guard(q)


# ---------------------------------------------------------------------------
# coverage_90
# ---------------------------------------------------------------------------

class TestCoverage90:
    def test_all_inside_gives_100(self):
        """When all actuals are inside [q05, q95], coverage should be 100%."""
        q = _make_quantiles("2026-01-01", n_days=10, q05=100.0, q95=200.0)
        y = _make_actuals(q.index, value=150.0)
        cov = coverage_90(q, y)
        assert abs(cov - 100.0) < 1e-6

    def test_none_inside_gives_0(self):
        """When all actuals are outside [q05, q95], coverage should be 0%."""
        q = _make_quantiles("2026-01-01", n_days=10, q05=100.0, q95=200.0)
        y = _make_actuals(q.index, value=300.0)
        cov = coverage_90(q, y)
        assert abs(cov - 0.0) < 1e-6

    def test_half_inside_gives_50(self):
        """Alternating inside/outside should give ~50%."""
        q = _make_quantiles("2026-01-01", n_days=10, q05=100.0, q95=200.0)
        vals = np.where(np.arange(len(q.index)) % 2 == 0, 150.0, 300.0).astype(float)
        y = pd.Series(vals, index=q.index)
        cov = coverage_90(q, y)
        assert abs(cov - 50.0) < 1e-6

    def test_mask_restricts_evaluation(self):
        """Mask should restrict coverage to only the specified rows."""
        q = _make_quantiles("2026-01-01", n_days=10, q05=100.0, q95=200.0)
        y_inside = _make_actuals(q.index, value=150.0)
        # First half inside, second half outside
        second_half = q.index[len(q.index) // 2:]
        y_mixed = y_inside.copy()
        y_mixed[second_half] = 300.0  # outside
        # With mask = first half only: should be 100%
        first_half = q.index[: len(q.index) // 2]
        cov = coverage_90(q, y_mixed, mask=first_half)
        assert abs(cov - 100.0) < 1e-6

    def test_empty_mask_returns_nan(self):
        """Empty mask should return NaN."""
        q = _make_quantiles("2026-01-01", n_days=5)
        y = _make_actuals(q.index)
        empty_mask = q.index[:0]
        cov = coverage_90(q, y, mask=empty_mask)
        assert np.isnan(cov)

    def test_all_nan_actuals_returns_nan(self):
        """All-NaN actuals should return NaN."""
        q = _make_quantiles("2026-01-01", n_days=5)
        y = pd.Series(np.nan, index=q.index)
        cov = coverage_90(q, y)
        assert np.isnan(cov)


# ---------------------------------------------------------------------------
# _make_verdict
# ---------------------------------------------------------------------------

class TestMakeVerdict:
    def test_both_pass_gives_pass(self):
        verdict, _ = _make_verdict(
            cov_jan_feb=90.0, cov_hd=85.0, n_hd=10, cov_jan_oct=90.0, cov_cold=80.0, n_cold=5
        )
        assert verdict == "PASS"

    def test_jan_feb_fail_gives_fail(self):
        verdict, _ = _make_verdict(
            cov_jan_feb=80.0, cov_hd=85.0, n_hd=10, cov_jan_oct=89.0, cov_cold=80.0, n_cold=5
        )
        assert verdict == "FAIL"

    def test_hd_fail_gives_mixed(self):
        """Jan-Feb PASS but high-demand FAIL → MIXED."""
        verdict, _ = _make_verdict(
            cov_jan_feb=90.0, cov_hd=70.0, n_hd=10, cov_jan_oct=89.0, cov_cold=80.0, n_cold=5
        )
        assert verdict == "MIXED"

    def test_both_fail_gives_fail(self):
        verdict, _ = _make_verdict(
            cov_jan_feb=80.0, cov_hd=70.0, n_hd=10, cov_jan_oct=85.0, cov_cold=70.0, n_cold=5
        )
        assert verdict == "FAIL"

    def test_jan_feb_too_high_gives_fail(self):
        """Coverage above 95% also fails (over-width)."""
        verdict, _ = _make_verdict(
            cov_jan_feb=97.0, cov_hd=85.0, n_hd=10, cov_jan_oct=94.0, cov_cold=80.0, n_cold=5
        )
        assert verdict == "FAIL"

    def test_n_hd_too_small_gives_inconclusive(self):
        """n_hd < 5 → co-primary 2 INCONCLUSIVE; verdict depends only on co-primary 1."""
        verdict, reasons = _make_verdict(
            cov_jan_feb=90.0, cov_hd=70.0, n_hd=3, cov_jan_oct=90.0, cov_cold=float("nan"), n_cold=0
        )
        assert "co-primary 1" in verdict.lower() or "PASS" in verdict
        assert "INCONCLUSIVE" in reasons

    def test_nan_jan_feb_gives_inconclusive(self):
        verdict, _ = _make_verdict(
            cov_jan_feb=float("nan"), cov_hd=85.0, n_hd=10, cov_jan_oct=90.0, cov_cold=80.0, n_cold=5
        )
        assert verdict == "INCONCLUSIVE"

    def test_reasons_contain_values(self):
        """Reasons string should include numeric coverage values."""
        _, reasons = _make_verdict(
            cov_jan_feb=90.5, cov_hd=82.1, n_hd=12, cov_jan_oct=89.3, cov_cold=78.0, n_cold=8
        )
        assert "90.5" in reasons
        assert "82.1" in reasons
        assert "n=12" in reasons


# ---------------------------------------------------------------------------
# compute_criteria — integration with synthetic data
# ---------------------------------------------------------------------------

class TestComputeCriteria:
    def _make_scenario(
        self,
        n_days_jan_feb: int = 59,
        n_days_mar_oct: int = 245,
        actual_inside: bool = True,
        q50_high_demand: float = HIGH_DEMAND_THRESHOLD_MW + 1_000,
        cold_temp: float = 1.0,
    ) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
        """Build synthetic 2026 Jan-Oct data with controllable properties."""
        # Jan-Feb
        q_jf = _make_quantiles(
            "2026-01-01", n_days=n_days_jan_feb,
            q05=100.0, q95=200.0, q50=q50_high_demand
        )
        # Mar-Oct
        q_mo = _make_quantiles(
            "2026-03-01", n_days=n_days_mar_oct,
            q05=100.0, q95=200.0, q50=q50_high_demand
        )
        cal_q = pd.concat([q_jf, q_mo]).sort_index()

        y_val = 150.0 if actual_inside else 250.0
        y = _make_actuals(cal_q.index, value=y_val)

        # Build temp_proxy for 2026 Jan-Oct dates
        all_dates = sorted({t.date() for t in cal_q.index.tz_convert("Europe/London")})
        # First 5 days are "cold", rest are mild
        temp_proxy = pd.Series(
            {d: cold_temp if i < 5 else 15.0 for i, d in enumerate(all_dates)},
            dtype=float,
        )
        return cal_q, y, temp_proxy

    def test_all_inside_gives_100_coverage(self):
        """All actuals inside the interval → 100% coverage everywhere.

        Note: 100% > 95% upper bound, so the verdict is FAIL (over-width), not PASS.
        This test only checks the coverage computation is correct.
        """
        cal_q, y, temp_proxy = self._make_scenario(actual_inside=True)
        result = compute_criteria(cal_q, y, temp_proxy)
        assert abs(result["coverage_90_jan_feb"] - 100.0) < 1e-6
        assert abs(result["coverage_90_jan_oct"] - 100.0) < 1e-6
        # 100% > 95% upper bound → co-primary 1 fails
        assert result["verdict"] == "FAIL"

    def test_90_pct_coverage_with_high_demand_gives_pass(self):
        """~90% Jan-Feb coverage and high-demand coverage above 80% → PASS."""
        # Build synthetic data where roughly 90% of Jan-Feb half-hours are inside
        q_jf = _make_quantiles(
            "2026-01-01", n_days=59, q05=100.0, q95=200.0,
            q50=HIGH_DEMAND_THRESHOLD_MW + 1_000
        )
        q_mo = _make_quantiles(
            "2026-03-01", n_days=245, q05=100.0, q95=200.0,
            q50=HIGH_DEMAND_THRESHOLD_MW + 1_000
        )
        cal_q = pd.concat([q_jf, q_mo]).sort_index()

        # 90% inside, 10% outside (cycle every 10 half-hours)
        vals = np.where(np.arange(len(cal_q)) % 10 == 0, 250.0, 150.0).astype(float)
        y = pd.Series(vals, index=cal_q.index)

        all_dates = sorted({t.date() for t in cal_q.index.tz_convert("Europe/London")})
        temp_proxy = pd.Series({d: 15.0 for d in all_dates}, dtype=float)

        result = compute_criteria(cal_q, y, temp_proxy)
        # Expect ~90% coverage everywhere → PASS
        assert 85.0 <= result["coverage_90_jan_feb"] <= 95.0
        assert result["coverage_90_high_demand"] >= 80.0
        assert result["verdict"] == "PASS"

    def test_all_outside_gives_0_coverage_fail(self):
        """All actuals outside the interval → 0% coverage everywhere → FAIL."""
        cal_q, y, temp_proxy = self._make_scenario(actual_inside=False)
        result = compute_criteria(cal_q, y, temp_proxy)
        assert abs(result["coverage_90_jan_feb"] - 0.0) < 1e-6
        assert result["verdict"] == "FAIL"

    def test_high_demand_days_identified_by_threshold(self):
        """Days with q50 above threshold should be classified as high-demand."""
        cal_q, y, temp_proxy = self._make_scenario(
            q50_high_demand=HIGH_DEMAND_THRESHOLD_MW + 1_000, actual_inside=True
        )
        result = compute_criteria(cal_q, y, temp_proxy)
        # All days have q50 above threshold, so n_hd should equal total days
        expected_days = len(cal_q.index.tz_convert("Europe/London").normalize().unique())
        assert result["n_high_demand_days"] == expected_days

    def test_low_q50_no_high_demand_days(self):
        """Days with q50 below threshold should not be counted as high-demand."""
        cal_q, y, temp_proxy = self._make_scenario(
            q50_high_demand=HIGH_DEMAND_THRESHOLD_MW - 1_000, actual_inside=True
        )
        result = compute_criteria(cal_q, y, temp_proxy)
        assert result["n_high_demand_days"] == 0

    def test_cold_days_counted_from_temp_proxy(self):
        """Days with temp_proxy < 3°C should be counted as cold days."""
        cal_q, y, temp_proxy = self._make_scenario(cold_temp=1.0)
        result = compute_criteria(cal_q, y, temp_proxy)
        # We set first 5 days to cold (temp=1.0), rest to 15.0
        assert result["n_cold_days"] == 5

    def test_no_cold_days_when_all_mild(self):
        """No cold days when all temps are well above threshold."""
        cal_q, y, temp_proxy = self._make_scenario(cold_temp=15.0)
        result = compute_criteria(cal_q, y, temp_proxy)
        assert result["n_cold_days"] == 0

    def test_result_contains_required_keys(self):
        """Result dict must contain all required keys."""
        cal_q, y, temp_proxy = self._make_scenario()
        result = compute_criteria(cal_q, y, temp_proxy)
        required = {
            "coverage_90_jan_feb", "coverage_90_jan_oct",
            "coverage_90_high_demand", "coverage_90_cold",
            "n_high_demand_days", "n_cold_days", "verdict", "reasons",
        }
        assert required.issubset(result.keys())

    def test_verdict_is_one_of_expected_values(self):
        cal_q, y, temp_proxy = self._make_scenario()
        result = compute_criteria(cal_q, y, temp_proxy)
        # Verdict starts with one of the allowed labels
        allowed = {"PASS", "FAIL", "MIXED", "INCONCLUSIVE"}
        assert any(result["verdict"].startswith(a) for a in allowed)
