"""
CS-3 quantile generation: GBMQuantile FW predictions for 2026.

STATUS: committed BEFORE any run. MUST NOT be called until Dani approves
docs/cs3_protocol.md and 2026 data has been downloaded.

Frozen method (from commit 304b7d8 and cs3_protocol.md §5):
  - GBMQuantile(use_weather=True, train_start="2009-01-01")
  - Refit schedule: QS (quarterly start), expanding window
  - Training: observed (PW) weather for all years; prediction: previous_day2
    archived forecasts (FW) for 2026
  - Architecture: Dani's Mac (arm64 Darwin); same as quantiles_FW_raw_mac_2024-2025.parquet

Output:
  outputs/v3_cs3_confirmation/inputs/quantiles_FW_raw_mac_2026.parquet
  (UTC-indexed, columns q05/q10/q25/q50/q75/q90/q95; restricted to 2026-01-01..2026-10-31)

Data inputs:
  data/processed/demand_weather.parquet           (2009-2025, read-only)
  data/processed/demand_weather_2026.parquet      (2026, from download_cs3_data_2026.py)
  data/raw/weather_forecast/                      (forecast JSON for 2024-2025 and 2026)
  outputs/advanced/validation/summary.json        (chosen train_start)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from energy_futures.clean.benchmarks import forecast_weather as _forecast_weather
from energy_futures.evaluate import backtest
from energy_futures.features import build as feat_build
from energy_futures.forecast.gbm import GBMQuantile

TZ = "Europe/London"
CS3_START = "2026-01-01"
CS3_END   = "2026-10-31"
REFIT_FREQ = "QS"            # quarterly start
TRAIN_START = "2009-01-01"   # frozen; expanded to include 2026 data up to each refit date

DEMAND_PATH     = REPO / "data" / "processed" / "demand_weather.parquet"
DEMAND_2026_PATH = REPO / "data" / "processed" / "demand_weather_2026.parquet"
FORECAST_DIR    = REPO / "data" / "raw" / "weather_forecast"
VALIDATION_JSON = REPO / "outputs" / "advanced" / "validation" / "summary.json"

OUT_DIR = REPO / "outputs" / "v3_cs3_confirmation" / "inputs"
OUT_PATH = OUT_DIR / "quantiles_FW_raw_mac_2026.parquet"

Q_COLS = ["q05", "q10", "q25", "q50", "q75", "q90", "q95"]


# ---------------------------------------------------------------------------
# Schema guard (protects concatenation integrity)
# ---------------------------------------------------------------------------

def _check_schema_match(
    candidate: pd.DataFrame,
    reference: pd.DataFrame,
    context: str,
) -> None:
    """Raise RuntimeError if candidate's columns or dtypes differ from reference.

    Columns must be identical (same names, same order). Dtypes must match exactly.
    """
    cand_cols = list(candidate.columns)
    ref_cols = list(reference.columns)
    if cand_cols != ref_cols:
        missing_c = [c for c in ref_cols if c not in cand_cols]
        extra_c = [c for c in cand_cols if c not in ref_cols]
        raise RuntimeError(
            f"Schema mismatch in {context}: "
            f"missing columns {missing_c}, extra columns {extra_c}. "
            f"Expected {ref_cols}, got {cand_cols}."
        )
    mismatched = [
        (col, str(reference[col].dtype), str(candidate[col].dtype))
        for col in ref_cols
        if candidate[col].dtype != reference[col].dtype
    ]
    if mismatched:
        raise RuntimeError(
            f"Dtype mismatch in {context}: "
            + ", ".join(
                f"'{col}' expected {exp} got {got}" for col, exp, got in mismatched
            )
        )


# ---------------------------------------------------------------------------
# Data loading helpers (separated to allow unit testing)
# ---------------------------------------------------------------------------

def load_combined_demand(
    demand_path: Path = DEMAND_PATH,
    demand_2026_path: Path = DEMAND_2026_PATH,
) -> pd.DataFrame:
    """Load 2009-2025 demand_weather and 2026 demand_weather, concatenate.

    The combined index is used for lag feature computation so that January 2026
    half-hours draw on December 2025 values (no gap at the year boundary).
    Raises RuntimeError if demand_weather_2026.parquet columns/dtypes do not match
    demand_weather.parquet (guards against partial or mismatched builds).
    """
    d_hist = pd.read_parquet(demand_path)
    d_2026 = pd.read_parquet(demand_2026_path)
    _check_schema_match(
        d_2026, d_hist,
        "demand_weather_2026.parquet vs demand_weather.parquet"
    )
    combined = pd.concat([d_hist, d_2026]).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    return combined


def load_forecast_weather(
    forecast_dir: Path,
    combined_index: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Load all archived forecast weather JSON files and align to combined_index.

    Loads both 2024-2025 and 2026 JSON files from forecast_dir.
    Uses clean.benchmarks.forecast_weather() logic.
    """
    locations = [
        "london", "birmingham", "manchester", "newcastle", "glasgow", "cardiff"
    ]
    return _forecast_weather(forecast_dir, locations, combined_index)


