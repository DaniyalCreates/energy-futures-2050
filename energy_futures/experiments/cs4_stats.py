"""
CS-4: Statistical significance tests on frozen EXP-004 and EXP-006 results.

Reads frozen outputs (read-only); writes summary CSVs and a machine-readable
JSON to outputs/v2_cs4_stats/.  No data is retrained or modified.

Tests run:
  1. Diebold-Mariano (1995) with Newey-West HAC variance at lags 1 and 7:
       - LightGBM FW vs naive_d7 on underlying demand
       - LightGBM FW vs NESO on net demand
     Losses aggregated to daily MAE before DM to reduce within-day autocorrelation.
     Evaluation window: 2024-03-08 onward (fw_comparison_start, n=664 days).

  2. Holm-Bonferroni correction on C-vs-B bootstrap CIs from EXP-006:
       Pre-specified family (H1, H2, H3 from D-035): H3 not testable from saved outputs.
       Conservative family: all 10 C-vs-B comparisons.
     p-values derived from 95% bootstrap CI under a normal approximation:
       SE ≈ (CI_hi - CI_lo) / (2 * 1.96); z = diff / SE; p = 2(1 - Φ(|z|)).
     These p-values are APPROXIMATE (normal approximation assumption).
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
FROZEN_CVB = REPO / "outputs" / "optimisation" / "c_vs_b_bootstrap.csv"
OUT_DIR = REPO / "outputs" / "v2_cs4_stats"

FW_START = "2024-03-08"   # first date with FW predictions (fw_comparison_start)
ALPHA = 0.05
DM_LAGS = (1, 7)


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

    d_t = |e_model,t| - |e_benchmark,t|  (positive → model worse)
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
    List of booleans; True means reject H0.  Once a test fails, all subsequent
    tests (in sorted order) also fail.
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


def run_holm() -> dict:
    """Compute Holm-corrected p-values for EXP-006 C-vs-B bootstrap CIs."""
    cvb = pd.read_csv(FROZEN_CVB)

    rows = []
    for _, row in cvb.iterrows():
        p = approx_pvalue_from_ci(row["diff"], row["lo"], row["hi"])
        rows.append({
            "setting": row["setting"],
            "stat": row["stat"],
            "diff": round(float(row["diff"]), 2),
            "ci_lo": round(float(row["lo"]), 2),
            "ci_hi": round(float(row["hi"]), 2),
            "p_approx": round(p, 4) if np.isfinite(p) else float("nan"),
        })

    df = pd.DataFrame(rows)
    p_all = df["p_approx"].tolist()

    # Pre-specified family: H1 and H2 from D-035 (H3 not testable from saved outputs)
    h1_idx = df[(df["setting"].str.startswith("Historical")) & (df["stat"] == "mean")].index[0]
    h2_idx = df[(df["setting"].str.startswith("Historical")) & (df["stat"] == "p95")].index[0]
    p_prespec_2 = [df.loc[h1_idx, "p_approx"], df.loc[h2_idx, "p_approx"]]
    reject_prespec_2 = holm_correction(p_prespec_2)

    # Pre-specified family with H3 included (m=3; H3 p-value not available)
    # H1 survives Holm with m=3: threshold α/3 = 0.0167; p(H1) = 0.007 < 0.0167 → survives
    h1_p = df.loc[h1_idx, "p_approx"]
    h1_survives_m3 = bool(h1_p <= ALPHA / 3.0)

    # Conservative family: all 10 tests
    reject_all = holm_correction(p_all)
    df["reject_conservative"] = reject_all

    return {
        "rows": df,
        "h1_idx": h1_idx,
        "h2_idx": h2_idx,
        "p_prespec_2": p_prespec_2,
        "reject_prespec_2": reject_prespec_2,
        "h1_p": h1_p,
        "h1_survives_m3": h1_survives_m3,
        "reject_conservative": reject_all,
    }


def run() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- DM tests ---
    dm_rows = run_dm_tests()
    dm_df = pd.DataFrame(dm_rows)
    dm_df.to_csv(OUT_DIR / "dm_tests.csv", index=False)

    # --- Holm correction ---
    holm = run_holm()
    holm["rows"].to_csv(OUT_DIR / "holm_cvb.csv", index=False)

    # --- Machine-readable summary ---
    summary = {
        "dm_tests": dm_df.to_dict(orient="records"),
        "holm": {
            "pre_specified_m2": {
                "h1_p": holm["h1_p"],
                "h1_reject": holm["reject_prespec_2"][0],
                "h1_threshold": round(ALPHA / 2, 4),
                "h2_p": holm["p_prespec_2"][1],
                "h2_reject": holm["reject_prespec_2"][1],
            },
            "h1_survives_holm_m3": {
                "h1_p": holm["h1_p"],
                "threshold_alpha_over_3": round(ALPHA / 3, 4),
                "survives": holm["h1_survives_m3"],
            },
            "conservative_all10": {
                "any_reject": any(holm["reject_conservative"]),
            },
        },
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str), encoding="utf-8"
    )

    print("CS-4 stats written to", OUT_DIR)
    print()

    for lag in DM_LAGS:
        for row in dm_rows:
            if row["lag"] == lag:
                p_str = f"{row['p_value']:.6f}" if row["p_value"] >= 0.001 else "< 0.001"
                print(
                    f"  {row['comparison']} lag={lag}: "
                    f"DM={row['dm_stat']:.4f}, p={p_str}, n={row['n_days']}"
                )

    print()
    h1_p_str = f"{holm['h1_p']:.4f}"
    print(f"  H1 p (approx): {h1_p_str}")
    print(f"  H1 survives Holm (m=2, thresh 0.025): {holm['reject_prespec_2'][0]}")
    print(f"  H1 survives Holm (m=3, thresh 0.0167): {holm['h1_survives_m3']}")


if __name__ == "__main__":
    run()
