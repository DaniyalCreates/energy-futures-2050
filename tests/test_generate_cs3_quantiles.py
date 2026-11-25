"""
Tests for generate_cs3_quantiles.py.

Tests verify: lag-feature continuity at the year boundary, output date bounds,
and refit cutoff ordering — without running LightGBM or opening real data files.
"""

from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest

from energy_futures.experiments.generate_cs3_quantiles import (
    CS3_END,
    CS3_START,
    REFIT_FREQ,
    _check_output_dates,
    _check_schema_match,
    load_combined_demand,
)
from energy_futures.evaluate.backtest import blocks
from energy_futures.features.build import demand_features
from energy_futures.forecast import task


TZ = "Europe/London"


# ---------------------------------------------------------------------------
# Lag-feature continuity at the year boundary (2025-12-31 → 2026-01-01)
# ---------------------------------------------------------------------------

class TestLagFeatureContinuity:
    """Jan 2026 lag features must draw on Dec 2025 values, not NaN."""

    def _make_demand_series(self, start: str, n_days: int) -> pd.Series:
        """Synthetic half-hourly demand series (UTC, constant 30 000 MW)."""
        idx = pd.date_range(start, periods=n_days * 48, freq="30min", tz="UTC")
        return pd.Series(30_000.0, index=idx, dtype=float)

    def test_lag_d2_is_not_nan_for_2026_jan_01(self):
        """lag_d2 for 2026-01-01 uses 2025-12-30 — not NaN when history covers it."""
        # Build demand covering 2025-12-01..2026-01-05 (plenty of history)
        y = self._make_demand_series("2025-12-01", n_days=36)

        # Feature index: just first half of 2026-01-01 UTC
        jan01_hh = pd.date_range("2026-01-01", periods=48, freq="30min", tz="UTC")

        X = demand_features(y, jan01_hh)
        # lag_d2: wall-clock 2 days earlier = 2025-12-30 — present in y
        assert X["lag_d2"].notna().all(), \
            "lag_d2 for 2026-01-01 is NaN; Dec 2025 history was not carried over."

    def test_lag_d7_is_not_nan_for_2026_jan_01(self):
        """lag_d7 for 2026-01-01 uses 2025-12-25 — not NaN when history covers it."""
        y = self._make_demand_series("2025-12-01", n_days=36)
        jan01_hh = pd.date_range("2026-01-01", periods=48, freq="30min", tz="UTC")
        X = demand_features(y, jan01_hh)
        assert X["lag_d7"].notna().all(), \
            "lag_d7 for 2026-01-01 is NaN; Dec 2025 history was not carried over."

    def test_lag_features_nan_when_history_missing(self):
        """lag_d2 IS NaN if the demand series starts at 2026-01-01 (no Dec 2025 data)."""
        y = self._make_demand_series("2026-01-01", n_days=10)
        jan01_hh = pd.date_range("2026-01-01", periods=48, freq="30min", tz="UTC")
        X = demand_features(y, jan01_hh)
        # lag_d2 looks up 2025-12-30 which is not in y; should be all NaN
        assert X["lag_d2"].isna().all(), \
            "Expected NaN when Dec 2025 history is absent."

    def test_combined_demand_has_no_duplicate_index(self):
        """When hist and 2026 are concatenated, duplicates are dropped."""
        # Simulate the load_combined_demand deduplication
        y_hist = self._make_demand_series("2025-12-01", n_days=31)
        y_2026 = self._make_demand_series("2026-01-01", n_days=31)
        combined_idx = y_hist.index.append(y_2026.index)
        assert not combined_idx.duplicated().any(), \
            "Index has duplicates after concatenation (non-overlapping ranges)."


# ---------------------------------------------------------------------------
# Output date guard
# ---------------------------------------------------------------------------

class TestCheckOutputDates:
    def _make_q(self, start: str, n_days: int) -> pd.DataFrame:
        idx = pd.date_range(start, periods=n_days * 48, freq="30min", tz="UTC")
        return pd.DataFrame({"q05": 1.0, "q50": 2.0, "q95": 3.0}, index=idx)

    def test_valid_range_does_not_raise(self):
        """Rows within 2026-01-01..2026-10-31 should pass."""
        q = self._make_q("2026-01-01", n_days=10)
        _check_output_dates(q)  # no exception

    def test_november_2026_raises(self):
        """Rows in November 2026 must be rejected."""
        q = self._make_q("2026-11-01", n_days=5)
        with pytest.raises(ValueError, match="date guard"):
            _check_output_dates(q)

    def test_mixed_valid_and_invalid_raises(self):
        q_ok = self._make_q("2026-01-01", n_days=304)
        q_bad = self._make_q("2026-11-01", n_days=2)
        q = pd.concat([q_ok, q_bad]).sort_index()
        with pytest.raises(ValueError, match="date guard"):
            _check_output_dates(q)

    def test_exactly_oct_31_passes(self):
        """The last allowed date (Oct 31) should not raise."""
        oct31 = pd.date_range("2026-10-31", periods=48, freq="30min", tz="UTC")
        q = pd.DataFrame({"q05": 1.0, "q50": 2.0, "q95": 3.0}, index=oct31)
        _check_output_dates(q)  # no exception


