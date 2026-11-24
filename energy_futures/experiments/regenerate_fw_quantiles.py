"""Generate Mac-consistent FW quantile series for 2024-01-01..2025-12-31 (STAGE 3e).

Runs the same GBMQuantile backtest as advanced.test() on this Mac, producing a
single consistent series. The cloud-generated Batch 4 file (quantiles_FW_raw.parquet)
is NOT touched; it remains the reported Batch 4 result.

Outputs (all in outputs/v2_cs2_rolling/inputs/):
  quantiles_FW_raw_mac_2024-2025.parquet  — Mac FW quantiles 2024-01-01..2025-12-31
  cloud_vs_mac.csv                        — reproducibility table (per-quantile diffs,
                                            raw Coverage_90, library versions)

Does NOT write to outputs/advanced/ or outputs_archive/.

Background (Amendment 2 addendum, 2026-11-24):
  The existing quantiles_FW_raw.parquet was generated in Claude's cloud workspace
  (Batch 4). A determinism check showed up to 113 MW difference from a Mac re-run,
  caused by LightGBM's n_jobs=-1 parallel tree building (same code, seed, lockfile).
  Resolution: use ONE consistent Mac series for all CS-2b calibration and evaluation.
"""

from __future__ import annotations

import json
import platform
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

CLOUD_FW_RAW = REPO / "outputs" / "advanced" / "test" / "quantiles_FW_raw.parquet"
OUT_DIR = REPO / "outputs" / "v2_cs2_rolling" / "inputs"
OUT_MAC = OUT_DIR / "quantiles_FW_raw_mac_2024-2025.parquet"
OUT_CSV = OUT_DIR / "cloud_vs_mac.csv"

T0 = CFG["test"]["start"]     # "2024-01-01"
T1 = CFG["test"]["end"]       # "2025-12-31"
FW_START = "2024-03-08"       # start of evaluation window; also start of cloud file
Q_COLS = ["q05", "q10", "q25", "q50", "q75", "q90", "q95"]


def _local_days(index: pd.DatetimeIndex) -> pd.Series:
    return pd.Series(
        index.tz_convert(TZ).normalize().tz_localize(None), index=index
    )


def _cloud_vs_mac_csv(q_cloud: pd.DataFrame, q_mac: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    """Build reproducibility comparison table for 2024-03-08+ rows."""
    shared_idx = q_cloud.index.intersection(q_mac.index)

    rows = []
    for col in Q_COLS:
        diff = np.abs(q_cloud.loc[shared_idx, col].values - q_mac.loc[shared_idx, col].values)
        rows.append({
            "metric": col,
            "mean_abs_diff_mw": round(float(diff.mean()), 2),
            "p99_abs_diff_mw": round(float(np.percentile(diff, 99)), 2),
            "max_abs_diff_mw": round(float(diff.max()), 2),
            "cloud_value": "",
            "mac_value": "",
        })

    # Raw Coverage_90: fraction of half-hours where actual demand ∈ [q05, q95]
    y_shared = y.reindex(shared_idx).dropna()
    shared_valid = y_shared.index
    if len(shared_valid) > 0:
        cov_cloud = float(
            ((y_shared >= q_cloud.loc[shared_valid, "q05"])
             & (y_shared <= q_cloud.loc[shared_valid, "q95"])).mean()
        ) * 100.0
        cov_mac = float(
            ((y_shared >= q_mac.loc[shared_valid, "q05"])
             & (y_shared <= q_mac.loc[shared_valid, "q95"])).mean()
        ) * 100.0
    else:
        cov_cloud = cov_mac = float("nan")

    rows.append({
        "metric": "coverage_90_raw",
        "mean_abs_diff_mw": "",
        "p99_abs_diff_mw": "",
        "max_abs_diff_mw": "",
        "cloud_value": round(cov_cloud, 2),
        "mac_value": round(cov_mac, 2),
    })

    # Library/platform metadata
    import lightgbm as lgb  # local import; known to be available
    rows.append({
        "metric": "lightgbm_version",
        "mean_abs_diff_mw": "", "p99_abs_diff_mw": "", "max_abs_diff_mw": "",
        "cloud_value": "cloud-workspace (unknown)", "mac_value": lgb.__version__,
    })
    rows.append({
        "metric": "numpy_version",
        "mean_abs_diff_mw": "", "p99_abs_diff_mw": "", "max_abs_diff_mw": "",
        "cloud_value": "cloud-workspace (unknown)", "mac_value": np.__version__,
    })
    rows.append({
        "metric": "platform_machine",
        "mean_abs_diff_mw": "", "p99_abs_diff_mw": "", "max_abs_diff_mw": "",
        "cloud_value": "cloud-workspace (unknown)", "mac_value": platform.machine(),
    })
    rows.append({
        "metric": "n_rows_compared",
        "mean_abs_diff_mw": "", "p99_abs_diff_mw": "", "max_abs_diff_mw": "",
        "cloud_value": len(shared_idx), "mac_value": len(shared_idx),
    })

    return pd.DataFrame(rows)


def run() -> None:
    t_start = time.time()

    # --- 1. Load validation summary ---
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
    y = d[CFG["target"]]

    print("Building forecast-weather features ...")
    fw_weather = forecast_weather(
        REPO / "data" / "raw" / "weather_forecast",
        CFG["locations"],
        d.index,
    )
    X_pw, _ = build.build(d, CFG["target"])
    X_fw, _ = build.build(d, CFG["target"], weather=fw_weather)

    # --- 3. Run FW quantile backtest ---
    print(
        f"Running FW quantile backtest {T0}..{T1} "
        f"(quantile_refit={CFG['quantile_refit']!r}, start_pw={start_pw!r}) ..."
    )
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
    q_mac = qp["FW"]
    print(f"Backtest complete: {len(q_mac):,} rows ({T0}..{T1})")

    # --- 4. Build cloud_vs_mac.csv (comparison for 2024-03-08+ rows) ---
    if not CLOUD_FW_RAW.exists():
        print(f"WARNING: cloud file not found at {CLOUD_FW_RAW}; skipping comparison table.")
        df_cmp = None
    else:
        print("Building cloud_vs_mac comparison table ...")
        q_cloud = pd.read_parquet(CLOUD_FW_RAW)
        df_cmp = _cloud_vs_mac_csv(q_cloud, q_mac, y)
        print("cloud_vs_mac stats (2024-03-08+ rows):")
        print(df_cmp[df_cmp["metric"].isin(Q_COLS + ["coverage_90_raw"])].to_string(index=False))

    # --- 5. Write outputs ---
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    q_mac.to_parquet(OUT_MAC)
    print(f"\nMac series written: {len(q_mac):,} rows → {OUT_MAC}")

    if df_cmp is not None:
        df_cmp.to_csv(OUT_CSV, index=False)
        print(f"Comparison table written → {OUT_CSV}")

    elapsed = time.time() - t_start
    print(f"Runtime: {elapsed:.1f}s\nDone.")


if __name__ == "__main__":
    run()
