"""Regenerate FW quantile gap: 2024-01-01..2024-03-07.

The original EXP-004 CQR calibrated 2024-25 predictions using FW quantiles from
t0="2024-01-01", but only the slice from fw_comparison_start="2024-03-08" was saved
to quantiles_FW_raw.parquet. This script re-runs the identical GBMQuantile backtest
to recover the missing 67 days (Amendment 2 of CS-2 pre-registration).

Outputs:
    outputs/v2_cs2_rolling/inputs/quantiles_FW_raw_from_2024-01-01.parquet
        (gap slice only: 2024-01-01..2024-03-07)

Does NOT touch outputs/advanced/ or outputs_archive/.

Determinism check: rows from 2024-03-08 onward must equal the existing
outputs/advanced/test/quantiles_FW_raw.parquet (max abs diff < 1e-6).
If the check fails, the script exits without writing the gap file.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from energy_futures.clean.benchmarks import forecast_weather
from energy_futures.evaluate import backtest
from energy_futures.features import build
from energy_futures.forecast.gbm import GBMQuantile

TZ = "Europe/London"
CFG = yaml.safe_load((REPO / "configs" / "advanced.yaml").read_text())

EXISTING_FW_RAW = REPO / "outputs" / "advanced" / "test" / "quantiles_FW_raw.parquet"
OUT_DIR = REPO / "outputs" / "v2_cs2_rolling" / "inputs"
OUT_PATH = OUT_DIR / "quantiles_FW_raw_from_2024-01-01.parquet"

T0 = CFG["test"]["start"]           # "2024-01-01"
T1 = CFG["test"]["end"]             # "2025-12-31"
GAP_END = "2024-03-07"
FW_START = "2024-03-08"
DETERMINISM_TOL = 1e-6


def _local_days(index: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(
        index.tz_convert(TZ).normalize().tz_localize(None), index=index
    )


def run() -> None:
    t_start = time.time()

    # --- 1. Load validation summary to get the chosen start_pw ---
    summary_path = REPO / "outputs" / "advanced" / "validation" / "summary.json"
    if not summary_path.exists():
        print(f"ERROR: validation summary not found at {summary_path}")
        sys.exit(1)
    vs = json.loads(summary_path.read_text())
    start_pw = vs["chosen_train_start"]["PW"]
    print(f"start_pw = {start_pw!r}  (from validation summary)")

    # --- 2. Load demand data and build features ---
    print("Loading demand data ...")
    d = pd.read_parquet(REPO / "data" / "processed" / "demand_weather.parquet")

    print("Building forecast-weather features ...")
    fw_weather = forecast_weather(
        REPO / "data" / "raw" / "weather_forecast",
        CFG["locations"],
        d.index,
    )
    X_pw, y = build.build(d, CFG["target"])
    X_fw, _ = build.build(d, CFG["target"], weather=fw_weather)

    # --- 3. Run FW quantile backtest (same config as advanced.test()) ---
    print(f"Running FW quantile backtest {T0} to {T1} (quantile_refit={CFG['quantile_refit']!r}) ...")
    qp, _ = backtest.run_multi(
        lambda: GBMQuantile(True, start_pw),
        X_pw,
        y,
        {"FW": X_fw},
        T0,
        T1,
        CFG["quantile_refit"],
        method="predict_quantiles",
    )
    q_fw = qp["FW"]
    print(f"Backtest complete: {len(q_fw):,} rows generated ({T0} to {T1})")

    # --- 4. Determinism check: rows from 2024-03-08 must match existing file ---
    if not EXISTING_FW_RAW.exists():
        print(f"ERROR: existing quantiles_FW_raw.parquet not found at {EXISTING_FW_RAW}")
        sys.exit(1)

    existing = pd.read_parquet(EXISTING_FW_RAW)
    days_new = _local_days(q_fw.index)
    overlap_mask = days_new >= pd.Timestamp(FW_START)
    q_new_overlap = q_fw[overlap_mask]

    shared_idx = q_new_overlap.index.intersection(existing.index)
    if len(shared_idx) == 0:
        print("ERROR: no overlapping rows found for determinism check.")
        sys.exit(1)

    q_cols = ["q05", "q10", "q25", "q50", "q75", "q90", "q95"]
    max_diff = float(
        np.abs(
            q_new_overlap.loc[shared_idx, q_cols].values
            - existing.loc[shared_idx, q_cols].values
        ).max()
    )
    print(f"Determinism check: {len(shared_idx):,} overlapping rows, max abs diff = {max_diff:.2e}")

    if max_diff >= DETERMINISM_TOL:
        print(
            f"\nSTOP: Determinism check FAILED (max abs diff {max_diff:.2e} ≥ {DETERMINISM_TOL:.0e}).\n"
            "The regenerated FW quantiles do not match the existing file for 2024-03-08+.\n"
            "Do not write the gap file. Investigate the discrepancy and report to Dani."
        )
        sys.exit(1)

    print("Determinism check PASSED.")

    # --- 5. Save gap slice only (2024-01-01..2024-03-07) ---
    days_new_local = _local_days(q_fw.index)
    gap_mask = (days_new_local >= pd.Timestamp(T0)) & (days_new_local <= pd.Timestamp(GAP_END))
    q_gap = q_fw[gap_mask]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    q_gap.to_parquet(OUT_PATH)

    elapsed = time.time() - t_start
    print(
        f"\nGap file written: {len(q_gap):,} rows ({T0} to {GAP_END})\n"
        f"Path: {OUT_PATH}\n"
        f"Runtime: {elapsed:.1f}s"
    )


if __name__ == "__main__":
    run()
