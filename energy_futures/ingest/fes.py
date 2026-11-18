"""Download NESO Future Energy Scenarios (FES) 2025 summary tables (NESO Open Data Licence).

ED1 = electricity demand summary by pathway and year; ED2 = its definitions (PDF);
ES1 = electricity supply (capacity/generation) by pathway and year.
URLs taken from the NESO Data Portal resource pages (verified 2026-11-18).
"""
import requests

from energy_futures.config import load_config, path
from energy_futures.ingest.manifest import record

BASE = "https://api.neso.energy/dataset"
FILES = {
    "fes2025_ed1_v006.csv": f"{BASE}/2c15c755-d8fe-4229-9169-3b6dd7c88fec/resource/300c07b9-baeb-4411-bc40-987cbb4aec0b/download/fes2025_ed1_v006.csv",
    "fes2025_ed2_v004.pdf": f"{BASE}/2c15c755-d8fe-4229-9169-3b6dd7c88fec/resource/93761974-17f5-43da-a690-71faaab610a5/download/fes2025_ed2_v004.pdf",
    "fes2025_es1_v006.csv": f"{BASE}/549b0667-b533-4748-95bd-f6e13933a47d/resource/6c78a777-b885-4bb6-bc35-8100f9e137a2/download/fes2025_es1_v006.csv",
}


def download(force: bool = False):
    raw = path(load_config(), "raw") / "fes"
    raw.mkdir(exist_ok=True)
    for name, url in FILES.items():
        dest = raw / name
        if dest.exists() and not force:
            print(f"  skip {name} (exists)")
            continue
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        dest.write_bytes(r.content)
        record(raw.parent / "manifest.csv", dest, "NESO FES 2025", url)
        print(f"  got {name} ({dest.stat().st_size/1e3:.0f} kB)")


if __name__ == "__main__":
    download()