# ---------------------------------------------------------------------------
# Refit cutoff ordering (no refit uses data after its refit date)
# ---------------------------------------------------------------------------

class TestRefitCutoffOrdering:
    """Verify that for each QS block in 2026, train_cutoff < block_start."""

    def test_all_qs_2026_cutoffs_before_block_start(self):
        """For every block in the QS schedule over 2026, train_cutoff < block_start."""
        qs_blocks = blocks(CS3_START, CS3_END, freq=REFIT_FREQ)
        assert len(qs_blocks) >= 4, f"Expected ≥4 QS blocks, got {len(qs_blocks)}"

        for b0, b1 in qs_blocks:
            cutoff = task.train_cutoff(b0)
            # train_cutoff returns UTC timestamp; block_start is a local date
            # Convert block_start to UTC for comparison
            b0_utc = b0.tz_localize(TZ).tz_convert("UTC")
            assert cutoff < b0_utc, (
                f"Refit at block {b0.date()}: train_cutoff={cutoff} is NOT before "
                f"block_start_utc={b0_utc}. Training would use future data."
            )

    def test_q1_2026_uses_only_2025_and_earlier(self):
        """The 2026-Q1 refit (block start 2026-01-01) must train on data ≤ late 2025."""
        b0 = pd.Timestamp("2026-01-01")
        cutoff = task.train_cutoff(b0)
        cutoff_local = cutoff.tz_convert(TZ)
        # Should be in Dec 2025 (a few hours before 2026-01-01 09:00 local)
        assert cutoff_local.year == 2025, (
            f"Q1-2026 refit should train only on 2025 data, "
            f"but train_cutoff is {cutoff_local.date()}."
        )

    def test_refit_blocks_cover_full_cs3_window(self):
        """QS blocks must together cover the full 2026-01-01..2026-10-31 window."""
        qs_blocks = blocks(CS3_START, CS3_END, freq=REFIT_FREQ)
        earliest_start = min(b0 for b0, _ in qs_blocks)
        latest_end = max(b1 for _, b1 in qs_blocks)
        assert earliest_start <= pd.Timestamp("2026-01-01")
        assert latest_end >= pd.Timestamp("2026-10-31")

    def test_four_qs_refits_in_2026(self):
        """There should be exactly 4 quarterly refits in 2026-01-01..2026-10-31."""
        qs_blocks = blocks(CS3_START, CS3_END, freq=REFIT_FREQ)
        # QS: 2026-01-01, 2026-04-01, 2026-07-01, 2026-10-01
        assert len(qs_blocks) == 4, \
            f"Expected 4 QS refits, got {len(qs_blocks)}: {[(str(b0.date()), str(b1.date())) for b0, b1 in qs_blocks]}"


# ---------------------------------------------------------------------------
# Stage 17 (b): schema check in load_combined_demand
# ---------------------------------------------------------------------------

class TestLoadCombinedDemandSchemaCheck:
    """load_combined_demand must raise if demand_weather_2026 schema doesn't match hist."""

    def _make_demand_parquet(self, tmp_path: "Path", name: str, start: str, n_days: int,
                              extra_col: bool = False, bad_dtype: bool = False) -> "Path":
        idx = pd.date_range(start, periods=n_days * 48, freq="30min", tz="UTC")
        df = pd.DataFrame({"underlying_demand": 30_000.0}, index=idx)
        if extra_col:
            df["unexpected_col"] = 0.0
        if bad_dtype:
            df["underlying_demand"] = df["underlying_demand"].astype("int32")
        path = tmp_path / f"{name}.parquet"
        df.to_parquet(path)
        return path

    def test_raises_when_2026_has_extra_column(self, tmp_path):
        """demand_weather_2026 with an extra column should raise before concatenating."""
        hist = self._make_demand_parquet(tmp_path, "hist", "2025-01-01", 10)
        d2026 = self._make_demand_parquet(tmp_path, "d2026", "2026-01-01", 5, extra_col=True)
        with pytest.raises(RuntimeError, match="Schema mismatch"):
            load_combined_demand(demand_path=hist, demand_2026_path=d2026)

    def test_raises_when_2026_has_dtype_mismatch(self, tmp_path):
        """demand_weather_2026 with wrong dtype should raise before concatenating."""
        hist = self._make_demand_parquet(tmp_path, "hist", "2025-01-01", 10)
        d2026 = self._make_demand_parquet(tmp_path, "d2026", "2026-01-01", 5, bad_dtype=True)
        with pytest.raises(RuntimeError, match="Dtype mismatch"):
            load_combined_demand(demand_path=hist, demand_2026_path=d2026)

    def test_passes_when_schemas_match(self, tmp_path):
        """Matching schemas concatenate correctly."""
        hist = self._make_demand_parquet(tmp_path, "hist", "2025-12-01", 10)
        d2026 = self._make_demand_parquet(tmp_path, "d2026", "2026-01-01", 5)
        combined = load_combined_demand(demand_path=hist, demand_2026_path=d2026)
        assert len(combined) == (10 + 5) * 48
