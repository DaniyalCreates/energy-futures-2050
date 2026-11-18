"""Raw-data manifest: one row per downloaded file (source URL, time, size, SHA-256)."""
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ["file", "source", "url", "downloaded_utc", "bytes", "sha256", "notes"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def record(manifest: Path, file: Path, source: str, url: str, notes: str = "") -> dict:
    row = {
        "file": file.name, "source": source, "url": url,
        "downloaded_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "bytes": file.stat().st_size, "sha256": sha256(file), "notes": notes,
    }
    rows = []
    if manifest.exists():
        with open(manifest, newline="") as f:
            rows = [r for r in csv.DictReader(f) if r["file"] != file.name]
    rows.append(row)
    with open(manifest, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: r["file"]))
    return row
