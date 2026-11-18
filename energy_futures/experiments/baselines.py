"""Batch 3 experiment: baseline forecasts on the validation year.

    uv run python -m energy_futures.experiments.baselines
"""
import json
import subprocess
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml

from energy_futures.config import ROOT
from energy_futures.evaluate import backtest
from energy_futures.evaluate.metrics import point_metrics
from energy_futures.features.calendar import calendar_features
from energy_futures.forecast import task
from energy_futures.forecast.baselines import make_models

TZ = "Europe/London"


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except Exception:
        return "unknown"


def build_features(d: pd.DataFrame, target: str) -> tuple[pd.DataFrame, pd.Series]:
    y = d[target]
    X = calendar_features(d.index).join(task.lag_features(y, d.index))
    X = X.join(d[[c for c in d.columns if c.endswith("_gb_mean")]])
    return X, y


def main():
    cfg = yaml.safe_load(open(ROOT / "configs/baselines.yaml"))
    d = pd.read_parquet(ROOT / "data/processed/demand_weather.parquet")
    version = json.load(open(ROOT / "data/processed/dataset_version.json"))
    X, y = build_features(d, cfg["target"])
    v0, v1 = cfg["validation"]["start"], cfg["validation"]["end"]
    # High-demand threshold from the 365 days before validation only (no peeking; recent level, since
    # demand has fallen ~17% since 2009 and an all-history threshold is never reached in 2023).
    t0 = pd.Timestamp(v0, tz=TZ).tz_convert("UTC")
    pre = y[(y.index < t0) & (y.index >= t0 - pd.Timedelta(days=cfg["high_demand_window_days"]))]
    thr = float(pre.quantile(cfg["high_demand_quantile"]))

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M") + "-" + git_commit()
    out = ROOT / "outputs" / "baselines" / run_id
    out.mkdir(parents=True, exist_ok=True)
    preds, results, logs = {}, {}, {}
    for name, model in make_models().items():
        p, log = backtest.run(lambda m=model: m, X, y, v0, v1, cfg["train_start"], cfg["refit"])
        preds[name], logs[name] = p, log
        results[name] = point_metrics(y.reindex(p.index), p, thr)
        print(f"{name:20s} MAE {results[name]['MAE']:7.0f} MW  MAPE {results[name]['MAPE_pct']:5.2f}%")

    P = pd.DataFrame(preds).assign(actual=y.reindex(next(iter(preds.values())).index))
    P.to_parquet(out / "predictions.parquet")
    meta = {"run_id": run_id, "config": cfg, "dataset_version": version, "high_demand_threshold_MW": thr,
            "metrics": results, "refits": logs}
    (out / "metrics.json").write_text(json.dumps(meta, indent=2, default=str))
    write_report(results, thr, run_id, version, cfg)
    figures(P, ROOT / "docs" / "figures")
    print(f"Saved outputs/baselines/{run_id}/ and docs/results/baselines_validation.md")


def write_report(results, thr, run_id, version, cfg):
    df = pd.DataFrame(results).T
    cols = ["MAE", "RMSE", "MAPE_pct", "bias", "daily_peak_MAE", "daily_peak_timing_within_1h_pct", "high_demand_MAE"]
    tbl = df[cols].astype(float).round(1).to_string()
    p = ROOT / "docs" / "results"
    p.mkdir(parents=True, exist_ok=True)
    (p / "baselines_validation.md").write_text(
        f"# Baseline results: validation year {cfg['validation']['start'][:4]}\n\n"
        f"Run `{run_id}` · dataset built {version['built_utc']} (config {version['config_sha256']}) · "
        f"target `{cfg['target']}` (MW) · day-ahead, issued 09:00 UK time on D-1 · monthly expanding-window refits.\n\n"
        f"High-demand threshold (95th percentile of the 365 days before validation): {thr:,.0f} MW.\n\n"
        f"`linear_weather_PW` uses observed weather at the target time (**perfect-weather**, D-009); "
        f"it is an upper bound for weather value, not a realistic forecast.\n\n```\n{tbl}\n```\n")


def figures(P: pd.DataFrame, figdir):
    figdir.mkdir(parents=True, exist_ok=True)
    models = [c for c in P.columns if c != "actual"]
    # 1. One winter week.
    wk = P.loc["2023-01-16":"2023-01-23"]
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(wk.index, wk.actual / 1e3, color="black", lw=2, label="actual")
    for m in models:
        ax.plot(wk.index, wk[m] / 1e3, lw=1, label=m)
    ax.set_ylabel("GW"); ax.set_title("Underlying demand, 16-23 Jan 2023: actual vs baselines (day-ahead)")
    ax.legend(ncol=5, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.12)); fig.tight_layout()
    fig.savefig(figdir / "baselines_week_jan2023.png", dpi=120); plt.close(fig)
    # 2. MAE by local time of day.
    hod = P.index.tz_convert(TZ).hour
    mae = pd.DataFrame({m: (P[m] - P.actual).abs().groupby(hod).mean() / 1e3 for m in models})
    ax = mae.plot(figsize=(9, 4), title="Mean absolute error by local hour, 2023 (GW)")
    ax.set_xlabel("hour (UK local)"); ax.set_ylabel("GW"); plt.tight_layout()
    plt.savefig(figdir / "baselines_mae_by_hour.png", dpi=120); plt.close()
    # 3. MAE by month.
    mon = P.index.tz_convert(TZ).month
    mm = pd.DataFrame({m: (P[m] - P.actual).abs().groupby(mon).mean() / 1e3 for m in models})
    ax = mm.plot.bar(figsize=(10, 4), title="Mean absolute error by month, 2023 (GW)")
    ax.set_xlabel("month"); ax.set_ylabel("GW"); plt.tight_layout()
    plt.savefig(figdir / "baselines_mae_by_month.png", dpi=120); plt.close()


if __name__ == "__main__":
    main()
