"""
CS-2b: Rolling evaluation of all four conditional calibration methods.

Loads development data, applies each method over §5 evaluation quarters
(2023-Q1 to Q4; 2024-Q2 to Q4; 2025-Q1 to Q4 — 11 quarters; 2024-Q1 excluded),
computes §6 metrics with block-bootstrap 95% CIs, and calls select_method.

This file is committed BEFORE any real evaluation run (pre-registration CS-2b).
Outputs go to outputs/v2_cs2_rolling/ only. No 2026 data is loaded.

Stage 2b additions (committed before first run):
  (a) NaN actual demand: half-hours with missing y are dropped before any metric;
      count reported in data_quality_counts.csv.
  (b) Sanity check in run(): baseline Coverage_90 vs CS-1 reference values written
      to sanity_check.txt; raises ValueError if 2024-25 differs by >0.5 pp.
  (c) Fallback report (reporting only): per-quarter share of eval days per stratum
      where mondrian / mondrian_extended fell back to global correction.
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
    COLD_THRESHOLD_C,
    MIN_DAYS_STRATUM,
    apply_calibration_daily,
    assign_stratum,
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

# CS-1 reference coverage values used in the sanity check (§ sanity check)
CS1_COV_2024_25 = 90.5   # EXP-004 / CS-1 overall 2024-25 (cloud-generated Batch 4)
CS1_COV_2023 = 92.5      # EXP-003 / CS-1 overall 2023 (rounded from 92.47%)
# Amendment 2 addendum: tolerance widened from 0.5 pp to 1.0 pp to allow for the
# Mac/cloud prediction difference (see §12 addendum in cs2_preregistration.md).
SANITY_TOL_PP = 1.0      # maximum permitted deviation for 2024-25

_TAUS = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
_QCOLS = ["q05", "q10", "q25", "q50", "q75", "q90", "q95"]

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
    """Block-bootstrap by calendar day; return (mean, ci_low_95, ci_high_95)."""
    n = len(vals)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    idx = rng.integers(0, n, size=(N_BOOT, n))
    boot_means = vals[idx].mean(axis=1)
    return (
        float(vals.mean()),
        float(np.percentile(boot_means, 2.5)),
        float(np.percentile(boot_means, 97.5)),
    )


# ---------------------------------------------------------------------------
# Half-hourly metrics  (a: NaN y dropped here)
# ---------------------------------------------------------------------------

def _add_hh_metrics(cal_q: pd.DataFrame, y: pd.Series) -> pd.DataFrame:
    """Add metric columns to calibrated-quantile df.

    Half-hours where actual demand y is NaN are dropped before any metric
    is computed (stage 2b item a). The returned DataFrame is a strict subset
    of cal_q rows.
    """
    df = cal_q[_QCOLS].copy()
    df["y"] = y.reindex(cal_q.index)
    df = df.dropna(subset=["y"])          # drop missing actuals before metrics

    df["covered_90"] = (df["y"] >= df["q05"]) & (df["y"] <= df["q95"])
    df["covered_80"] = (df["y"] >= df["q10"]) & (df["y"] <= df["q90"])
    df["covered_50"] = (df["y"] >= df["q25"]) & (df["y"] <= df["q75"])
    df["width_90"] = df["q95"] - df["q05"]
    df["winkler"] = (
        df["width_90"]
        + 20.0 * np.maximum(df["q05"] - df["y"], 0.0)
        + 20.0 * np.maximum(df["y"] - df["q95"], 0.0)
    )
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
    df = df.copy()
    local = df.index.tz_convert(TZ)
    df["date"] = local.date
    df["month"] = local.month

    proxy_num = pd.to_numeric(df["date"].map(temp_proxy), errors="coerce")
    df["is_nan_proxy"] = proxy_num.isna()
    df["is_cold_proxy"] = (proxy_num < COLD_THRESHOLD_C).fillna(False)

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
# Metric rows
# ---------------------------------------------------------------------------

def _metric_rows(
    day_df: pd.DataFrame,
    quarter: str,
    method: str,
    rng: np.random.Generator,
) -> list[dict]:
    rows = []
    for cond_key, flag_col, label in _CONDITIONS:
        mask = day_df[flag_col].astype(bool) if flag_col else pd.Series(True, index=day_df.index)
        for metric in METRIC_COLS:
            vals = day_df.loc[mask, metric].values.astype(float)
            mean, lo, hi = _block_bootstrap(vals, rng)
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
# (c) Fallback report — reporting only, no calibration change
# ---------------------------------------------------------------------------

def _compute_fallback_summary(
    raw_q: pd.DataFrame,
    temp_proxy: pd.Series,
    high_demand_dates: set,
    eval_start: str = EVAL_START,
    eval_end: str = EVAL_END,
    window_days: int = 365,
) -> pd.DataFrame:
    """Compute per-eval-day stratum and fallback flags for mondrian/mondrian_extended.

    Uses global high-demand threshold (approximation; apply_calibration_daily uses
    window-specific threshold). Reporting only — no calibration is performed or changed.

    Returns one row per eval day with columns:
        date, stratum, mondrian_fallback (bool), mondrian_ext_fallback (bool).
    """
    local_all = pd.Series(
        raw_q.index.tz_convert(TZ).normalize().tz_localize(None), index=raw_q.index
    )
    daily_max_q50 = raw_q["q50"].groupby(local_all).max()
    all_days_ts = pd.DatetimeIndex(sorted(local_all.unique()))

    # Assign stratum for every day with data
    strata: dict[pd.Timestamp, str] = {}
    for day_ts in all_days_ts:
        day_date = day_ts.date()
        t = float(temp_proxy.get(day_date, float("nan")))
        mq50 = float(daily_max_q50.get(day_ts, float("nan")))
        # Use high_demand_dates (global threshold) as approximation
        is_hd = day_date in high_demand_dates
        threshold_approx = float("nan")  # used only as a flag reference
        strata[day_ts] = "cold" if t < COLD_THRESHOLD_C else ("high_demand" if is_hd else "normal")

    strata_s = pd.Series(strata)

    # Cumulative cold day count (for mondrian_extended)
    cold_indicator = (strata_s == "cold").astype(int)
    cold_cumsum = cold_indicator.cumsum()

    eval_start_ts = pd.Timestamp(eval_start)
    eval_end_ts = pd.Timestamp(eval_end)
    eval_days = all_days_ts[(all_days_ts >= eval_start_ts) & (all_days_ts <= eval_end_ts)]

    rows = []
    for day_ts in eval_days:
        window_start = day_ts - pd.Timedelta(days=window_days)
        # Window: days strictly before day_ts and after window_start
        w_idx = all_days_ts[(all_days_ts >= window_start) & (all_days_ts < day_ts)]
        day_stratum = strata_s.get(day_ts, "normal")

        # Mondrian: stratum days in rolling window
        w_strata = strata_s.reindex(w_idx)
        n_stratum = int((w_strata == day_stratum).sum())
        mondrian_fallback = n_stratum < MIN_DAYS_STRATUM

        # Mondrian extended: for cold days, check all history
        if day_stratum == "cold":
            # Number of cold days strictly before this day in full history
            pos = int((all_days_ts < day_ts).sum()) - 1
            n_cold_hist = int(cold_cumsum.iloc[pos]) if pos >= 0 else 0
            mondrian_ext_fallback = n_cold_hist < MIN_DAYS_STRATUM
        else:
            mondrian_ext_fallback = mondrian_fallback

        rows.append({
            "date": day_ts.date(),
            "stratum": day_stratum,
            "mondrian_fallback": int(mondrian_fallback),
            "mondrian_ext_fallback": int(mondrian_ext_fallback),
        })

    return pd.DataFrame(rows)


def _fallback_by_quarter(fallback_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate per-day fallback flags into per-quarter per-stratum summary."""
    rows = []
    fallback_df = fallback_df.copy()
    fallback_df["date_ts"] = pd.to_datetime(fallback_df["date"])

    for quarter, q_start, q_end in EVAL_QUARTERS:
        q_start_ts = pd.Timestamp(q_start)
        q_end_ts = pd.Timestamp(q_end)
        sub = fallback_df[
            (fallback_df["date_ts"] >= q_start_ts) & (fallback_df["date_ts"] <= q_end_ts)
        ]
        if len(sub) == 0:
            continue
        for stratum in ["cold", "high_demand", "normal"]:
            s = sub[sub["stratum"] == stratum]
            n = len(s)
            if n == 0:
                continue
            m_fb = int(s["mondrian_fallback"].sum())
            me_fb = int(s["mondrian_ext_fallback"].sum())
            rows.append({
                "quarter": quarter,
                "stratum": stratum,
                "total_days": n,
                "mondrian_fallback_days": m_fb,
                "mondrian_fallback_share_pct": round(100.0 * m_fb / n, 1),
                "mondrian_ext_fallback_days": me_fb,
                "mondrian_ext_fallback_share_pct": round(100.0 * me_fb / n, 1),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# (b) Sanity check — written and checked inside run(), not evaluate()
# ---------------------------------------------------------------------------

def _sanity_check(
    sanity_data: dict,
    out_dir: Path,
    ref_2024_25: float = CS1_COV_2024_25,
    ref_2023: float = CS1_COV_2023,
    tol: float = SANITY_TOL_PP,
) -> None:
    """Write sanity_check.txt; raise ValueError if 2024-25 baseline coverage is off.

    Parameters
    ----------
    sanity_data  : dict with keys "cov_2023" and "cov_2024_25" (% half-hour coverage)
    out_dir      : directory where sanity_check.txt is written
    ref_2024_25  : CS-1 reference for 2024-03-08..2025-12-31 (default 90.5%)
    ref_2023     : CS-1 reference for 2023 (default 92.5%)
    tol          : tolerance in pp for the 2024-25 comparison (default 0.5)
    """
    cov_2023 = sanity_data.get("cov_2023", float("nan"))
    cov_2024_25 = sanity_data.get("cov_2024_25", float("nan"))
    diff_2023 = cov_2023 - ref_2023
    diff_2024_25 = cov_2024_25 - ref_2024_25
    result_str = "PASS" if (np.isfinite(diff_2024_25) and abs(diff_2024_25) <= tol) else "FAIL"

    lines = [
        "CS-2b baseline sanity check (stage 2b item b)",
        "=" * 50,
        "Period: 2023 (all half-hours in development data)",
        f"  CS-1 reference : {ref_2023:.1f} %",
        f"  CS-2b baseline : {cov_2023:.2f} %",
        f"  Difference     : {diff_2023:+.2f} pp  (not a failure condition)",
        "",
        "Period: 2024-03-08 to 2025-12-31",
        f"  CS-1 reference : {ref_2024_25:.1f} %",
        f"  CS-2b baseline : {cov_2024_25:.2f} %",
        f"  Difference     : {diff_2024_25:+.2f} pp",
        f"  Tolerance      : ± {tol:.1f} pp",
        f"  Result         : {result_str}",
    ]
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "sanity_check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

    if not np.isfinite(diff_2024_25):
        raise ValueError(
            "Sanity check: 2024-25 baseline Coverage_90 is NaN — "
            "likely no data in that period."
        )
    if abs(diff_2024_25) > tol:
        raise ValueError(
            f"Sanity check FAILED: 2024-25 baseline Coverage_90 = {cov_2024_25:.2f}%, "
            f"expected {ref_2024_25:.1f}% ± {tol:.1f} pp (diff = {diff_2024_25:+.2f} pp). "
            "Evaluation stopped before writing selection.txt. "
            "Check that load_development_data() returned the correct quantiles and actuals."
        )


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

    Does NOT write selection.txt — that is written by run() after the sanity
    check passes (stage 2b item b).

    Parameters
    ----------
    raw_q         : UTC-indexed DataFrame of raw (uncalibrated) quantiles (q05–q95)
    y             : UTC-indexed Series of actual underlying demand
    temp_proxy    : local date-indexed Series of temperature proxy (NaN if unavailable)
    obs_temp_daily: local date-indexed Series of observed daily mean temperature
                    (outcome-based cold coverage, labelled "reporting only")
    out_dir       : directory for output files (created if needed)

    Returns
    -------
    dict with keys: metrics_df, quarter_df, pooled_df, data_quality_df,
                    fallback_df, selected_method, select_input, sanity_data
    """
    rng = np.random.default_rng(SEED)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # §6.1 high-demand threshold: raw q50, full evaluation window
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

    # (a) Pre-compute NaN-y counts per quarter — same for all methods
    y_aligned = y.reindex(raw_q.index)
    nan_y_mask = y_aligned.isna()
    nan_y_per_quarter: dict[str, int] = {}
    local_q_check = local_all  # already computed above
    for quarter, q_start, q_end in EVAL_QUARTERS:
        q_m = (local_q_check >= pd.Timestamp(q_start)) & (local_q_check <= pd.Timestamp(q_end))
        nan_y_per_quarter[quarter] = int(nan_y_mask[q_m].sum())

    all_metric_rows: list[dict] = []
    all_dq_rows: list[dict] = []   # data_quality rows
    select_input: dict[str, dict] = {}
    sanity_data: dict[str, float] = {}

    for method in METHODS:
        print(f"  Applying {method} ...")
        cal_q = apply_calibration_daily(
            raw_q, y, temp_proxy, method, window_days=365, apply_from=EVAL_START
        )
        hh_df = _add_hh_metrics(cal_q, y)   # NaN y rows already dropped
        hh_df = _add_flags(hh_df, temp_proxy, obs_temp_daily, high_demand_dates, bank_hol_dates)

        # (b) Collect sanity_data from baseline method
        if method == "baseline":
            local_b = pd.Series(
                hh_df.index.tz_convert(TZ).normalize().tz_localize(None), index=hh_df.index
            )
            m2023 = (local_b >= pd.Timestamp("2023-01-01")) & (local_b <= pd.Timestamp("2023-12-31"))
            m2024 = local_b >= pd.Timestamp("2024-03-08")
            sanity_data["cov_2023"] = float(hh_df.loc[m2023, "covered_90"].mean()) * 100.0
            sanity_data["cov_2024_25"] = float(hh_df.loc[m2024, "covered_90"].mean()) * 100.0

        local_norm = pd.Series(
            hh_df.index.tz_convert(TZ).normalize().tz_localize(None), index=hh_df.index
        )
        pooled_parts: list[pd.DataFrame] = []

        for quarter, q_start, q_end in EVAL_QUARTERS:
            q_mask = (local_norm >= pd.Timestamp(q_start)) & (local_norm <= pd.Timestamp(q_end))
            hh_q = hh_df[q_mask]

            n_nan_proxy = 0
            if len(hh_q) > 0:
                day_q = _day_level(hh_q)
                n_nan_proxy = int(day_q["is_nan_proxy"].sum())
                all_metric_rows.extend(_metric_rows(day_q, quarter, method, rng))
                pooled_parts.append(day_q)

            # (a) Data quality row: NaN y (same for all methods), NaN proxy
            all_dq_rows.append({
                "quarter": quarter,
                "method": method,
                "n_nan_y_dropped": nan_y_per_quarter.get(quarter, 0),
                "n_nan_proxy_days": n_nan_proxy,
            })

        if pooled_parts:
            day_pooled = pd.concat(pooled_parts)
            p_rows = _metric_rows(day_pooled, "pooled", method, rng)
            all_metric_rows.extend(p_rows)
            p_lookup = {(r["condition_key"], r["metric"]): r["mean"] for r in p_rows}
            select_input[method] = {
                "coverage_90_all":  p_lookup.get(("all",         "covered_90"), float("nan")),
                "coverage_90_cold": p_lookup.get(("cold_proxy",  "covered_90"), float("nan")),
                "coverage_90_high": p_lookup.get(("high_demand", "covered_90"), float("nan")),
                "width_90":         p_lookup.get(("all",         "width_90"),   float("nan")),
                "winkler":          p_lookup.get(("all",         "winkler"),    float("nan")),
            }

    metrics_df = pd.DataFrame(all_metric_rows)
    data_quality_df = pd.DataFrame(all_dq_rows)
    quarter_df = metrics_df[metrics_df["quarter"] != "pooled"].copy()
    pooled_df = metrics_df[metrics_df["quarter"] == "pooled"].copy()

    # §7 method selection
    selected_method = (
        select_method(select_input) if "baseline" in select_input else "baseline"
    )
    print(f"\n  Selected method (§7): {selected_method}")

    # (c) Fallback report
    print("  Computing fallback report (reporting only) ...")
    fallback_raw = _compute_fallback_summary(raw_q, temp_proxy, high_demand_dates)
    fallback_df = _fallback_by_quarter(fallback_raw)

    # Write outputs (selection.txt written by run() after sanity check)
    quarter_df.to_csv(out_dir / "metrics_by_quarter.csv", index=False)
    pooled_df.to_csv(out_dir / "metrics_pooled.csv", index=False)
    data_quality_df.to_csv(out_dir / "data_quality_counts.csv", index=False)
    fallback_df.to_csv(out_dir / "fallback_report.csv", index=False)
    print(f"  Outputs written to {out_dir}")

    return {
        "metrics_df": metrics_df,
        "quarter_df": quarter_df,
        "pooled_df": pooled_df,
        "data_quality_df": data_quality_df,
        "fallback_df": fallback_df,
        "selected_method": selected_method,
        "select_input": select_input,
        "sanity_data": sanity_data,
    }


def run() -> dict:
    """Load development data, run evaluation, check sanity, and write selection.txt."""
    print("CS-2b: Rolling evaluation — loading data ...")
    raw_q, y, temp_proxy = load_development_data()

    # Observed temperatures for outcome-based cold coverage (reporting only)
    demand = pd.read_parquet(DEMAND_PATH, columns=["temperature_2m_gb_mean"])
    obs_hh = demand["temperature_2m_gb_mean"].reindex(raw_q.index)
    obs_local = pd.Series(obs_hh.values, index=raw_q.index.tz_convert(TZ))
    obs_daily = obs_local.resample("D").mean()
    obs_temp_daily = pd.Series(obs_daily.values, index=[d.date() for d in obs_daily.index])

    result = evaluate(raw_q, y, temp_proxy, obs_temp_daily, out_dir=OUT_DIR)

    # (b) Sanity check — raises before selection.txt if 2024-25 coverage is off
    _sanity_check(result["sanity_data"], out_dir=OUT_DIR)

    # Write selection.txt only after sanity check passes
    (OUT_DIR / "selection.txt").write_text(
        f"selected_method: {result['selected_method']}\n\n"
        f"select_input:\n{json.dumps(result['select_input'], indent=2, default=str)}\n",
        encoding="utf-8",
    )

    return result


if __name__ == "__main__":
    run()
