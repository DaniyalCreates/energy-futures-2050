"""
CS-2b: Rolling evaluation of all four conditional calibration methods.

Loads development data, applies each method over §5 evaluation quarters
(2023-Q1 to Q4; 2024-Q2 to Q4; 2025-Q1 to Q4 — 11 quarters; 2024-Q1 excluded),
computes §6 metrics with block-bootstrap 95% CIs, and calls select_method.

This file is committed BEFORE any real evaluation run (pre-registration CS-2b).
Outputs go to outputs/v2_cs2_rolling/ only. No 2026 data is loaded.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from energy_futures.experiments.conditional_calibration import (
    apply_calibration_daily,
    load_development_data,
    select_method,
)
from energy_futures.features.calendar import bank_holidays_ew

TZ = "Europe/London"
SEED = 42
N_BOOT = 1_000
METHODS = ["baseline", "mondrian", "mondrian_extended", "width_normalised"]
EVAL_START = "2023-01-01"
EVAL_END = "2025-12-31"
OUT_DIR = REPO / "outputs" / "v2_cs2_rolling"
DEMAND_PATH = REPO / "data" / "processed" / "demand_weather.parquet"
COLD_THRESHOLD_C = 3.0

# Pinball taus and their quantile columns (§6, same order)
_TAUS = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
_QCOLS = ["q05", "q10", "q25", "q50", "q75", "q90", "q95"]

# §5 evaluation quarters — 11 quarters; 2024-Q1 is calibration-only (window too short)
EVAL_QUARTERS: list[tuple[str, str, str]] = [
    ("2023-Q1", "2023-01-01", "2023-03-31"),
    ("2023-Q2", "2023-04-01", "2023-06-30"),
    ("2023-Q3", "2023-07-01", "2023-09-30"),
    ("2023-Q4", "2023-10-01", "2023-12-31"),
    ("2024-Q2", "2024-04-01", "2024-06-30"),
    ("2024-Q3", "2024-07-01", "2024-09-30"),
    ("2024-Q4", "2024-10-01", "2024-12-31"),
    ("2025-Q1", "2025-01-01", "2025-03-31"),
    ("2025-Q2", "2025-04-01", "2025-06-30"),
    ("2025-Q3", "2025-07-01", "2025-09-30"),
    ("2025-Q4", "2025-10-01", "2025-12-31"),
]

# (condition_key, flag_column_or_None, display_label)
# "cold_obs" is outcome-based and labelled "reporting only" per §6
_CONDITIONS: list[tuple[str, str | None, str]] = [
    ("all",          None,                 "All"),
    ("cold_proxy",   "is_cold_proxy",      "Cold proxy (temp_proxy < 3°C)"),
    ("high_demand",  "is_high_demand",     "High-demand (§6.1: daily max q50 ≥ P95)"),
    ("winter",       "is_winter",          "Winter (Dec–Feb)"),
    ("bank_holiday", "is_bank_holiday",    "Bank holiday (England & Wales)"),
    ("cold_obs",     "is_cold_obs",        "Cold observed — reporting only"),
]

METRIC_COLS = ["covered_90", "covered_80", "covered_50", "width_90", "winkler", "pinball"]


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _block_bootstrap(
    vals: np.ndarray,
    rng: np.random.Generator,
) -> tuple[float, float, float]:
    """Block-bootstrap by calendar day; return (mean, ci_low_95, ci_high_95).

    Vectorised: generates all N_BOOT × n indices at once to avoid Python loop overhead.
    """
    n = len(vals)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    idx = rng.integers(0, n, size=(N_BOOT, n))  # (N_BOOT, n)
    boot_means = vals[idx].mean(axis=1)          # (N_BOOT,)
    return (
        float(vals.mean()),
        float(np.percentile(boot_means, 2.5)),
        float(np.percentile(boot_means, 97.5)),
    )


# ---------------------------------------------------------------------------
# Half-hourly metric columns
# ---------------------------------------------------------------------------

def _add_hh_metrics(cal_q: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    """Add covered_90/80/50, width_90, winkler, pinball columns to calibrated-quantile df."""
    df = cal_q[_QCOLS].copy()
    df["y"] = y.reindex(cal_q.index)

    df["covered_90"] = (df["y"] >= df["q05"]) & (df["y"] <= df["q95"])
    df["covered_80"] = (df["y"] >= df["q10"]) & (df["y"] <= df["q90"])
    df["covered_50"] = (df["y"] >= df["q25"]) & (df["y"] <= df["q75"])
    df["width_90"] = df["q95"] - df["q05"]

    # Winkler: width + 20 × undercut penalty + 20 × overrun penalty (§6)
    df["winkler"] = (
        df["width_90"]
        + 20.0 * np.maximum(df["q05"] - df["y"], 0.0)
        + 20.0 * np.maximum(df["y"] - df["q95"], 0.0)
    )

    # Pinball: mean over τ ∈ {0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95} (§6)
    pinball_sum = np.zeros(len(df))
    for tau, qcol in zip(_TAUS, _QCOLS):
        diff = df["y"].values - df[qcol].values
        pinball_sum += np.where(diff >= 0.0, tau * diff, (tau - 1.0) * diff)
    df["pinball"] = pinball_sum / len(_TAUS)

    return df


# ---------------------------------------------------------------------------
# Condition flags
# ---------------------------------------------------------------------------

def _add_flags(
    df: pd.DataFrame,
    temp_proxy: pd.Series,
    obs_temp_daily: pd.Series,
    high_demand_dates: set,
    bank_hol_dates: set,
) -> pd.DataFrame:
    """Add date-level condition flag columns to a half-hourly DataFrame."""
    df = df.copy()
    local = df.index.tz_convert(TZ)
    df["date"] = local.date
    df["month"] = local.month

    # Proxy-based cold flag (NaN proxy → not cold per IEEE 754; NaN days tracked separately)
    proxy_num = pd.to_numeric(df["date"].map(temp_proxy), errors="coerce")
    df["is_nan_proxy"] = proxy_num.isna()
    df["is_cold_proxy"] = (proxy_num < COLD_THRESHOLD_C).fillna(False)

    # Outcome-based cold flag — reporting only (uses observed temperature, not proxy)
    obs_num = pd.to_numeric(df["date"].map(obs_temp_daily), errors="coerce")
    df["is_cold_obs"] = (obs_num < COLD_THRESHOLD_C).fillna(False)

    df["is_high_demand"] = df["date"].isin(high_demand_dates)
    df["is_winter"] = df["month"].isin([12, 1, 2])
    df["is_bank_holiday"] = df["date"].isin(bank_hol_dates)
    return df


# ---------------------------------------------------------------------------
# Day-level aggregation
# ---------------------------------------------------------------------------

def _day_level(hh_sub: pd.DataFrame) -> pd.DataFrame:
    """Aggregate half-hourly data to day-level mean values and first-value flags."""
    return hh_sub.groupby("date").agg(
        covered_90=("covered_90", "mean"),
        covered_80=("covered_80", "mean"),
        covered_50=("covered_50", "mean"),
        width_90=("width_90", "mean"),
        winkler=("winkler", "mean"),
        pinball=("pinball", "mean"),
        is_cold_proxy=("is_cold_proxy", "first"),
        is_cold_obs=("is_cold_obs", "first"),
        is_high_demand=("is_high_demand", "first"),
        is_winter=("is_winter", "first"),
        is_bank_holiday=("is_bank_holiday", "first"),
        is_nan_proxy=("is_nan_proxy", "first"),
    )


# ---------------------------------------------------------------------------
# Metric rows with bootstrap CIs
# ---------------------------------------------------------------------------

def _metric_rows(
    day_df: pd.DataFrame,
    quarter: str,
    method: str,
    rng: np.random.Generator,
) -> list[dict]:
    """Compute all §6 metrics for each condition; return a list of result dicts."""
    rows = []
    for cond_key, flag_col, label in _CONDITIONS:
        mask = day_df[flag_col].astype(bool) if flag_col else pd.Series(True, index=day_df.index)

        for metric in METRIC_COLS:
            vals = day_df.loc[mask, metric].values.astype(float)
            mean, lo, hi = _block_bootstrap(vals, rng)
            # Coverage metrics → percentage
            if metric.startswith("covered_"):
                mean, lo, hi = mean * 100.0, lo * 100.0, hi * 100.0
            rows.append({
                "quarter": quarter,
                "method": method,
                "condition_key": cond_key,
                "condition": label,
                "metric": metric,
                "mean": round(float(mean), 4) if np.isfinite(mean) else float("nan"),
                "ci_low_95": round(float(lo), 4) if np.isfinite(lo) else float("nan"),
                "ci_high_95": round(float(hi), 4) if np.isfinite(hi) else float("nan"),
                "n_days": int(mask.sum()),
            })
    return rows


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def evaluate(
    raw_q: pd.DataFrame,
    y: pd.Series,
    temp_proxy: pd.Series,
    obs_temp_daily: pd.Series,
    out_dir: Path = OUT_DIR,
) -> dict:
    """Run the full CS-2b rolling evaluation on development data.

    Parameters
    ----------
    raw_q         : UTC-indexed DataFrame of raw (uncalibrated) quantiles (q05–q95)
    y             : UTC-indexed Series of actual underlying demand
    temp_proxy    : local date-indexed Series of temperature proxy (NaN if unavailable)
    obs_temp_daily: local date-indexed Series of observed daily mean temperature
                    (used only for outcome-based cold coverage labelled "reporting only")
    out_dir       : where to write CSV and text outputs (created if needed)

    Returns
    -------
    dict with keys: metrics_df, quarter_df, pooled_df, nan_proxy_df,
                    selected_method, select_input
    """
    rng = np.random.default_rng(SEED)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # §6.1 high-demand threshold: raw q50, full evaluation window (all 11 quarters pooled)
    local_all = pd.Series(
        raw_q.index.tz_convert(TZ).normalize().tz_localize(None), index=raw_q.index
    )
    eval_window = (local_all >= pd.Timestamp(EVAL_START)) & (local_all <= pd.Timestamp(EVAL_END))
    daily_max_q50 = raw_q.loc[eval_window, "q50"].groupby(local_all[eval_window]).max()
    threshold_95 = (
        float(np.percentile(daily_max_q50.values, 95)) if len(daily_max_q50) else float("nan")
    )
    high_demand_dates: set = set(
        daily_max_q50[daily_max_q50 >= threshold_95].index.map(lambda ts: ts.date())
    )

    bank_hol_dates: set = set()
    for yr in range(2023, 2026):
        bank_hol_dates |= bank_holidays_ew(yr)

    all_metric_rows: list[dict] = []
    all_nan_rows: list[dict] = []
    select_input: dict[str, dict] = {}

    for method in METHODS:
        print(f"  Applying {method} ...")
        cal_q = apply_calibration_daily(
            raw_q, y, temp_proxy, method, window_days=365, apply_from=EVAL_START
        )
        hh_df = _add_hh_metrics(cal_q, y)
        hh_df = _add_flags(hh_df, temp_proxy, obs_temp_daily, high_demand_dates, bank_hol_dates)

        local_norm = pd.Series(
            hh_df.index.tz_convert(TZ).normalize().tz_localize(None), index=hh_df.index
        )
        pooled_parts: list[pd.DataFrame] = []

        for quarter, q_start, q_end in EVAL_QUARTERS:
            q_mask = (local_norm >= pd.Timestamp(q_start)) & (local_norm <= pd.Timestamp(q_end))
            hh_q = hh_df[q_mask]

            if len(hh_q) == 0:
                all_nan_rows.append({"quarter": quarter, "method": method, "n_nan_proxy_days": 0})
                continue

            day_q = _day_level(hh_q)
            all_nan_rows.append({
                "quarter": quarter,
                "method": method,
                "n_nan_proxy_days": int(day_q["is_nan_proxy"].sum()),
            })
            all_metric_rows.extend(_metric_rows(day_q, quarter, method, rng))
            pooled_parts.append(day_q)

        # Pooled across all eval quarters (excludes 2024-Q1 since that quarter is not in EVAL_QUARTERS)
        if pooled_parts:
            day_pooled = pd.concat(pooled_parts)
            p_rows = _metric_rows(day_pooled, "pooled", method, rng)
            all_metric_rows.extend(p_rows)

            # Build select_method input from pooled "all", "cold_proxy", "high_demand"
            p_lookup = {(r["condition_key"], r["metric"]): r["mean"] for r in p_rows}
            select_input[method] = {
                "coverage_90_all": p_lookup.get(("all", "covered_90"), float("nan")),
                "coverage_90_cold": p_lookup.get(("cold_proxy", "covered_90"), float("nan")),
                "coverage_90_high": p_lookup.get(("high_demand", "covered_90"), float("nan")),
                "width_90": p_lookup.get(("all", "width_90"), float("nan")),
                "winkler": p_lookup.get(("all", "winkler"), float("nan")),
            }

    metrics_df = pd.DataFrame(all_metric_rows)
    nan_proxy_df = pd.DataFrame(all_nan_rows)
    quarter_df = metrics_df[metrics_df["quarter"] != "pooled"].copy()
    pooled_df = metrics_df[metrics_df["quarter"] == "pooled"].copy()

    # §7 method selection
    selected_method = (
        select_method(select_input)
        if "baseline" in select_input
        else "baseline"
    )
    print(f"\n  Selected method (§7): {selected_method}")

    # Write outputs
    quarter_df.to_csv(out_dir / "metrics_by_quarter.csv", index=False)
    pooled_df.to_csv(out_dir / "metrics_pooled.csv", index=False)
    nan_proxy_df.to_csv(out_dir / "nan_proxy_counts.csv", index=False)
    (out_dir / "selection.txt").write_text(
        f"selected_method: {selected_method}\n\n"
        f"select_input:\n{json.dumps(select_input, indent=2, default=str)}\n",
        encoding="utf-8",
    )
    print(f"  Outputs written to {out_dir}")

    return {
        "metrics_df": metrics_df,
        "quarter_df": quarter_df,
        "pooled_df": pooled_df,
        "nan_proxy_df": nan_proxy_df,
        "selected_method": selected_method,
        "select_input": select_input,
    }


def run() -> dict:
    """Load development data and run evaluation, writing outputs to outputs/v2_cs2_rolling/."""
    print("CS-2b: Rolling evaluation — loading data ...")
    raw_q, y, temp_proxy = load_development_data()

    # Observed temperatures for outcome-based cold coverage (reporting only)
    demand = pd.read_parquet(DEMAND_PATH, columns=["temperature_2m_gb_mean"])
    obs_hh = demand["temperature_2m_gb_mean"].reindex(raw_q.index)
    obs_local = pd.Series(obs_hh.values, index=raw_q.index.tz_convert(TZ))
    obs_daily = obs_local.resample("D").mean()
    obs_temp_daily = pd.Series(obs_daily.values, index=[d.date() for d in obs_daily.index])

    return evaluate(raw_q, y, temp_proxy, obs_temp_daily, out_dir=OUT_DIR)


if __name__ == "__main__":
    run()
