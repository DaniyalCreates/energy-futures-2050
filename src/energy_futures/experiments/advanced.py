"""Batch 4 experiment (Steps 24-29).

    uv run python -m energy_futures.experiments.advanced validation   # EXP-002, EXP-003 (2023 only)
    uv run python -m energy_futures.experiments.advanced test         # EXP-004: unseals 2024-2025 ONCE

Stage outputs go to outputs/advanced/<stage>/ (git-ignored); summaries to docs/results/.
"""
import json
import sys
from datetime import datetime, timezone

import pandas as pd
import yaml

from energy_futures.clean.benchmarks import forecast_weather, neso_day_ahead
from energy_futures.config import ROOT
from energy_futures.evaluate import backtest
from energy_futures.evaluate.metrics import point_metrics
from energy_futures.experiments.baselines import build_features as baseline_features, git_commit
from energy_futures.features import build
from energy_futures.forecast.baselines import LinearBaseline, SeasonalNaive
from energy_futures.forecast.gbm import GBMPoint, GBMQuantile
from energy_futures.uncertainty.calibration import interval_stats, rolling_cqr

TZ = "Europe/London"
CFG = yaml.safe_load(open(ROOT / "configs/advanced.yaml"))
OUT = ROOT / "outputs" / "advanced"


def load():
    return pd.read_parquet(ROOT / "data/processed/demand_weather.parquet")


def threshold(y, start):
    t0 = pd.Timestamp(start, tz=TZ).tz_convert("UTC")
    return float(y[(y.index < t0) & (y.index >= t0 - pd.Timedelta(days=365))].quantile(0.95))


def local_mask(index, start, end=None):
    days = index.tz_convert(TZ).tz_localize(None).normalize()
    m = days >= pd.Timestamp(start)
    return m & (days <= pd.Timestamp(end)) if end else m


def save(stage, name, obj):
    p = OUT / stage
    p.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        (obj.to_frame() if isinstance(obj, pd.Series) else obj).to_parquet(p / f"{name}.parquet")
    else:
        (p / f"{name}.json").write_text(json.dumps(obj, indent=2, default=str))


# ---------------------------------------------------------------- validation (2023)
def validation():
    d = load()
    X, y = build.build(d, CFG["target"])
    v0, v1 = CFG["validation"]["start"], CFG["validation"]["end"]
    thr = threshold(y, v0)
    res, preds = {}, {}
    for setting, w in (("NW", False), ("PW", True)):
        for ts in CFG["train_start_candidates"]:
            name = f"gbm_{setting}_from{ts[:4]}"
            p, _ = backtest.run(lambda w=w, ts=ts: GBMPoint(w, ts), X, y, v0, v1, None, CFG["point_refit"])
            preds[name] = p
            res[name] = point_metrics(y.reindex(p.index), p, thr)
            print(f"{name:22s} MAE {res[name]['MAE']:6.0f}  bias {res[name]['bias']:6.0f}", flush=True)
    chosen = {s: min((k for k in res if k.startswith(f"gbm_{s}_")), key=lambda k: res[k]["MAE"]) for s in ("NW", "PW")}
    chosen_start = {s: chosen[s].split("from")[1] + "-01-01" for s in chosen}
    save("validation", "point_predictions", pd.DataFrame(preds).assign(actual=y.reindex(next(iter(preds.values())).index)))

    # EXP-003: quantiles (PW inputs, chosen PW window), backtest 2022-2023 so 2022 out-of-sample
    # scores exist to calibrate 2023.
    qb = CFG["quantile_backtest"]
    qp, _ = backtest.run_multi(lambda: GBMQuantile(True, chosen_start["PW"]), X, y, {"PW": X},
                               qb["start"], qb["end"], qb["refit"], method="predict_quantiles")
    Q = qp["PW"]
    save("validation", "quantiles_2022_2023", Q)
    raw = Q[local_mask(Q.index, v0, v1)]
    cal = rolling_cqr(y, Q, apply_from=v0, window_days=CFG["cqr_window_days"])
    qres = {"raw": interval_stats(y.reindex(raw.index), raw), "cqr": interval_stats(y.reindex(cal.index), cal)}
    save("validation", "quantiles_2023_cqr", cal)
    summary = {"run": run_id(), "point": res, "chosen": chosen, "chosen_train_start": chosen_start,
               "high_demand_threshold": thr, "quantile_2023": qres}
    save("validation", "summary", summary)
    print(json.dumps({"chosen": chosen, "quantile_2023": qres}, indent=1, default=str))


