"""Batch 4 downloads (run on Dani's Mac; Claude's sandboxes cannot reach these hosts).

1. NESO Day-Ahead Half-Hourly Demand Forecast Performance (Apr 2021 onwards): NESO's published
   day-ahead National Demand forecast + outturn. Benchmark for the realistic comparison.
2. Open-Meteo Previous Runs API (Jan 2024 onwards): archived weather FORECASTS at a fixed lead.
   We use `_previous_day2` (issued ~48 h before the target hour), which is always earlier than
   our 09:00 D-1 issue time; `_previous_day1` would leak for targets after 09:00 on day D (D-024).
"""
import json
import time

import requests

from energy_futures.config import load_config, path
from energy_futures.ingest.manifest import record

NESO_DATASET = "day-ahead-half-hourly-demand-forecast-performance"
PREV_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
LEAD = "previous_day2"


def neso_day_ahead(force=False):
    cfg = load_config()
    raw = path(cfg, "raw") / "neso_benchmark"
    raw.mkdir(exist_ok=True)
    r = requests.get(f"{cfg['neso']['api_base']}/package_show", params={"id": NESO_DATASET}, timeout=60)
    r.raise_for_status()
    res = [x for x in r.json()["result"]["resources"] if str(x.get("format", "")).upper() == "CSV"]
    if len(res) != 1:
        raise RuntimeError(f"expected 1 CSV resource, found {[x.get('name') for x in res]}")
    dest = raw / "day_ahead_forecast_performance.csv"
    if dest.exists() and not force:
        print("  skip NESO day-ahead file (exists)")
        return
    resp = requests.get(res[0]["url"], timeout=180)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    record(raw.parent / "manifest.csv", dest, "NESO Day-Ahead Demand Forecast Performance", res[0]["url"])
    print(f"  got {dest.name} ({dest.stat().st_size/1e6:.1f} MB)")


def weather_forecasts(force=False):
    cfg = load_config()
    w = cfg["weather"]
    raw = path(cfg, "raw") / "weather_forecast"
    raw.mkdir(exist_ok=True)
    hourly = [f"{v}_{LEAD}" for v in w["hourly"]]
    for name, loc in w["locations"].items():
        for y in (2024, 2025):
            dest = raw / f"{name}_{y}.json"
            if dest.exists() and not force:
                continue
            params = {"latitude": loc["lat"], "longitude": loc["lon"], "start_date": f"{y}-01-01",
                      "end_date": f"{y}-12-31", "hourly": ",".join(hourly), "timezone": "GMT"}
            for attempt in range(4):
                resp = requests.get(PREV_RUNS_URL, params=params, timeout=120)
                if resp.status_code == 429:
                    time.sleep(30 * (attempt + 1))
                    continue
                resp.raise_for_status()
                break
            else:
                raise RuntimeError(f"rate-limited fetching {name} {y}")
            js = resp.json()
            missing = [h for h in hourly if h not in js.get("hourly", {})]
            if missing:
                raise RuntimeError(f"Previous Runs API did not return {missing}; check variable names")
            dest.write_text(json.dumps(js))
            record(raw.parent / "manifest.csv", dest, "Open-Meteo Previous Runs API", resp.url, notes=f"{name} {y} {LEAD}")
            time.sleep(0.5)
        print(f"  weather forecasts {name}: done")


def download():
    print("Downloading NESO day-ahead forecast performance...")
    neso_day_ahead()
    print("Downloading archived weather forecasts (6 locations x 2024-2025)...")
    weather_forecasts()


if __name__ == "__main__":
    download()
