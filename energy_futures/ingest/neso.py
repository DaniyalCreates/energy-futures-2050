"""Download NESO Historic Demand Data (one CSV per year) unchanged into data/raw/neso/.

Resource URLs are resolved at run time from the NESO CKAN API, so the script does not
depend on hard-coded file links. Source licence: NESO Open Data Licence.
"""
import re
import time

import requests

from energy_futures.config import load_config, path
from energy_futures.ingest.manifest import record

YEAR_RE = re.compile(r"historic demand data\s+(\d{4})", re.I)


def list_resources(cfg: dict) -> dict[int, str]:
    n = cfg["neso"]
    r = requests.get(f"{n['api_base']}/package_show", params={"id": n["dataset_id"]}, timeout=60)
    r.raise_for_status()
    out = {}
    for res in r.json()["result"]["resources"]:
        m = YEAR_RE.search(res.get("name", ""))
        if m and str(res.get("format", "")).upper() == "CSV":
            out[int(m.group(1))] = res["url"]
    return out


def download(force: bool = False) -> list[dict]:
    cfg = load_config()
    raw = path(cfg, "raw") / "neso"
    raw.mkdir(exist_ok=True)
    resources = list_resources(cfg)
    years = range(cfg["neso"]["first_year"], cfg["neso"]["last_year"] + 1)
    missing = [y for y in years if y not in resources]
    if missing:
        raise RuntimeError(f"NESO resources not found for years {missing}; available: {sorted(resources)}")
    rows = []
    for y in years:
        dest = raw / f"demanddata_{y}.csv"
        if dest.exists() and not force:
            print(f"  skip {dest.name} (exists)")
            continue
        url = resources[y]
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=120)
                resp.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(5 * (attempt + 1))
        dest.write_bytes(resp.content)
        rows.append(record(raw.parent / "manifest.csv", dest, "NESO Historic Demand Data", url))
        print(f"  got {dest.name} ({dest.stat().st_size/1e6:.1f} MB)")
    return rows


if __name__ == "__main__":
    download()
