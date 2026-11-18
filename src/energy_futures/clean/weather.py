"""Turn raw Open-Meteo JSON into half-hourly weather aligned to settlement-period start times (UTC).

Alignment rules (Open-Meteo variable definitions):
- temperature_2m, wind_speed_10m, cloud_cover are instantaneous at the hour -> linear interpolation
  to each half-hour start.
- shortwave_radiation is the mean over the PRECEDING hour, labelled at the hour's end. A period
  starting at HH:00 or HH:30 lies inside the hour labelled HH+1, so it takes that value.
"""
import json
from pathlib import Path

import pandas as pd

INSTANT = ["temperature_2m", "wind_speed_10m", "cloud_cover"]
PRECEDING_HOUR_MEAN = ["shortwave_radiation"]


def load_location(files: list[Path]) -> pd.DataFrame:
    frames = []
    for f in sorted(files):
        h = json.loads(f.read_text())["hourly"]
        frames.append(pd.DataFrame(h).assign(time=lambda d: pd.to_datetime(d["time"], utc=True)))
    df = pd.concat(frames).drop_duplicates("time").set_index("time").sort_index()
    return df


def to_half_hourly(hourly: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    out = pd.DataFrame(index=index)
    full = hourly.reindex(hourly.index.union(index))
    for c in INSTANT:
        if c in hourly:
            out[c] = full[c].interpolate(method="time", limit=1, limit_area="inside").reindex(index)
    for c in PRECEDING_HOUR_MEAN:
        if c in hourly:
            label = index.floor("h") + pd.Timedelta(hours=1)
            out[c] = hourly[c].reindex(label).to_numpy()
    return out


def build(raw_dir: Path, locations: list[str], index: pd.DatetimeIndex) -> tuple[pd.DataFrame, dict]:
    rep, parts = {}, {}
    for name in locations:
        hourly = load_location(list(raw_dir.glob(f"{name}_*.json")))
        hh = to_half_hourly(hourly, index)
        rep[name] = {"hourly_rows": int(len(hourly)), "missing_half_hours": {c: int(hh[c].isna().sum()) for c in hh}}
        parts[name] = hh
    wide = pd.concat({k: v for k, v in parts.items()}, axis=1)
    wide.columns = [f"{var}_{loc}" for loc, var in wide.columns]
    # Equal-weight GB means (population weighting deferred: D-012).
    for var in INSTANT + PRECEDING_HOUR_MEAN:
        cols = [f"{var}_{loc}" for loc in locations if f"{var}_{loc}" in wide]
        if cols:
            wide[f"{var}_gb_mean"] = wide[cols].mean(axis=1, skipna=False)
    return wide, rep