# ---------------------------------------------------------------- test (2024-2025), unsealed once
def test():
    vs = json.loads((OUT / "validation" / "summary.json").read_text())
    start_pw, start_nw = vs["chosen_train_start"]["PW"], vs["chosen_train_start"]["NW"]
    d = load()
    t0, t1, fw0 = CFG["test"]["start"], CFG["test"]["end"], CFG["fw_comparison_start"]
    fw_weather = forecast_weather(ROOT / "data/raw/weather_forecast", CFG["locations"], d.index)
    neso = neso_day_ahead(ROOT / "data/raw/neso_benchmark/day_ahead_forecast_performance.csv")
    summary = {"run": run_id(), "train_start": {"PW": start_pw, "NW": start_nw}, "targets": {}}

    for target in (CFG["target"], CFG["benchmark_target"]):
        X_pw, y = build.build(d, target)
        X_fw, _ = build.build(d, target, weather=fw_weather)
        P = {}
        # Baselines (same code as EXP-001).
        Xb, _ = baseline_features(d, target)
        for name, f in {"naive_d7": lambda: SeasonalNaive(7), "linear_calendar": lambda: LinearBaseline(False),
                        "linear_weather_PW": lambda: LinearBaseline(True)}.items():
            P[name], _ = backtest.run(f, Xb, y, t0, t1, "2009-01-01", CFG["point_refit"])
        pn, _ = backtest.run_multi(lambda: GBMPoint(False, start_nw), X_pw, y, {"NW": X_pw}, t0, t1, CFG["point_refit"])
        P["gbm_NW"] = pn["NW"]
        pw, _ = backtest.run_multi(lambda: GBMPoint(True, start_pw), X_pw, y, {"PW": X_pw, "FW": X_fw}, t0, t1, CFG["point_refit"])
        P["gbm_PW"], P["gbm_FW"] = pw["PW"], pw["FW"]
        if target == CFG["benchmark_target"]:
            P["NESO"] = neso["neso_forecast"].reindex(P["naive_d7"].index).astype(float)
        P = pd.DataFrame(P).assign(actual=y.reindex(P["naive_d7"].index))
        save("test", f"point_{target}", P)

        thr = threshold(y, t0)
        res = {}
        for period, mask in {"test_full": local_mask(P.index, t0, t1), "fw_window": local_mask(P.index, fw0, t1)}.items():
            sub = P[mask]
            res[period] = {m: point_metrics(sub.actual, sub[m], thr) for m in P.columns if m != "actual"
                           if not (period == "test_full" and m in ("gbm_FW", "NESO"))}
        summary["targets"][target] = res
        print(target, {m: round(v["MAE"]) for m, v in res["fw_window"].items()}, flush=True)

        if target == CFG["target"]:
            # Quantiles with forecast weather; CQR scores come from 2023 (PW inputs) then the test's own past.
            qp, _ = backtest.run_multi(lambda: GBMQuantile(True, start_pw), X_pw, y, {"FW": X_fw, "PW": X_pw},
                                       t0, t1, CFG["quantile_refit"], method="predict_quantiles")
            q23 = pd.read_parquet(OUT / "validation" / "quantiles_2022_2023.parquet")
            q_res = {}
            for k in ("FW", "PW"):
                Q = pd.concat([q23, qp[k]]).sort_index()
                cal = rolling_cqr(y, Q, apply_from=fw0, window_days=CFG["cqr_window_days"])
                raw = qp[k][local_mask(qp[k].index, fw0, t1)]
                save("test", f"quantiles_{k}_cqr", cal)
                save("test", f"quantiles_{k}_raw", raw)
                q_res[k] = {"raw": interval_stats(y.reindex(raw.index), raw),
                            "cqr": interval_stats(y.reindex(cal.index), cal)}
            summary["quantile_test"] = q_res
            print(json.dumps(q_res, indent=1), flush=True)
    save("test", "summary", summary)


def run_id():
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M") + "-" + git_commit()


if __name__ == "__main__":
    {"validation": validation, "test": test}[sys.argv[1]]()
