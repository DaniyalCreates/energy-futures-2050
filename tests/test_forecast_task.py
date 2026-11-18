"""Batch 3 tests: calendar, task timing/leakage, backtest separation, metrics."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from energy_futures.evaluate import backtest
from energy_futures.evaluate.metrics import point_metrics
from energy_futures.features.calendar import bank_holidays_ew, calendar_features
from energy_futures.forecast import task
from energy_futures.forecast.baselines import LinearBaseline, SeasonalNaive


@pytest.mark.parametrize("d", [date(2023, 5, 8), date(2022, 9, 19), date(2020, 5, 8), date(2021, 12, 27),
                               date(2021, 12, 28), date(2022, 6, 2), date(2022, 6, 3), date(2023, 4, 7),
                               date(2024, 8, 26), date(2025, 1, 1)])
def test_known_bank_holidays(d):
    assert d in bank_holidays_ew(d.year)


def test_moved_holidays_removed():
    assert date(2020, 5, 4) not in bank_holidays_ew(2020)
    assert date(2022, 5, 30) not in bank_holidays_ew(2022)
    assert len(bank_holidays_ew(2023)) == 9      # 8 regular + Coronation


def test_issue_time_is_0900_local_previous_day():
    idx = pd.DatetimeIndex(["2024-07-10 12:00", "2024-01-10 12:00"], tz="UTC")
    it = task.issue_time(idx)
    assert list(it) == [pd.Timestamp("2024-07-09 08:00", tz="UTC"), pd.Timestamp("2024-01-09 09:00", tz="UTC")]


def test_lags_keep_local_wall_clock_across_clock_change():
    # Target 12:00 local on 2 Apr 2024 (BST) -> D-7 is 12:00 local on 26 Mar (GMT).
    idx = pd.DatetimeIndex(["2024-04-02 11:00"], tz="UTC")
    assert task.shifted_local(idx, 7)[0] == pd.Timestamp("2024-03-26 12:00", tz="UTC")


def test_no_leakage_on_full_year_including_clock_changes():
    idx = pd.date_range("2023-01-01", "2024-12-31 23:30", freq="30min", tz="UTC")
    task.assert_no_leakage(idx)   # raises if any lag is unavailable at issue time


def test_leakage_check_catches_d1_lag(monkeypatch):
    monkeypatch.setattr(task, "LAG_DAYS", (1,))
    idx = pd.date_range("2023-06-01", periods=48, freq="30min", tz="UTC")
    with pytest.raises(AssertionError):
        task.assert_no_leakage(idx)


def _toy(n_days=60):
    idx = pd.date_range("2023-01-01", periods=48 * n_days, freq="30min", tz="UTC")
    y = pd.Series(30000 + 5000 * np.sin(np.arange(len(idx)) * 2 * np.pi / 48), index=idx)
    X = calendar_features(idx).join(task.lag_features(y, idx))
    return X, y


def test_backtest_training_ends_before_issue_time():
    X, y = _toy()
    p, log = backtest.run(lambda: SeasonalNaive(7), X, y, "2023-02-01", "2023-02-28")
    first_issue = task.issue_time(pd.DatetimeIndex([pd.Timestamp("2023-02-01", tz="Europe/London").tz_convert("UTC")]))[0]
    assert pd.Timestamp(log[0]["train_end_utc"]) + task.PERIOD + task.PUBLICATION_LAG <= first_issue
    assert p.index.min() >= pd.Timestamp("2023-02-01", tz="Europe/London")


def test_naive_on_periodic_series_is_exact():
    X, y = _toy()
    p, _ = backtest.run(lambda: SeasonalNaive(7), X, y, "2023-02-01", "2023-02-28")
    assert np.allclose(p, y.reindex(p.index))


def test_linear_baseline_fits_and_predicts():
    X, y = _toy()
    p, _ = backtest.run(lambda: LinearBaseline(use_weather=False), X, y, "2023-02-01", "2023-02-28")
    assert p.notna().all() and np.abs(p - y.reindex(p.index)).mean() < 1.0


def test_metrics_known_values():
    idx = pd.date_range("2023-06-01", periods=48, freq="30min", tz="UTC")
    y = pd.Series(100.0, index=idx)
    m = point_metrics(y, y + 10, peak_threshold=50)
    assert m["MAE"] == 10 and m["RMSE"] == 10 and m["bias"] == 10 and abs(m["MAPE_pct"] - 10) < 1e-9
    assert m["daily_peak_MAE"] == 10 and m["high_demand_n"] == 48
