"""Forecasting task definition (Step 17).

Day-ahead task: at ISSUE_HOUR local time on day D-1, forecast every settlement period of local
day D (46/48/50 periods). Matches NESO's first day-ahead publication (09:00-09:15 local).

Information rule: an observation for the half-hour starting at t is treated as available only
from t + 30 min (period end) + PUBLICATION_LAG. Lags used here (same local time on D-2, D-7)
are always available under this rule; `assert_no_leakage` checks it explicitly.
"""
import numpy as np
import pandas as pd

TZ = "Europe/London"
ISSUE_HOUR = 9
PUBLICATION_LAG = pd.Timedelta(minutes=30)
PERIOD = pd.Timedelta(minutes=30)
LAG_DAYS = (2, 7)


def issue_time(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """UTC issue time of the forecast covering each target timestamp."""
    local_day = index.tz_convert(TZ).normalize().tz_localize(None)
    issue_local = local_day - pd.Timedelta(days=1) + pd.Timedelta(hours=ISSUE_HOUR)
    return issue_local.tz_localize(TZ).tz_convert("UTC")


def shifted_local(index: pd.DatetimeIndex, days: int) -> pd.DatetimeIndex:
    """Same local wall-clock time `days` earlier, in UTC. Wall-clock (not UTC) shifting keeps the
    daily profile aligned across clock changes. Ambiguous October hours take BST; non-existent
    March hours shift forward (documented simplification affecting <=2 periods a year)."""
    wall = index.tz_convert(TZ).tz_localize(None) - pd.Timedelta(days=days)
    return wall.tz_localize(TZ, ambiguous=np.ones(len(wall), dtype=bool), nonexistent="shift_forward").tz_convert("UTC")


def lag_features(y: pd.Series, index: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({f"lag_d{k}": y.reindex(shifted_local(index, k)).to_numpy() for k in LAG_DAYS}, index=index)


def assert_no_leakage(index: pd.DatetimeIndex) -> None:
    it = issue_time(index)
    for k in LAG_DAYS:
        avail = shifted_local(index, k) + PERIOD + PUBLICATION_LAG
        bad = int((avail > it).sum())
        if bad:
            raise AssertionError(f"lag_d{k}: {bad} features not available at issue time")


def train_cutoff(first_target_day: pd.Timestamp) -> pd.Timestamp:
    """Latest target timestamp (period start, UTC) whose outcome is known when forecasting
    first_target_day: period end + publication lag <= issue time."""
    it = issue_time(pd.DatetimeIndex([first_target_day.tz_localize(TZ).tz_convert("UTC")]))[0]
    return it - PUBLICATION_LAG - PERIOD
