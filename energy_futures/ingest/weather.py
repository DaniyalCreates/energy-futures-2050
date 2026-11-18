"""Download hourly ERA5-based historical weather from Open-Meteo (CC BY 4.0; free tier is
non-commercial) for each configured location, saved unchanged as JSON in data/raw/weather/.
Requests are split by year to stay well within fair-use limits.
"""
import json
import time
from datetime import date

import requests

from energy_futures.config import load_config, path
from energy_futures.ingest.manifest import record


def download(force: bool = False) -> list[dict]:
    cfg = load_config()
    w = cfg["weather"]
    raw = path(cfg, "raw") / "weather"
    raw.mkdir(exist_ok=True)
    y0, y1 = date.fromisoformat(w["start_date"]).year, date.fromisoformat(w["end_date"]).year
    rows = []
    for name, loc in w["locations"].items():
        for y in range(y0, y1 + 1):
            dest = raw / f"{name}_{y}.json"
            if dest.exists() and not force:
                continue
            params = {
                "latitude": loc["lat"], "longitude": loc["lon"],
                "start_date": f"{y}-01-01", "end_date": f"{y}-12-31",
                "hourly": ",".join(w["hourly"]), "timezone": w["timezone"],
            }
            for attempt in range(4):
                resp = requests.get(w["api_url"], params=params, timeout=120)
                if resp.status_code == 429:  # rate limited: back off
                    time.sleep(30 * (attempt + 1))
                    continue
                resp.raise_for_status()
                break
            else:
                raise RuntimeError(f"rate-limited fetching {name} {y}")
            dest.write_text(json.dumps(resp.json()))
            rows.append(record(raw.parent / "manifest.csv", dest, "Open-Meteo Historical Weather API",
                               resp.url, notes=f"{name} {y}"))
            time.sleep(0.5)
        print(f"  weather {name}: done")
    return rows


if __name__ == "__main__":
    download()