# ---------------------------------------------------------------------------
# Validation guard
# ---------------------------------------------------------------------------

def _check_output_dates(q: pd.DataFrame) -> None:
    """Raise ValueError if any row falls outside 2026-01-01..2026-10-31."""
    local_dates = q.index.tz_convert(TZ).normalize().tz_localize(None)
    lo = pd.Timestamp("2026-01-01")
    hi = pd.Timestamp("2026-10-31")
    out_of_range = local_dates[(local_dates < lo) | (local_dates > hi)]
    if len(out_of_range) > 0:
        raise ValueError(
            f"Output date guard: {len(out_of_range)} rows outside "
            f"2026-01-01..2026-10-31 detected. First: {out_of_range.min().date()}."
        )


# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------

def run(
    demand_path: Path = DEMAND_PATH,
    demand_2026_path: Path = DEMAND_2026_PATH,
    forecast_dir: Path = FORECAST_DIR,
    out_path: Path = OUT_PATH,
) -> pd.DataFrame:
    """Generate FW quantile predictions for 2026-01-01..2026-10-31.

    Returns the quantile DataFrame (also written to out_path).
    MUST NOT be called until Dani approves docs/cs3_protocol.md and 2026
    data has been downloaded.
    """
    # --- Load train_start from validation summary (same as regenerate_fw_quantiles.py) ---
    if not VALIDATION_JSON.exists():
        raise FileNotFoundError(
            f"Validation summary not found: {VALIDATION_JSON}. "
            "Run the advanced.py validation step first."
        )
    vs = json.loads(VALIDATION_JSON.read_text())
    start_pw = vs["chosen_train_start"]["PW"]
    print(f"start_pw = {start_pw!r}  (from validation summary)")

    # --- Load data ---
    print("Loading combined demand (2009-2026) ...")
    d = load_combined_demand(demand_path, demand_2026_path)
    y = d["underlying_demand"]

    print("Loading forecast weather features ...")
    fw_weather = load_forecast_weather(forecast_dir, d.index)
    X_pw, _ = feat_build.build(d, "underlying_demand")
    X_fw, _ = feat_build.build(d, "underlying_demand", weather=fw_weather)

    # --- Run quantile backtest ---
    print(
        f"Running FW quantile backtest {CS3_START}..{CS3_END} "
        f"(refit={REFIT_FREQ!r}, start_pw={start_pw!r}) ..."
    )
    qp, refit_log = backtest.run_multi(
        lambda: GBMQuantile(True, start_pw),
        X_pw,
        y,
        {"FW": X_fw},
        CS3_START,
        CS3_END,
        REFIT_FREQ,
        method="predict_quantiles",
    )
    q_2026 = qp["FW"]

    # --- Validate output dates ---
    _check_output_dates(q_2026)
    print(f"Backtest complete: {len(q_2026):,} rows, {len(refit_log)} refits")
    for entry in refit_log:
        print(f"  refit at {entry['block_start']}: "
              f"train_end={entry['train_end_utc'][:10]}, "
              f"n_eval={entry['n_eval']}")

    # --- Write output ---
    out_path.parent.mkdir(parents=True, exist_ok=True)
    q_2026.to_parquet(out_path)
    print(f"\nCS-3 quantiles written: {len(q_2026):,} rows → {out_path}")
    return q_2026


if __name__ == "__main__":
    run()
