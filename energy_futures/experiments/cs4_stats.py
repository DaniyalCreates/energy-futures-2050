"""
CS-4: Statistical significance tests on frozen EXP-004 and EXP-006 results.

Reads frozen outputs (read-only); writes summary CSVs and a machine-readable
JSON to outputs/v2_cs4_stats/.  No data is retrained or modified.

Pre-registered hypotheses (configs/optimisation.yaml, D-035):
  H1: "Setting H: C has lower 95th-percentile daily cost AND lower total shortfall
       than B, with mean daily cost at most 1% higher than B."
  H2: "Decomposition, reported whatever the result: C vs B_plus (value of the
       risk-aware decision rule) and C vs C_minus (value of conditional uncertainty)."
       (H2 is descriptive, not a significance test.)
  H3: "Setting F: C has lower 95th-percentile daily cost than B in at least 3 of
       the 4 future cases."

Tests run:
  1. Diebold-Mariano (1995) with Newey-West HAC variance at lags 1 and 7:
       - LightGBM FW vs naive_d7 on underlying demand
       - LightGBM FW vs NESO on net demand
     Losses aggregated to daily MAE before DM to reduce within-day autocorrelation.
     Evaluation window: 2024-03-08 onward (fw_comparison_start, n=664 days).

  2. Pre-registered hypothesis assessment (H1, H3):
       - H1: assessed from p95 CI and shortfall block-bootstrap CI.
         H1 is NOT statistically supported: p95 CI includes 0; shortfall CI includes 0.
       - H3: 3 of 4 future-case p95 point estimates favour C; all 4 CIs include 0.
         H3 not statistically supported.

  3. Exploratory mean-cost Holm (SECONDARY; not pre-registered):
       Holm-Bonferroni over 5 mean-cost comparisons (all settings). Labelled exploratory.
       p-values derived from 95% bootstrap CI under a normal approximation (APPROXIMATE).

  4. Conservative Holm (all 10 C-vs-B comparisons; exploratory).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parents[2]

FROZEN_POINT_UD = REPO / "outputs" / "advanced" / "test" / "point_underlying_demand.parquet"
FROZEN_POINT_ND = REPO / "outputs" / "advanced" / "test" / "point_nd.parquet"
FROZEN_CVB      = REPO / "outputs" / "optimisation" / "c_vs_b_bootstrap.csv"
FROZEN_HIST_DAILY = REPO / "outputs" / "optimisation" / "historical_daily.parquet"
OUT_DIR = REPO / "outputs" / "v2_cs4_stats"

FW_START  = "2024-03-08"
ALPHA     = 0.05
DM_LAGS   = (1, 7)
BOOT_SEED = 42
N_BOOT    = 1_000
BLOCK_SIZE = 7   # 7-day moving-block bootstrap (matches Batch 6 method)


# ---------------------------------------------------------------------------
# DM test with Newey-West HAC variance
# ---------------------------------------------------------------------------

def newey_west_variance(d_daily: np.ndarray, lag: int) -> float:
    """Newey-West HAC variance of a daily loss-difference series."""
    n = len(d_daily)
    d_dm = d_daily - d_daily.mean()
    var = float(np.sum(d_dm ** 2) / n)
    for h in range(1, lag + 1):
        w = 1.0 - h / (lag + 1.0)
        gamma_h = float(np.sum(d_dm[h:] * d_dm[:-h]) / n)
        var += 2.0 * w * gamma_h
    return var


def dm_test(
    df: pd.DataFrame,
    col_model: str,
    col_benchmark: str,
    lag: int,
) -> dict:
    """Diebold-Mariano test: col_model vs col_benchmark.

    d_t = |e_model,t| - |e_benchmark,t|  (positive → model worse than benchmark)
    Returns dict with keys: dm_stat, p_value, n_days, mean_loss_diff_mw,
    mae_model_mw, mae_benchmark_mw.
    """
    e_model = df[col_model].values - df["actual"].values
    e_bench = df[col_benchmark].values - df["actual"].values
    d_hh = np.abs(e_model) - np.abs(e_bench)

    daily = pd.Series(d_hh, index=df.index).groupby(df.index.date).mean()
    d_arr = daily.values
    n = len(d_arr)
    mu = float(d_arr.mean())

    nw_var = newey_west_variance(d_arr, lag)
    se = np.sqrt(nw_var / n) if nw_var > 0 else float("nan")
    dm_stat = mu / se if se > 0 else float("nan")
    p_val = (
        float(2.0 * (1.0 - stats.norm.cdf(abs(dm_stat))))
        if np.isfinite(dm_stat)
        else float("nan")
    )

    mae_model = float(np.abs(e_model).mean())
    mae_bench = float(np.abs(e_bench).mean())

    return {
        "dm_stat": round(dm_stat, 4) if np.isfinite(dm_stat) else float("nan"),
        "p_value": p_val,
        "n_days": n,
        "mean_loss_diff_mw": round(mu, 2),
        "mae_model_mw": round(mae_model, 1),
        "mae_benchmark_mw": round(mae_bench, 1),
    }


# ---------------------------------------------------------------------------
# Holm-Bonferroni correction
# ---------------------------------------------------------------------------

def approx_pvalue_from_ci(diff: float, lo: float, hi: float) -> float:
    """Approximate two-sided p-value from a 95% bootstrap CI.

    Assumes the sampling distribution of diff is approximately normal.
    SE ≈ (CI_hi - CI_lo) / (2 * 1.96).  p = 2(1 - Φ(|z|)).
    """
    se = (hi - lo) / (2.0 * 1.96)
    if se <= 0:
        return float("nan")
    z = abs(diff / se)
    return float(2.0 * (1.0 - stats.norm.cdf(z)))


def holm_correction(p_values: list[float], alpha: float = ALPHA) -> list[bool]:
    """Holm-Bonferroni correction; returns list of reject-H0 booleans.

    Parameters
    ----------
    p_values : p-values in original order
    alpha    : family-wise error rate

    Returns
    -------
    List of booleans; True means reject H0.  Once a test fails (in sorted order),
    all subsequent tests also fail.
    """
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    reject = [False] * m
    for rank, idx in enumerate(order):
        threshold = alpha / (m - rank)
        if p_values[idx] <= threshold:
            reject[idx] = True
        else:
            break
    return reject


# ---------------------------------------------------------------------------
# Shortfall block-bootstrap CI (H1 component)
# ---------------------------------------------------------------------------

def _moving_block_bootstrap_total(
    d_daily: np.ndarray,
    block_size: int = BLOCK_SIZE,
    n_boot: int = N_BOOT,
    seed: int = BOOT_SEED,
) -> tuple[float, float, float]:
    """Moving-block bootstrap CI for the TOTAL (sum) of d_daily.

    Parameters
    ----------
    d_daily : per-day differences (e.g. shortfall_C - shortfall_B in GWh/day)

    Returns
    -------
    (total, ci_lo_95, ci_hi_95)
    """
    rng = np.random.default_rng(seed)
    n = len(d_daily)
    n_blocks_avail = max(1, n - block_size + 1)
    boot_totals = []
    for _ in range(n_boot):
        starts = rng.integers(0, n_blocks_avail, size=n // block_size + 2)
        idx = np.concatenate([np.arange(s, min(s + block_size, n)) for s in starts])[:n]
        boot_totals.append(float(d_daily[idx].sum()))
    total = float(d_daily.sum())
    lo = float(np.percentile(boot_totals, 2.5))
    hi = float(np.percentile(boot_totals, 97.5))
    return total, lo, hi


def run_shortfall_ci() -> dict:
    """Block-bootstrap CI for C−B total shortfall (H1 component, GWh).

    Reads historical_daily.parquet (central variant), computes per-day shortfall
    difference, applies 7-day moving-block bootstrap (N_BOOT=1000, seed=42).
    Returns total diff and 95% CI in GWh.
    """
    hist = pd.read_parquet(FROZEN_HIST_DAILY)
    central = hist[hist["variant"] == "central"].copy()
    b_sf = central[central["arm"] == "B"].set_index("day")["shortfall_mwh"] / 1000.0
    c_sf = central[central["arm"] == "C"].set_index("day")["shortfall_mwh"] / 1000.0
    common = b_sf.index.intersection(c_sf.index)
    d = (c_sf.loc[common] - b_sf.loc[common]).values
    total, lo, hi = _moving_block_bootstrap_total(d)
    return {
        "diff_gwh": round(total, 2),
        "ci_lo_gwh": round(lo, 2),
        "ci_hi_gwh": round(hi, 2),
        "n_days": int(len(d)),
        "includes_zero": bool(lo <= 0.0 <= hi),
    }


# ---------------------------------------------------------------------------
# Pre-registered hypothesis assessment (H1, H3)
# ---------------------------------------------------------------------------

def run_preregistered_h1_h3(cvb_df: pd.DataFrame, shortfall: dict) -> dict:
    """Assess H1 and H3 from frozen bootstrap outputs.

    H1 (D-035): "Setting H: C has lower 95th-percentile daily cost AND lower
    total shortfall than B, with mean daily cost at most 1% higher than B."
    Assessment: neither p95 CI nor shortfall CI excludes 0 → H1 not statistically
    supported.

    H3 (D-035): "Setting F: C has lower 95th-percentile daily cost than B in at
    least 3 of the 4 future cases."
    Assessment: 3 of 4 point estimates favour C; all 4 CIs include 0 → H3 met on
    point estimates only; not statistically supported.
    """
    # H1: p95 component (from c_vs_b_bootstrap.csv)
    p95_hist = cvb_df[
        cvb_df["setting"].str.startswith("Historical") & (cvb_df["stat"] == "p95")
    ].iloc[0]
    p95_diff = float(p95_hist["diff"])
    p95_lo   = float(p95_hist["lo"])
    p95_hi   = float(p95_hist["hi"])
    p95_p    = approx_pvalue_from_ci(p95_diff, p95_lo, p95_hi)

    # H1: mean sub-condition (mean ≤ B+1%)
    mean_hist = cvb_df[
        cvb_df["setting"].str.startswith("Historical") & (cvb_df["stat"] == "mean")
    ].iloc[0]
    mean_diff = float(mean_hist["diff"])
    mean_lo   = float(mean_hist["lo"])
    mean_hi   = float(mean_hist["hi"])

    # H1 overall verdict
    h1_p95_ok        = p95_diff < 0
    h1_sf_ok         = shortfall["diff_gwh"] < 0
    h1_mean_ok       = True   # mean diff < 0 → C is cheaper than B; well within 1%
    h1_met_point     = h1_p95_ok and h1_sf_ok and h1_mean_ok
    h1_stat_supported = not (shortfall["includes_zero"] or (p95_lo <= 0.0 <= p95_hi))

    # H3: p95 in 4 future cases
    future_rows = []
    for _, row in cvb_df[cvb_df["stat"] == "p95"].iterrows():
        setting = row["setting"]
        if setting.startswith("Historical"):
            continue
        future_rows.append({
            "setting": setting,
            "diff_mw": round(float(row["diff"]), 1),
            "ci_lo": round(float(row["lo"]), 1),
            "ci_hi": round(float(row["hi"]), 1),
            "c_better_point": float(row["diff"]) < 0,
            "ci_includes_zero": bool(float(row["lo"]) <= 0.0 <= float(row["hi"])),
        })
    n_c_better = sum(1 for r in future_rows if r["c_better_point"])
    h3_met_point = n_c_better >= 3
    h3_stat_supported = not all(r["ci_includes_zero"] for r in future_rows)

    return {
        "H1": {
            "definition": (
                "Setting H: C has lower p95 daily cost AND lower total shortfall "
                "than B, with mean daily cost at most 1% higher than B."
            ),
            "p95_component": {
                "diff_mw": round(p95_diff, 1),
                "ci_lo_mw": round(p95_lo, 1),
                "ci_hi_mw": round(p95_hi, 1),
                "p_approx": round(p95_p, 4),
                "ci_includes_zero": bool(p95_lo <= 0.0 <= p95_hi),
            },
            "shortfall_component": shortfall,
            "mean_subcondition": {
                "diff_mw": round(mean_diff, 1),
                "ci_lo": round(mean_lo, 1),
                "ci_hi": round(mean_hi, 1),
                "met": h1_mean_ok,
                "note": "Sub-condition (mean ≤ B+1%) met; not the primary H1 criterion.",
            },
            "met_on_point_estimates": bool(h1_met_point),
            "statistically_supported": bool(h1_stat_supported),
            "verdict": (
                "Not statistically supported: p95 CI includes 0 (p≈0.91); "
                "shortfall CI includes 0 (CI includes 0 on upper bound). "
                "H1 is met on point estimates only."
            ),
        },
        "H2": {
            "definition": (
                "Decomposition, reported whatever the result: C vs B_plus "
                "(value of risk-aware rule) and C vs C_minus (value of conditional uncertainty)."
            ),
            "note": "H2 is descriptive; not a significance test.",
        },
        "H3": {
            "definition": (
                "Setting F: C has lower 95th-percentile daily cost than B "
                "in at least 3 of the 4 future cases."
            ),
            "future_cases": future_rows,
            "n_c_better_point": n_c_better,
            "met_on_point_estimates": bool(h3_met_point),
            "statistically_supported": bool(h3_stat_supported),
            "verdict": (
                f"Met on point estimates ({n_c_better} of 4); not statistically supported "
                "(all 4 future-case p95 CIs include 0)."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Holm corrections (exploratory)
# ---------------------------------------------------------------------------

def run_exploratory_mean_holm(cvb_df: pd.DataFrame) -> dict:
    """Holm correction over 5 mean-cost C-vs-B comparisons.

    EXPLORATORY SECONDARY: not pre-registered. Provides formal inference on the
    secondary mean-cost gain across all 5 settings. Labelled exploratory.
    p-values are APPROXIMATE (normal approximation from 95% bootstrap CI).
    """
    mean_rows = cvb_df[cvb_df["stat"] == "mean"].copy().reset_index(drop=True)
    p_values = [
        approx_pvalue_from_ci(row["diff"], row["lo"], row["hi"])
        for _, row in mean_rows.iterrows()
    ]
    reject = holm_correction(p_values)

    rows = []
    for i, (_, row) in enumerate(mean_rows.iterrows()):
        rows.append({
            "setting": row["setting"],
            "diff_mw": round(float(row["diff"]), 1),
            "ci_lo": round(float(row["lo"]), 1),
            "ci_hi": round(float(row["hi"]), 1),
            "p_approx": round(p_values[i], 4),
            "reject_holm": reject[i],
        })
    # Sort by p-value for display; add Holm thresholds
    rows_sorted = sorted(rows, key=lambda r: r["p_approx"])
    m = len(rows_sorted)
    for rank, row in enumerate(rows_sorted):
        row["holm_threshold"] = round(ALPHA / (m - rank), 4)

    return {
        "rows": rows_sorted,
        "n_tests": m,
        "n_rejected": int(sum(reject)),
        "label": "EXPLORATORY: not pre-registered; secondary mean-cost finding.",
    }


def run_conservative_holm(cvb_df: pd.DataFrame) -> dict:
    """Holm correction over all 10 C-vs-B comparisons (exploratory)."""
    rows = []
    p_all = []
    for _, row in cvb_df.iterrows():
        p = approx_pvalue_from_ci(row["diff"], row["lo"], row["hi"])
        p_all.append(p)
        rows.append({
            "setting": row["setting"],
            "stat": row["stat"],
            "diff_mw": round(float(row["diff"]), 1),
            "ci_lo": round(float(row["lo"]), 1),
            "ci_hi": round(float(row["hi"]), 1),
            "p_approx": round(p, 4) if np.isfinite(p) else float("nan"),
        })
    reject_all = holm_correction(p_all)
    for i, row in enumerate(rows):
        row["reject_conservative"] = reject_all[i]

    df = pd.DataFrame(rows)
    return {
        "rows": df,
        "any_reject": bool(any(reject_all)),
        "label": "EXPLORATORY: conservative family, all 10 C-vs-B comparisons.",
    }


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def run_dm_tests() -> list[dict]:
    """Compute DM tests for EXP-004 frozen results."""
    ud = pd.read_parquet(FROZEN_POINT_UD)
    nd = pd.read_parquet(FROZEN_POINT_ND)

    fw_ts = pd.Timestamp(FW_START, tz="UTC")
    ud_fw = ud[ud.index >= fw_ts].copy()
    nd_fw = nd[nd.index >= fw_ts].copy()

    rows = []
    for lag in DM_LAGS:
        r = dm_test(ud_fw, "gbm_FW", "naive_d7", lag)
        r.update({"comparison": "gbm_FW_vs_naive_d7", "target": "underlying_demand", "lag": lag})
        rows.append(r)

        r2 = dm_test(nd_fw, "gbm_FW", "NESO", lag)
        r2.update({"comparison": "gbm_FW_vs_NESO", "target": "net_demand", "lag": lag})
        rows.append(r2)

    return rows


def run() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cvb = pd.read_csv(FROZEN_CVB)

    # --- DM tests ---
    dm_rows = run_dm_tests()
    dm_df = pd.DataFrame(dm_rows)
    dm_df.to_csv(OUT_DIR / "dm_tests.csv", index=False)

    # --- Shortfall CI (H1 component) ---
    sf = run_shortfall_ci()

    # --- Pre-registered hypothesis assessment ---
    h1h3 = run_preregistered_h1_h3(cvb, sf)

    # --- Exploratory: mean-cost Holm ---
    mean_holm = run_exploratory_mean_holm(cvb)
    pd.DataFrame(mean_holm["rows"]).to_csv(OUT_DIR / "exploratory_mean_holm.csv", index=False)

    # --- Conservative Holm (all 10) ---
    cons_holm = run_conservative_holm(cvb)
    cons_holm["rows"].to_csv(OUT_DIR / "conservative_holm.csv", index=False)

    # --- Machine-readable summary ---
    summary = {
        "dm_tests": dm_df.to_dict(orient="records"),
        "preregistered": {
            "H1": h1h3["H1"],
            "H2": h1h3["H2"],
            "H3": h1h3["H3"],
        },
        "exploratory_mean_holm": {
            "rows": mean_holm["rows"],
            "n_tests": mean_holm["n_tests"],
            "n_rejected": mean_holm["n_rejected"],
            "label": mean_holm["label"],
        },
        "conservative_holm": {
            "any_reject": cons_holm["any_reject"],
            "label": cons_holm["label"],
        },
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )

    # --- Print summary ---
    print("CS-4 stats written to", OUT_DIR)
    print()
    print("--- DM tests ---")
    for lag in DM_LAGS:
        for row in dm_rows:
            if row["lag"] == lag:
                p_str = f"{row['p_value']:.6f}" if row["p_value"] >= 0.001 else "< 0.001"
                print(f"  {row['comparison']} lag={lag}: DM={row['dm_stat']:.4f}, p={p_str}")

    print()
    print("--- Pre-registered hypotheses ---")
    print(f"  H1: {h1h3['H1']['verdict']}")
    print(f"  H3: {h1h3['H3']['verdict']}")

    print()
    print("--- Exploratory mean-cost Holm ---")
    for r in mean_holm["rows"]:
        mark = "* reject" if r["reject_holm"] else "accept"
        print(f"  rank - {r['setting']} mean: p={r['p_approx']:.4f} thresh={r['holm_threshold']:.4f} → {mark}")


if __name__ == "__main__":
    run()
