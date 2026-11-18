"""Parse Batch 4 benchmark inputs into half-hourly UTC series."""
from pathlib import Path

import pandas as pd

from energy_futures.clean import demand as cd
from energy_futures.clean.weather import to_half_hourly

LEAD = "previous_day2"


def neso_day_ahead(path: Path) -> pd.DataFrame:
    """NESO day-ahead ND forecast. Its 'Datetime' column is not a reliable UTC period start, so the
    timestamp is rebuilt from Date + Settlement_Period with the same clock-change logic as the
    demand data."""
    b = pd.read_csv(path, encoding="utf-8-sig")
    dates = pd.to_datetime(b["Date"]).dt.normalize()
    ts = cd.to_utc(dates, b["Settlement_Period"].astype(int))
    out = pd.DataFrame({"neso_forecast": b["Demand_Forecast"].to_numpy(),
                        "neso_outturn": b["Demand_Outturn"].to_numpy(),
                        "neso_published_utc": pd.to_datetime(b["Publish_Datetime"], utc=True).to_numpy()},
                       index=pd.DatetimeIndex(ts, name="timestamp_utc"))
    return out[~out.index.duplicated(keep="last")].sort_index()


def forecast_weather(raw_dir: Path, locations: list[str], index: pd.DatetimeIndex) -> pd.DataFrame:
    """Archived ~48 h-ahead weather forecasts, aligned like the observed weather, GB equal-weight mean."""
    import json
    per_loc = []
    for loc in locations:
        frames = []
        for f in sorted(raw_dir.glob(f"{loc}_*.json")):
            h = pd.DataFrame(json.loads(f.read_text())["hourly"])
            h["time"] = pd.to_datetime(h["time"], utc=True)
            frames.append(h.set_index("time"))
        hourly = pd.concat(frames).sort_index()
        hourly.columns = [c.replace(f"_{LEAD}", "") for c in hourly.columns]
        per_loc.append(to_half_hourly(hourly, index))
    return sum(per_loc) / len(per_loc)   # NaN wherever any location is missing
