"""Batch 6 experiment (Steps 38-42): compare flexibility decision methods under uncertainty.

    uv run python -m energy_futures.experiments.optimisation historical
    uv run python -m energy_futures.experiments.optimisation future
    uv run python -m energy_futures.experiments.optimisation report
"""
import json
import sys
from multiprocessing import Pool

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from energy_futures.config import ROOT
from energy_futures.experiments.baselines import git_commit
from energy_futures.optimise.battery import Battery, realised, schedule, threshold_rule

TZ = "Europe/London"
CFG = yaml.safe_load(open(ROOT / "configs/optimisation.yaml"))
OUT = ROOT / "outputs" / "optimisation"
ADV = ROOT / "outputs" / "advanced"
LEVELS = CFG["scenarios_from_quantiles"]["levels"]
PROBS = np.array(CFG["scenarios_from_quantiles"]["probabilities"])
ARMS = ["none", "A", "B", "B_plus", "C_minus", "C", "oracle"]


def local_day(idx):
    return idx.tz_convert(TZ).tz_localize(None).normalize()


def run_day(job):
    """job: dict with actual (T,), naive, point, Q (7,T), Qu (7,T), battery, threshold, mu, alpha, w."""
    a = job["actual"]; bat = job["battery"]; thr, mu, alpha, w = job["threshold"], job["mu"], job["alpha"], job["w"]
    tp = CFG["battery"]["throughput_cost"]
    decisions = {
        "none": (np.zeros_like(a), np.zeros_like(a)),
        "A": threshold_rule(job["naive"], bat),
        "B": schedule(job["point"], [1.0], bat, thr, mu, throughput=tp),
        "B_plus": schedule(job["Q"][3], [1.0], bat, thr, mu, throughput=tp),
        "C_minus": schedule(job["Qu"], PROBS, bat, thr, mu, alpha, w, tp),
        "C": schedule(job["Q"], PROBS, bat, thr, mu, alpha, w, tp),
        "oracle": schedule(a, [1.0], bat, thr, mu, throughput=tp),
    }
    out = []
    for arm, (c, d) in decisions.items():
        out.append({"day": job["day"], "variant": job["variant"], "arm": arm, **realised(a, c, d, thr, mu, tp)})
    return out


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("arm")
    s = pd.DataFrame({
        "mean_cost": g.cost.mean(), "p95_cost": g.cost.quantile(0.95), "worst_day_cost": g.cost.max(),
        "total_shortfall_gwh": g.shortfall_mwh.sum() / 1e3, "max_load_after_battery_mw": g.peak_mw.max(),
        "mean_daily_peak_mw": g.peak_mw.mean(), "throughput_gwh": g.throughput_mwh.sum() / 1e3,
    }).reindex(ARMS)
    none, orc = s.loc["none", "mean_cost"], s.loc["oracle", "mean_cost"]
    s["oracle_value_captured_pct"] = (none - s.mean_cost) / (none - orc) * 100
    return s


# ------------------------------------------------------------------ Setting H (historical, real forecasts)
def historical_jobs():
    h = CFG["historical"]
    P = pd.read_parquet(ADV / "test/point_underlying_demand.parquet")
    Q = pd.read_parquet(ADV / "test/quantiles_FW_cqr.parquet")
    V = pd.read_parquet(ADV / "validation/point_predictions.parquet")
    rel = (V.actual - V.gbm_PW_from2009) / V.gbm_PW_from2009           # 2023 out-of-sample relative errors
    equant = rel.quantile([int(l[1:]) / 100 for l in LEVELS]).to_numpy()
    days = local_day(P.index)
    keep = (days >= pd.Timestamp(h["start"])) & (days <= pd.Timestamp(h["end"]))
    P, days = P[keep], days[keep]
    Q = Q.reindex(P.index)
    base = dict(battery=Battery(h["battery_mw"], h["battery_mwh"], CFG["battery"]["roundtrip_efficiency"], CFG["battery"]["soc_start_end"]),
                threshold=h["threshold_mw"], mu=CFG["cost_index"]["mu"], alpha=CFG["cost_index"]["risk"]["alpha"],
                w=CFG["cost_index"]["risk"]["weight"])
    s = CFG["sensitivity"]
    thr95 = float(pd.read_parquet(ROOT / "data/processed/demand_weather.parquet").underlying_demand.loc["2023"].quantile(0.95))
    variants = {"central": {}}
    for k in s["battery_scale"]:
        variants[f"battery_x{k}"] = {"battery": Battery(h["battery_mw"] * k, h["battery_mwh"] * k, base["battery"].roundtrip, base["battery"].soc0)}
    for m in s["mu"]:
        variants[f"mu_{m}"] = {"mu": m}
    for a in s["alpha"]:
        variants[f"alpha_{a}"] = {"alpha": a}
    variants["threshold_p95"] = {"threshold": thr95}
    jobs = []
    for day, idx in P.groupby(days).groups.items():
        p, q = P.loc[idx], Q.loc[idx]
        if q.isna().any().any() or p.isna().any().any():
            continue
        day_data = dict(day=str(day.date()), actual=p.actual.to_numpy(), naive=p.naive_d7.to_numpy(), point=p.gbm_FW.to_numpy(),
                        Q=q[LEVELS].to_numpy().T, Qu=np.outer(1 + equant, p.gbm_FW.to_numpy()))
        for vname, patch in variants.items():
            jobs.append({**base, **day_data, **patch, "variant": vname})
    return jobs


