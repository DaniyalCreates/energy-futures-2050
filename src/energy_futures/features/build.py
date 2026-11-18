"""Feature construction for Batch 4 (Step 24). Every feature is either known in advance (calendar),
observed before the 09:00 D-1 issue time (demand lags/levels), or weather at the target time,
whose source depends on the setting:

    PW  perfect-weather: observed (reanalysis) weather; an upper bound, not a forecast (D-009)
    NW  no weather: realistic for any period
    FW  forecast weather: archived ~48 h-ahead forecasts (2024-2025 only), used at prediction
        time by a model trained on observed weather (standard operational practice)
"""
import numpy as np
import pandas as pd

from energy_futures.features.calendar import calendar_features
from energy_futures.forecast import task

TZ = "Europe/London"
WEATHER_VARS = ["temperature_2m", "wind_speed_10m", "cloud_cover", "shortwave_radiation"]
DEMAND_FEATURES = ["lag_d2", "lag_d7", "lag_d14", "d2_mean", "d2_max", "d7_mean", "level_24h"]
CALENDAR = ["slot", "dow", "month", "is_holiday", "is_xmas_period", "doy_sin", "doy_cos"]
WEATHER_FEATURES = ["temp", "temp_smooth24", "hdd", "cdd", "wind", "cloud", "radiation"]
AVAIL_DELAY = task.PERIOD + task.PUBLICATION_LAG   # period start -> available


def _day_aggregate(y: pd.Series, index: pd.DatetimeIndex, days_back: int, how: str) -> np.ndarray:
    local_day = y.index.tz_convert(TZ).tz_localize(None).normalize()
    agg = y.groupby(local_day).agg(how)
    target_day = index.tz_convert(TZ).tz_localize(None).normalize() - pd.Timedelta(days=days_back)
    return agg.reindex(target_day).to_numpy()


def demand_features(y: pd.Series, index: pd.DatetimeIndex) -> pd.DataFrame:
    X = pd.DataFrame({f"lag_d{k}": y.reindex(task.shifted_local(index, k)).to_numpy() for k in (2, 7, 14)}, index=index)
    X["d2_mean"] = _day_aggregate(y, index, 2, "mean")
    X["d2_max"] = _day_aggregate(y, index, 2, "max")
    X["d7_mean"] = _day_aggregate(y, index, 7, "mean")
    # Mean of the 48 half-hours whose values are available at issue time.
    last_avail_start = task.issue_time(index) - AVAIL_DELAY
    roll = y.rolling(48, min_periods=40).mean()
    X["level_24h"] = roll.reindex(last_avail_start).to_numpy()
    return X


def demand_feature_sources(index: pd.DatetimeIndex) -> dict[str, pd.DatetimeIndex]:
    """Latest source period start used by each demand feature (for the leakage test)."""
    local_midnight = index.tz_convert(TZ).normalize()
    end_of_d2 = (local_midnight.tz_localize(None) - pd.Timedelta(days=1)).tz_localize(TZ).tz_convert("UTC") - task.PERIOD
    return {
        "lag_d2": task.shifted_local(index, 2), "lag_d7": task.shifted_local(index, 7), "lag_d14": task.shifted_local(index, 14),
        "d2_day": end_of_d2, "level_24h": task.issue_time(index) - AVAIL_DELAY,
    }


def weather_features(w: pd.DataFrame) -> pd.DataFrame:
    """w: half-hourly GB-mean weather with columns WEATHER_VARS (any source)."""
    t = w["temperature_2m"]
    return pd.DataFrame({
        "temp": t,
        "temp_smooth24": t.ewm(halflife=12, min_periods=1).mean(),   # building thermal inertia (~6 h half-life)
        "hdd": (15.5 - t).clip(lower=0), "cdd": (t - 18.0).clip(lower=0),
        "wind": w["wind_speed_10m"], "cloud": w["cloud_cover"], "radiation": w["shortwave_radiation"],
    }, index=w.index)


def gb_weather(d: pd.DataFrame) -> pd.DataFrame:
    return d[[f"{v}_gb_mean" for v in WEATHER_VARS]].set_axis(WEATHER_VARS, axis=1)


def build(d: pd.DataFrame, target: str, weather: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.Series]:
    y = d[target]
    cal = calendar_features(d.index)
    doy = d.index.tz_convert(TZ).dayofyear.to_numpy()
    cal["doy_sin"], cal["doy_cos"] = np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
    X = cal.join(demand_features(y, d.index))
    w = gb_weather(d) if weather is None else weather.reindex(d.index)
    X = X.join(weather_features(w))
    return X, y
