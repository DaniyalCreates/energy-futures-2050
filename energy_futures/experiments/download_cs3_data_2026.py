"""
CS-3 data download scripts.

STATUS: committed BEFORE any run. These functions MUST NOT be called until
Dani approves docs/cs3_protocol.md (§2).

Three functions (all restricted to 2026-01-01..2026-10-31):

  demand_2026()          Download NESO historic demand 2026 raw CSV, download
                         ERA5 actual weather 2026, process both, and save
                         data/processed/demand_weather_2026.parquet.

  forecast_weather_2026() Download Open-Meteo Previous Runs API (previous_day2)
                          for 6 cities, 2026-01-01..2026-10-31, writing
                          data/raw/weather_forecast/{city}_2026.json.

  download_all()         Run both in order.

Protocol: docs/cs3_protocol.md §10.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[2]

# --- Paths ---
RAW_NESO_DIR      = REPO / "data" / "raw" / "neso"
RAW_WEATHER_DIR   = REPO / "data" / "raw" / "weather"
RAW_FORECAST_DIR  = REPO / "data" / "raw" / "weather_forecast"
PROCESSED_DIR     = REPO / "data" / "processed"
MANIFEST_PATH     = REPO / "data" / "raw" / "manifest.csv"

DEMAND_2026_OUT   = PROCESSED_DIR / "demand_weather_2026.parquet"

# --- Constants ---
NESO_API_BASE = "https://api.neso.energy/api/3/action"
NESO_DATASET  = "historic-demand-data"
ERA5_API_URL  = "https://archive-api.open-meteo.com/v1/archive"
PREV_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
LEAD          = "previous_day2"

CS3_START = "2026-01-01"
CS3_END   = "2026-10-31"
YEAR_2026 = 2026

HOURLY_VARS = [
    "temperature_2m",
    "wind_speed_10m",
    "cloud_cover",
    "shortwave_radiation",
]

LOCATIONS = {
    "london":     {"lat": 51.507, "lon": -0.128},
    "birmingham": {"lat": 52.486, "lon": -1.890},
    "manchester": {"lat": 53.481, "lon": -2.243},
    "newcastle":  {"lat": 54.978, "lon": -1.618},
    "glasgow":    {"lat": 55.864, "lon": -4.252},
    "cardiff":    {"lat": 51.481, "lon": -3.179},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_with_retry(url: str, params: dict, n_retry: int = 4) -> requests.Response:
    for attempt in range(n_retry):
        resp = requests.get(url, params=params, timeout=180)
        if resp.status_code == 429:
            time.sleep(30 * (attempt + 1))
            continue
        resp.raise_for_status()
        return resp
    raise RuntimeError(f"Rate-limited after {n_retry} attempts: {url}")


def _write_manifest(dest: Path, source: str, url: str, notes: str = "") -> None:
    """Append a row to the raw data manifest."""
    import csv
    import hashlib
    import datetime
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "file": str(dest.relative_to(REPO)),
        "source": source,
        "url": url[:200],
        "sha256": hashlib.sha256(dest.read_bytes()).hexdigest()[:16],
        "downloaded_utc": datetime.datetime.utcnow().isoformat(timespec="seconds"),
        "notes": notes,
    }
    write_header = not MANIFEST_PATH.exists()
    with open(MANIFEST_PATH, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row.keys()))
        if write_header:
            w.writeheader()
        w.writerow(row)


# ---------------------------------------------------------------------------
# NESO 2026 raw CSV
# ---------------------------------------------------------------------------

def _neso_list_resources() -> dict[int, str]:
    """Return {year: url} mapping from NESO CKAN API."""
    import re
    year_re = re.compile(r"historic demand data\s+(\d{4})", re.I)
    r = requests.get(
        f"{NESO_API_BASE}/package_show",
        params={"id": NESO_DATASET},
        timeout=60,
    )
    r.raise_for_status()
    out = {}
    for res in r.json()["result"]["resources"]:
        m = year_re.search(res.get("name", ""))
        if m and str(res.get("format", "")).upper() == "CSV":
            out[int(m.group(1))] = res["url"]
    return out


def _download_neso_2026_raw(force: bool = False) -> Path:
    """Download NESO historic demand 2026 CSV to data/raw/neso/demanddata_2026.csv."""
    RAW_NESO_DIR.mkdir(parents=True, exist_ok=True)
    dest = RAW_NESO_DIR / "demanddata_2026.csv"
    if dest.exists() and not force:
        print(f"  skip {dest.name} (exists)")
        return dest
    resources = _neso_list_resources()
    if YEAR_2026 not in resources:
        raise RuntimeError(
            f"NESO resource for year {YEAR_2026} not found. "
            f"Available years: {sorted(resources)}"
        )
    url = resources[YEAR_2026]
    resp = _get_with_retry(url, {})
    dest.write_bytes(resp.content)
    _write_manifest(dest, "NESO Historic Demand Data 2026", url)
    print(f"  got {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


# ---------------------------------------------------------------------------
# ERA5 actual weather 2026
# ---------------------------------------------------------------------------

def _download_era5_weather_2026(force: bool = False) -> None:
    """Download ERA5 actual weather for 2026-01-01..2026-10-31 (6 cities)."""
    RAW_WEATHER_DIR.mkdir(parents=True, exist_ok=True)
    for name, loc in LOCATIONS.items():
        dest = RAW_WEATHER_DIR / f"{name}_{YEAR_2026}.json"
        if dest.exists() and not force:
            print(f"  skip ERA5 {name} {YEAR_2026} (exists)")
            continue
        params = {
            "latitude": loc["lat"],
            "longitude": loc["lon"],
            "start_date": CS3_START,
            "end_date": CS3_END,
            "hourly": ",".join(HOURLY_VARS),
            "timezone": "GMT",
        }
        resp = _get_with_retry(ERA5_API_URL, params)
        raw = resp.json()
        missing = [v for v in HOURLY_VARS if v not in raw.get("hourly", {})]
        if missing:
            raise RuntimeError(f"ERA5 API did not return {missing} for {name}")
        dest.write_text(json.dumps(raw))
        _write_manifest(dest, "Open-Meteo ERA5 Archive 2026", resp.url, notes=f"{name} {YEAR_2026}")
        time.sleep(0.5)
        print(f"  ERA5 {name} {YEAR_2026}: done")


# ---------------------------------------------------------------------------
# Demand + weather processing
# ---------------------------------------------------------------------------

def _build_demand_weather_2026(neso_path: Path) -> None:
    """Process NESO 2026 CSV + ERA5 2026 weather → demand_weather_2026.parquet.

    Applies the same cleaning logic as the main pipeline (pipeline.py::build).
    Restricts output strictly to 2026-01-01..2026-10-31.
    """
    import sys
    sys.path.insert(0, str(REPO))
    import pandas as pd
    from energy_futures.clean import demand as cd
    from energy_futures.clean import weather as cw

    # --- Demand ---
    raw = cd.load_raw([neso_path])
    demand, drep = cd.clean(raw)
    if drep["rows_unparseable_date"] or drep["rows_invalid_period"]:
        raise RuntimeError(
            f"2026 demand CSV has parse errors: "
            f"{drep['rows_unparseable_date']} unparseable dates, "
            f"{drep['rows_invalid_period']} invalid periods."
        )

    # Restrict to 2026-01-01..2026-10-31
    lo = pd.Timestamp("2026-01-01", tz="UTC")
    hi = pd.Timestamp("2026-10-31 23:59:59", tz="UTC")
    demand = demand[(demand.index >= lo) & (demand.index <= hi)]
    if demand.empty:
        raise RuntimeError("No demand rows found in 2026-01-01..2026-10-31 after cleaning.")

    # --- Weather ---
    era5_files = list(RAW_WEATHER_DIR.glob(f"*_{YEAR_2026}.json"))
    if era5_files:
        locs = list(LOCATIONS.keys())
        wx, _ = cw.build(RAW_WEATHER_DIR, locs, demand.index)
        # Only keep gb_mean columns that exist in the standard demand_weather.parquet
        gb_cols = [c for c in wx.columns if c.endswith("_gb_mean")]
        merged = demand.join(wx[gb_cols])
    else:
        print("  WARNING: no ERA5 2026 weather files found; saving demand only.")
        merged = demand

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(DEMAND_2026_OUT)
    print(f"  demand_weather_2026.parquet: {len(merged):,} rows → {DEMAND_2026_OUT}")


# ---------------------------------------------------------------------------
# Open-Meteo previous_day2 forecast 2026
# ---------------------------------------------------------------------------

def _download_forecast_weather_2026(force: bool = False) -> None:
    """Download previous_day2 archived forecast for 2026-01-01..2026-10-31 (6 cities)."""
    RAW_FORECAST_DIR.mkdir(parents=True, exist_ok=True)
    hourly_forecast = [f"{v}_{LEAD}" for v in HOURLY_VARS]
    for name, loc in LOCATIONS.items():
        dest = RAW_FORECAST_DIR / f"{name}_{YEAR_2026}.json"
        if dest.exists() and not force:
            print(f"  skip forecast {name} {YEAR_2026} (exists)")
            continue
        params = {
            "latitude": loc["lat"],
            "longitude": loc["lon"],
            "start_date": CS3_START,
            "end_date": CS3_END,
            "hourly": ",".join(hourly_forecast),
            "timezone": "GMT",
        }
        resp = _get_with_retry(PREV_RUNS_URL, params)
        raw = resp.json()
        missing = [h for h in hourly_forecast if h not in raw.get("hourly", {})]
        if missing:
            raise RuntimeError(
                f"Previous Runs API did not return {missing} for {name}; "
                "check variable names."
            )
        dest.write_text(json.dumps(raw))
        _write_manifest(
            dest,
            "Open-Meteo Previous Runs API 2026",
            resp.url,
            notes=f"{name} {YEAR_2026} {LEAD}",
        )
        time.sleep(0.5)
        print(f"  forecast {name} {YEAR_2026}: done")


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def demand_2026(force: bool = False) -> None:
    """Download and process NESO demand + ERA5 weather for 2026.

    Writes: data/raw/neso/demanddata_2026.csv (raw)
            data/raw/weather/{city}_2026.json  (ERA5 actual)
            data/processed/demand_weather_2026.parquet (processed)

    Call only after Dani approves docs/cs3_protocol.md.
    """
    print("Downloading NESO historic demand 2026 ...")
    neso_path = _download_neso_2026_raw(force=force)
    print("Downloading ERA5 actual weather 2026 (6 cities) ...")
    _download_era5_weather_2026(force=force)
    print("Processing demand_weather_2026.parquet ...")
    _build_demand_weather_2026(neso_path)


def forecast_weather_2026(force: bool = False) -> None:
    """Download Open-Meteo previous_day2 archived forecasts for 2026.

    Writes: data/raw/weather_forecast/{city}_2026.json (6 cities).
    Call only after Dani approves docs/cs3_protocol.md.
    """
    print("Downloading archived forecast weather 2026 (6 cities x previous_day2) ...")
    _download_forecast_weather_2026(force=force)


def download_all(force: bool = False) -> None:
    """Run demand_2026() then forecast_weather_2026().

    MUST NOT be called until Dani approves docs/cs3_protocol.md.
    """
    demand_2026(force=force)
    forecast_weather_2026(force=force)
    print("\nAll CS-3 downloads complete.")


if __name__ == "__main__":
    download_all()
