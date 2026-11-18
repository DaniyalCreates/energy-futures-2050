"""Batch 4 tests: feature availability (no leakage), quantile ordering, conformal calibration."""
import numpy as np
import pandas as pd
import pytest

from energy_futures.features import build
from energy_futures.forecast import task
from energy_futures.uncertainty.calibration import interval_stats, pinball, rolling_cqr


def test_every_demand_feature_is_available_at_issue_time():
    idx = pd.date_range("2023-01-01", "2024-12-31 23:30", freq="30min", tz="UTC")   # includes 4 clock changes
    issue = task.issue_time(idx)
    for name, src in build.demand_feature_sources(idx).items():
        late = (src + build.AVAIL_DELAY) > issue
        assert not late.any(), f"{name}: {int(late.sum())} rows use data published after the issue time"


def test_level_feature_matches_definition():
    idx = pd.date_range("2023-03-01", periods=48 * 20, freq="30min", tz="UTC")
    y = pd.Series(np.arange(len(idx), dtype=float), index=idx)
    X = build.demand_features(y, idx)
    t = idx[48 * 15]                                     # some target in mid-March
    last = task.issue_time(pd.DatetimeIndex([t]))[0] - build.AVAIL_DELAY
    expected = y.loc[last - pd.Timedelta(minutes=30 * 47): last].mean()
    assert X.loc[t, "level_24h"] == pytest.approx(expected)


def test_d2_aggregates_use_whole_local_day_two_days_before():
    idx = pd.date_range("2024-06-01", periods=48 * 5, freq="30min", tz="UTC")
    y = pd.Series(1.0, index=idx)
    y[(idx.tz_convert("Europe/London").date == pd.Timestamp("2024-06-02").date())] = 5.0
    X = build.demand_features(y, idx)
    on_d4 = idx.tz_convert("Europe/London").date == pd.Timestamp("2024-06-04").date()
    assert (X.loc[on_d4, "d2_mean"] == 5.0).all()


def _quantiles(n=48 * 400, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n, freq="30min", tz="UTC")
    y = pd.Series(rng.normal(0, 1, n), index=idx)
    # Deliberately too narrow quantiles (scale 0.5 instead of 1): raw coverage must be low.
    from scipy.stats import norm
    Q = pd.DataFrame({f"q{int(q*100):02d}": norm.ppf(q) * 0.5 for q in (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95)}, index=idx)
    return y, Q


def test_rolling_cqr_repairs_undercoverage_without_future_data():
    y, Q = _quantiles()
    raw = interval_stats(y["2022-12-01":], Q["2022-12-01":])
    cal = rolling_cqr(y, Q, apply_from="2022-12-01", window_days=300)
    fixed = interval_stats(y.reindex(cal.index), cal)
    assert raw["cover_90"] < 65
    assert abs(fixed["cover_90"] - 90) < 3 and abs(fixed["cover_50"] - 50) < 4
    assert (np.diff(cal.to_numpy(), axis=1) >= 0).all()


def test_pinball_zero_for_perfect_constant():
    idx = pd.date_range("2023-01-01", periods=10, freq="30min", tz="UTC")
    y = pd.Series(5.0, index=idx)
    assert pinball(y, pd.DataFrame({"q50": 5.0, "q90": 5.0}, index=idx)) == 0