# ------------------------------------------------------------------ Setting F (FES futures, synthetic forecasts)
def future_jobs():
    from energy_futures.scenarios import engine, fes
    f = CFG["future"]
    scfg = yaml.safe_load(open(ROOT / "configs/scenarios.yaml"))
    d = pd.read_parquet(ROOT / "data/processed/demand_weather.parquet")
    D, S = fes.demand_table(ROOT / scfg["fes"]["ed1"]), fes.supply_table(ROOT / scfg["fes"]["es1"])
    P = pd.read_parquet(ADV / "test/point_underlying_demand.parquet")
    Q = pd.read_parquet(ADV / "test/quantiles_FW_cqr.parquet")
    src = P.join(Q, how="inner").dropna()
    sdays = local_day(src.index)
    src_groups = {k: v for k, v in src.groupby(sdays).groups.items()}
    by_month_T = {}
    for k, idx in src_groups.items():
        by_month_T.setdefault((k.month, len(idx)), []).append(k)
    rng = np.random.default_rng(f["seed"])
    V = pd.read_parquet(ADV / "validation/point_predictions.parquet")
    rel = (V.actual - V.gbm_PW_from2009) / V.gbm_PW_from2009
    equant = rel.quantile([int(l[1:]) / 100 for l in LEVELS]).to_numpy()
    jobs, meta = [], {}
    for case in f["cases"]:
        name = f"{case['pathway'].split()[0]}_{case['year']}" + ("_fastelec" if case.get("electrification_year") else "")
        x, m = engine.build(d, D, S, case["pathway"], case["year"], f["weather_year"], scfg, case.get("electrification_year"))
        vre = x.wind + x.solar + x.nuclear
        thr = float(x.net.quantile(0.99))
        bat = Battery(m["battery_mw"], m["battery_gwh"] * 1e3, CFG["battery"]["roundtrip_efficiency"], CFG["battery"]["soc_start_end"])
        meta[name] = {"threshold_mw": thr, "battery_mw": bat.power_mw, "battery_mwh": bat.energy_mwh}
        days = local_day(x.index)
        groups = x.groupby(days).groups
        prev_net = {}
        for day, idx in groups.items():
            xd = x.loc[idx]
            T = len(idx)
            cands = by_month_T.get((day.month, T))
            if not cands:
                continue
            sd = cands[rng.integers(len(cands))]
            s = src.loc[src_groups[sd]]
            ratio_point = (s.gbm_FW / s.actual).to_numpy()
            ratio_q = (s[LEVELS].to_numpy() / s.actual.to_numpy()[:, None]).T
            dem = xd.demand.to_numpy(); v = vre.loc[idx].to_numpy(); actual = xd.net.to_numpy()
            wk = day - pd.Timedelta(days=7)
            naive = prev_net.get(wk)
            if naive is None or len(naive) != T:
                naive = actual if naive is None else np.interp(np.linspace(0, 1, T), np.linspace(0, 1, len(naive)), naive)
            point = dem * ratio_point - v
            jobs.append(dict(day=str(day.date()), variant=name, actual=actual, naive=naive, point=point,
                             Q=dem * ratio_q - v, Qu=np.outer(1 + equant, dem * ratio_point) - v,
                             battery=bat, threshold=thr, mu=CFG["cost_index"]["mu"],
                             alpha=CFG["cost_index"]["risk"]["alpha"], w=CFG["cost_index"]["risk"]["weight"]))
            prev_net[day] = actual
    return jobs, meta


def run(jobs, name):
    OUT.mkdir(parents=True, exist_ok=True)
    with Pool(2) as pool:
        rows = [r for day in pool.imap_unordered(run_day, jobs, chunksize=20) for r in day]
    df = pd.DataFrame(rows)
    df.to_parquet(OUT / f"{name}_daily.parquet")
    return df


def historical():
    jobs = historical_jobs()
    print(f"historical: {len(jobs)} day-variant jobs", flush=True)
    df = run(jobs, "historical")
    for v, g in df.groupby("variant"):
        s = summarise(g)
        s.to_csv(OUT / f"historical_{v}.csv")
        if v == "central":
            print(s.round(1).to_string())


def future():
    jobs, meta = future_jobs()
    (OUT / "future_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"future: {len(jobs)} day jobs", meta, flush=True)
    df = run(jobs, "future")
    for v, g in df.groupby("variant"):
        s = summarise(g)
        s.to_csv(OUT / f"future_{v}.csv")
        cold = g[(g.day >= "2022-12-09") & (g.day <= "2022-12-15")]
        summarise(cold).to_csv(OUT / f"future_{v}_coldweek.csv")
        print(v); print(s.round(1).to_string())


if __name__ == "__main__":
    {"historical": historical, "future": future}[sys.argv[1]]()
