"""Batch 2 data pipeline.

    uv run python -m energy_futures.pipeline download   # fetch raw NESO + weather (needs internet)
    uv run python -m energy_futures.pipeline build      # clean, validate, align, save Parquet
    uv run python -m energy_futures.pipeline all
"""
import hashlib
import json
import sys
from datetime import datetime, timezone

import pandas as pd

from energy_futures.clean import demand as cd
from energy_futures.clean import weather as cw
from energy_futures.config import ROOT, load_config, path


def download():
    from energy_futures.ingest import neso, weather
    print("Downloading NESO historic demand data...")
    neso.download()
    print("Downloading Open-Meteo weather (6 locations x 17 years; a few minutes)...")
    weather.download()


def build():
    cfg = load_config()
    raw, interim, processed, reports = (path(cfg, k) for k in ("raw", "interim", "processed", "reports"))

    files = sorted((raw / "neso").glob("demanddata_*.csv"))
    if not files:
        sys.exit("No raw NESO files found. Run the 'download' step first.")
    demand, drep = cd.clean(cd.load_raw(files))
    demand.to_parquet(interim / "demand_clean.parquet")
    print(f"Demand: {drep['rows_clean']:,} clean half-hours, {drep['missing_slots']} missing slots")

    locs = list(cfg["weather"]["locations"])
    wrep = {}
    if list((raw / "weather").glob("*.json")):
        wx, wrep = cw.build(raw / "weather", locs, demand.index)
        wx.to_parquet(interim / "weather_halfhourly.parquet")
        merged = demand.join(wx)
    else:
        print("No weather files found; building demand-only dataset.")
        merged = demand
    merged.to_parquet(processed / "demand_weather.parquet")

    manifest = raw / "manifest.csv"
    version = {
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config_sha256": hashlib.sha256((ROOT / "configs/data.yaml").read_bytes()).hexdigest()[:16],
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest()[:16] if manifest.exists() else None,
        "rows": int(len(merged)), "columns": list(merged.columns),
        "start_utc": str(merged.index.min()), "end_utc": str(merged.index.max()),
    }
    (processed / "dataset_version.json").write_text(json.dumps(version, indent=2))
    (reports / "quality_report.json").write_text(json.dumps({"demand": drep, "weather": wrep}, indent=2, default=str))
    print(f"Saved data/processed/demand_weather.parquet ({len(merged):,} rows) and docs/data_quality/quality_report.json")


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    if step in ("download", "all"):
        download()
    if step in ("build", "all"):
        build()
