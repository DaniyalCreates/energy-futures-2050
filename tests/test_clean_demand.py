"""Cleaning tests on synthetic NESO-shaped data (no network needed)."""
import pandas as pd
import pytest

from energy_futures.clean import demand as cd


def make_day(date: str, n: int, fmt: str = "%Y-%m-%d", nd: int = 30000) -> pd.DataFrame:
    d = pd.Timestamp(date)
    return pd.DataFrame({
        "SETTLEMENT_DATE": [d.strftime(fmt)] * n,
        "SETTLEMENT_PERIOD": range(1, n + 1),
        "ND": [nd] * n, "TSD": [nd + 2000] * n,
        "EMBEDDED_SOLAR_GENERATION": [100] * n, "EMBEDDED_WIND_GENERATION": [200] * n,
        "EMBEDDED_SOLAR_CAPACITY": [15000] * n, "EMBEDDED_WIND_CAPACITY": [6000] * n,
        "SOURCE_FILE": ["demanddata_2024.csv"] * n,
    })


def test_period_counts_follow_clock_changes():
    dates = pd.Series(pd.to_datetime(["2024-03-31", "2024-06-01", "2024-10-27"]))
    assert cd.periods_in_local_day(dates).tolist() == [46, 48, 50]


def test_utc_mapping_on_clock_change_days():
    # Spring forward: local midnight 31 Mar 2024 = 00:00 UTC; period 46 starts 22:30 UTC.
    s = cd.to_utc(pd.Series(pd.to_datetime(["2024-03-31"] * 2)), pd.Series([1, 46]))
    assert s.tolist() == [pd.Timestamp("2024-03-31 00:00", tz="UTC"), pd.Timestamp("2024-03-31 22:30", tz="UTC")]
    # Summer: local midnight 1 Jun = 23:00 UTC previous day.
    s = cd.to_utc(pd.Series(pd.to_datetime(["2024-06-01"])), pd.Series([1]))
    assert s.iloc[0] == pd.Timestamp("2024-05-31 23:00", tz="UTC")


def test_full_clean_produces_continuous_unique_grid_across_clock_changes():
    raw = pd.concat([make_day("2024-03-30", 48), make_day("2024-03-31", 46), make_day("2024-04-01", 48),
                     make_day("2024-10-26", 48), make_day("2024-10-27", 50), make_day("2024-10-28", 48)])
    df, rep = cd.clean(raw)
    assert df.index.is_unique
    # Two separate blocks -> the gap between them is visible as missing slots, not dropped.
    assert rep["missing_slots"] > 0
    assert rep["rows_clean"] == 48 + 46 + 48 + 48 + 50 + 48
    diffs = df.index.to_series().diff().dropna().unique()
    assert list(diffs) == [pd.Timedelta(minutes=30)]


def test_mixed_date_formats_parse():
    raw = pd.concat([make_day("2012-01-01", 48, "%d-%b-%Y"), make_day("2012-01-02", 48, "%Y-%m-%d")])
    df, rep = cd.clean(raw)
    assert rep["rows_unparseable_date"] == 0 and rep["missing_slots"] == 0


def test_invalid_period_is_reported_not_silent():
    day = make_day("2024-06-01", 48)
    bad = day.iloc[[0]].assign(SETTLEMENT_PERIOD=49)
    _, rep = cd.clean(pd.concat([day, bad]))
    assert rep["rows_invalid_period"] == 1


def test_duplicates_and_conflicts_reported_latest_file_wins():
    a = make_day("2024-06-01", 48, nd=30000)
    b = make_day("2024-06-01", 48, nd=31000).assign(SOURCE_FILE="demanddata_2024_update.csv")
    df, rep = cd.clean(pd.concat([a, b]))
    assert rep["duplicate_keys"] == 48 and rep["duplicate_keys_conflicting"] == 48
    assert (df["nd"] == 31000).all()


def test_forecast_rows_removed_and_counted():
    day = make_day("2025-01-01", 48).assign(FORECAST_ACTUAL_INDICATOR="A")
    fc = make_day("2025-01-02", 48).assign(FORECAST_ACTUAL_INDICATOR="F")
    df, rep = cd.clean(pd.concat([day, fc]))
    assert rep["rows_forecast_removed"] == 48
    assert rep["rows_clean"] == 48


def test_underlying_demand_definition():
    df, _ = cd.clean(make_day("2024-06-01", 48))
    assert (df["underlying_demand"] == 30000 + 100 + 200).all()


def test_implausible_values_flagged_not_deleted():
    day = make_day("2024-06-01", 48)
    day.loc[day.index[5], "ND"] = 0
    df, rep = cd.clean(day)
    assert rep["flag_nd_implausible"] == 1 and len(df) == 48
