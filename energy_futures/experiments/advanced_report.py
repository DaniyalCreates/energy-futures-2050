"""Figures for the Batch 4 forecasting report (Step 30), from saved test outputs.

    uv run python -m energy_futures.experiments.advanced_report
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from energy_futures.config import ROOT

TZ = "Europe/London"
OUT = ROOT / "outputs" / "advanced" / "test"
FIG = ROOT / "docs" / "figures"
FW0 = pd.Timestamp("2024-03-08")


def window(df):
    return df[df.index.tz_convert(TZ).tz_localize(None) >= FW0]


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    s = json.loads((OUT / "summary.json").read_text())

    # 1. Test MAE by model, both targets.
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for ax, t in zip(axes, ["underlying_demand", "nd"]):
        r = s["targets"][t]["fw_window"]
        names = list(r)
        vals = [r[m]["MAE"] / 1e3 for m in names]
        colors = ["#bbbbbb" if m.startswith(("naive", "linear")) else ("#d62728" if m == "NESO" else "#1f77b4") for m in names]
        ax.barh(names, vals, color=colors)
        for i, v in enumerate(vals):
            ax.text(v, i, f" {v:.2f}", va="center", fontsize=8)
        ax.set_xlabel("MAE (GW)"); ax.set_title(f"Test 8 Mar 2024 - 31 Dec 2025: {t}")
        ax.invert_yaxis()
    fig.text(0.01, 0.01, "PW = perfect (observed) weather, an upper bound; FW = archived ~48 h weather forecasts (realistic).", fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(FIG / "b4_test_mae_by_model.png", dpi=120); plt.close(fig)

    # 2. ND: ours (FW) vs NESO by local hour.
    P = window(pd.read_parquet(OUT / "point_nd.parquet"))
    hr = P.index.tz_convert(TZ).hour
    m = pd.DataFrame({k: (P[k] - P.actual).abs().groupby(hr).mean() / 1e3 for k in ("gbm_FW", "NESO")})
    ax = m.plot(figsize=(9, 4), color=["#1f77b4", "#d62728"], title="National Demand day-ahead MAE by hour: our LightGBM (FW) vs NESO")
    ax.set_xlabel("hour (UK local)"); ax.set_ylabel("GW"); plt.tight_layout(); plt.savefig(FIG / "b4_nd_vs_neso_by_hour.png", dpi=120); plt.close()

    # 3. Calibration: nominal vs empirical coverage, raw vs CQR (FW).
    q = s["quantile_test"]["FW"]
    nom = [50, 80, 90]
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([40, 100], [40, 100], "k--", lw=1, label="perfect calibration")
    ax.plot(nom, [q["raw"][f"cover_{n}"] for n in nom], "o-", label="raw quantile LightGBM")
    ax.plot(nom, [q["cqr"][f"cover_{n}"] for n in nom], "s-", label="after rolling CQR")
    ax.set_xlabel("nominal interval coverage (%)"); ax.set_ylabel("observed coverage (%)")
    ax.set_title("Interval calibration, test (forecast weather)"); ax.legend(); ax.set_xlim(40, 100); ax.set_ylim(30, 100)
    fig.tight_layout(); fig.savefig(FIG / "b4_calibration.png", dpi=120); plt.close(fig)

    # 4. A winter week with calibrated intervals.
    U = pd.read_parquet(OUT / "point_underlying_demand.parquet")
    Q = pd.read_parquet(OUT / "quantiles_FW_cqr.parquet")
    a, b = "2025-01-06", "2025-01-13"
    u, qq = U.loc[a:b], Q.loc[a:b]
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.fill_between(qq.index, qq.q05 / 1e3, qq.q95 / 1e3, alpha=0.2, color="#1f77b4", label="90% interval")
    ax.fill_between(qq.index, qq.q10 / 1e3, qq.q90 / 1e3, alpha=0.3, color="#1f77b4", label="80% interval")
    ax.plot(u.index, u.gbm_FW / 1e3, color="#1f77b4", lw=1, label="LightGBM (FW) point forecast")
    ax.plot(u.index, u.actual / 1e3, color="black", lw=1.6, label="actual")
    ax.set_ylabel("GW"); ax.set_title("Underlying demand, 6-13 Jan 2025: day-ahead forecast with calibrated intervals")
    ax.legend(ncol=4, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.12)); fig.tight_layout()
    fig.savefig(FIG / "b4_week_jan2025_intervals.png", dpi=120); plt.close(fig)
    print("figures saved")


if __name__ == "__main__":
    main()
