"""Weather alignment tests: no look-ahead beyond the documented variable definitions."""
import pandas as pd

from energy_futures.clean.weather import to_half_hourly


def hourly():
    idx = pd.date_range("2024-01-01 00:00", periods=4, freq="h", tz="UTC")
    return pd.DataFrame({"temperature_2m": [0.0, 2.0, 4.0, 6.0],
                         "shortwave_radiation": [10.0, 20.0, 30.0, 40.0]}, index=idx)


def test_instantaneous_variables_interpolated():
    idx = pd.date_range("2024-01-01 00:00", periods=5, freq="30min", tz="UTC")
    out = to_half_hourly(hourly(), idx)
    assert out["temperature_2m"].tolist() == [0.0, 1.0, 2.0, 3.0, 4.0]


def test_radiation_uses_hour_containing_the_period():
    # Period 00:00-00:30 and 00:30-01:00 lie inside the hour labelled 01:00 (value 20).
    idx = pd.date_range("2024-01-01 00:00", periods=4, freq="30min", tz="UTC")
    out = to_half_hourly(hourly(), idx)
    assert out["shortwave_radiation"].tolist() == [20.0, 20.0, 30.0, 30.0]


def test_no_extrapolation_beyond_data():
    idx = pd.date_range("2024-01-01 03:00", periods=3, freq="30min", tz="UTC")
    out = to_half_hourly(hourly(), idx)
    assert out["temperature_2m"].isna().sum() == 2  # 03:30 and 04:00 have no bracketing data
