"""Clean NESO Historic Demand Data.

Principles: nothing is silently dropped. Every removed or questionable row is counted in the
quality report, and every gap stays visible as NaN plus a flag (never interpolated here).
"""
from pathlib import Path

import numpy as np
import pandas as pd

TZ = "Europe/London"
NUMERIC = ["ND", "TSD", "ENGLAND_WALES_DEMAND", "EMBEDDED_WIND_GENERATION", "EMBEDDED_WIND_CAPACITY",
           "EMBEDDED_SOLAR_GENERATION", "EMBEDDED_SOLAR_CAPACITY", "NON_BM_STOR", "PUMP_STORAGE_PUMPING"]
DATE_FORMATS = ["%Y-%m-%d", "%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]


def parse_dates(s: pd.Series) -> pd.Series:
    """Parse settlement dates. NESO files use several formats; each value must match one
    known format exactly, otherwise it becomes NaT and is reported."""
    s = s.astype(str).str.strip()
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for fmt in DATE_FORMATS:
        todo = out.isna()
        if not todo.any():
            break
        out[todo] = pd.to_datetime(s[todo], format=fmt, errors="coerce")
    return out.dt.normalize()


def periods_in_local_day(dates: pd.Series) -> pd.Series:
    """Number of half-hour settlement periods in each local (Europe/London) day: 46, 48 or 50."""
    d = pd.DatetimeIndex(dates)
    start = d.tz_localize(TZ)
    end = (d + pd.Timedelta(days=1)).tz_localize(TZ)
    return pd.Series(((end - start) / pd.Timedelta(minutes=30)).astype(int), index=dates.index)


def to_utc(dates: pd.Series, periods: pd.Series) -> pd.Series:
    """Start time (UTC) of a settlement period: local midnight + (period-1) x 30 min.
    UK clock changes happen at 01:00/02:00, so local midnight is never ambiguous."""
    midnight = pd.DatetimeIndex(dates).tz_localize(TZ).tz_convert("UTC")
    return pd.Series(midnight + pd.to_timedelta((periods.to_numpy() - 1) * 30, unit="min"), index=dates.index)


def load_raw(files: list[Path]) -> pd.DataFrame:
    frames = []
    for f in sorted(files):
        df = pd.read_csv(f, low_memory=False)
        df.columns = [c.strip().upper() for c in df.columns]
        df["SOURCE_FILE"] = f.name
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rep: dict = {"rows_raw": int(len(raw))}
    df = raw.copy()

    # 1. Forecast rows (some recent files mix actuals 'A' with forecasts 'F'): exclude, count.
    if "FORECAST_ACTUAL_INDICATOR" in df.columns:
        is_fc = df["FORECAST_ACTUAL_INDICATOR"].astype(str).str.strip().str.upper().eq("F")
        rep["rows_forecast_removed"] = int(is_fc.sum())
        df = df[~is_fc]
    else:
        rep["rows_forecast_removed"] = 0

    # 2. Dates and periods.
    df["settlement_date"] = parse_dates(df["SETTLEMENT_DATE"])
    df["settlement_period"] = pd.to_numeric(df["SETTLEMENT_PERIOD"], errors="coerce")
    bad_date = df["settlement_date"].isna()
    rep["rows_unparseable_date"] = int(bad_date.sum())
    df = df[~bad_date]
    df["periods_expected"] = periods_in_local_day(df["settlement_date"])
    bad_p = df["settlement_period"].isna() | (df["settlement_period"] < 1) | (df["settlement_period"] > df["periods_expected"])
    rep["rows_invalid_period"] = int(bad_p.sum())
    rep["invalid_period_examples"] = df.loc[bad_p, ["SETTLEMENT_DATE", "SETTLEMENT_PERIOD", "SOURCE_FILE"]].head(10).astype(str).to_dict("records")
    df = df[~bad_p]
    df["settlement_period"] = df["settlement_period"].astype(int)

    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce") if c in df.columns else np.nan

    # 3. Duplicates on (date, period): identical values -> keep one; conflicting -> keep the
    #    row from the latest source file (most recent publication) and report.
    key = ["settlement_date", "settlement_period"]
    dup = df.duplicated(key, keep=False)
    if dup.any():
        d = df[dup]
        n_conflict = int((d.groupby(key)[["ND", "TSD"]].nunique(dropna=False) > 1).any(axis=1).sum())
    else:
        n_conflict = 0
    rep["duplicate_keys"] = int(df[dup].groupby(key).ngroups) if dup.any() else 0
    rep["duplicate_keys_conflicting"] = n_conflict
    df = df.sort_values(key + ["SOURCE_FILE"]).drop_duplicates(key, keep="last")

    # 4. UTC timestamps on a complete half-hourly grid; gaps stay as NaN and are flagged.
    df["timestamp_utc"] = to_utc(df["settlement_date"], df["settlement_period"])
    df = df.set_index("timestamp_utc").sort_index()
    assert df.index.is_unique, "UTC timestamps not unique after de-duplication"
    grid = pd.date_range(df.index.min(), df.index.max(), freq="30min", tz="UTC", name="timestamp_utc")
    rep["grid_slots"] = int(len(grid))
    df = df.reindex(grid)
    df["flag_missing_row"] = df["ND"].isna() & df["SOURCE_FILE"].isna()
    rep["missing_slots"] = int(df["flag_missing_row"].sum())
    rep["missing_values"] = {c: int(df[c].isna().sum()) for c in NUMERIC}

    # 5. Plausibility flags (flag, never delete). GB ND has been ~13-60 GW since 2009.
    df["flag_nd_implausible"] = (df["ND"] <= 5_000) | (df["ND"] > 70_000)
    df["flag_embedded_negative"] = (df["EMBEDDED_SOLAR_GENERATION"] < 0) | (df["EMBEDDED_WIND_GENERATION"] < 0)
    df["flag_solar_above_capacity"] = df["EMBEDDED_SOLAR_GENERATION"] > df["EMBEDDED_SOLAR_CAPACITY"]
    for f in ["flag_nd_implausible", "flag_embedded_negative", "flag_solar_above_capacity"]:
        rep[f] = int(df[f].sum())

    # 6. Candidate targets (decision D-010): underlying demand adds back estimated embedded generation.
    df["underlying_demand"] = df["ND"] + df["EMBEDDED_SOLAR_GENERATION"] + df["EMBEDDED_WIND_GENERATION"]

    rep["rows_clean"] = int(df["ND"].notna().sum())
    rep["start_utc"], rep["end_utc"] = str(df.index.min()), str(df.index.max())
    keep = ["settlement_date", "settlement_period", *NUMERIC, "underlying_demand", "SOURCE_FILE",
            "flag_missing_row", "flag_nd_implausible", "flag_embedded_negative", "flag_solar_above_capacity"]
    return df[keep].rename(columns=str.lower), rep
