"""Batch 5 experiment (Steps 32-36): FES pathways x years x weather years, stress tests, checks.

    uv run python -m energy_futures.experiments.scenarios
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml

from energy_futures.config import ROOT
from energy_futures.experiments.baselines import git_commit
from energy_futures.scenarios import engine, fes, stress

OUT = ROOT / "outputs" / "scenarios"
FIG = ROOT / "docs" / "figures"


def main():
    cfg = yaml.safe_load(open(ROOT / "configs/scenarios.yaml"))
    d = pd.read_parquet(ROOT / "data/processed/demand_weather.parquet")
    D, S = fes.demand_table(ROOT / cfg["fes"]["ed1"]), fes.supply_table(ROOT / cfg["fes"]["es1"])
    OUT.mkdir(parents=True, exist_ok=True)
    rows, examples = [], {}

    # 1. Main grid.
    for p in cfg["pathways"]:
        for y in cfg["years"]:
            for w in cfg["weather_years"]:
                x, m = engine.build(d, D, S, p, y, w, cfg)
                rows.append({**m, **engine.metrics(x), "case": "central"})
                if w == 2024:
                    examples[(p, y)] = x
        print(f"  grid: {p} done", flush=True)
    # EV sensitivity (30% unmanaged) and hot-water sensitivity, Holistic Transition only.
    for label, patch in (("ev_smart_0.7", ("ev", "smart_share", 0.7)), ("hp_hot_water_0.2", ("heat_pumps", "hot_water_share", 0.2))):
        c2 = yaml.safe_load(yaml.safe_dump(cfg)); c2[patch[0]][patch[1]] = patch[2]
        for y in cfg["years"]:
            for w in cfg["weather_years"]:
                x, m = engine.build(d, D, S, "Holistic Transition", y, w, c2)
                rows.append({**m, **engine.metrics(x), "case": label})
    grid = pd.DataFrame(rows)
    grid.to_parquet(OUT / "grid.parquet")

    # 2. Stress tests.
    daily = stress.daily_weather(d)
    wy = cfg["weather_years"]
    cs0, cs1 = stress.cold_still_window(daily, cfg["stress"]["cold_still_days"], wy)
    s35 = S.loc[("Holistic Transition", 2035)]
    lr0, lr1 = stress.low_renewable_window(daily, cfg["stress"]["low_renewable_days"], wy,
                                           s35.offshore_wind_gen_twh + s35.onshore_wind_gen_twh, s35.solar_gen_twh)
    fe = cfg["stress"]["fast_electrification"]
    srows = []
    for p in cfg["pathways"]:
        for y in cfg["years"]:
            for name, (a, b) in {"cold_still_week": (cs0, cs1), "low_renewable_fortnight": (lr0, lr1)}.items():
                x, _ = engine.build(d, D, S, p, y, a.year, cfg)
                srows.append({"pathway": p, "year": y, "stress": name, **stress.window_metrics(x, a, b)})
        # Fast electrification: 2035 with 2040 EV/HP/flat demand, in the cold-still weather year.
        x, _ = engine.build(d, D, S, p, fe["year"], cs0.year, cfg, electrification_year=fe["electrification_from"])
        srows.append({"pathway": p, "year": fe["year"], "stress": "fast_electrification_cold_still",
                      **stress.window_metrics(x, cs0, cs1)})
    st = pd.DataFrame(srows)
    st.to_parquet(OUT / "stress.parquet")

    # 3. Consistency checks against FES (Step 36).
    c = grid[grid.case == "central"].copy()
    base_peaks = {w: engine.metrics(engine.build(d, D, S, "Holistic Transition", 2024, w, cfg)[0])["peak_demand_gw"] for w in wy}
    c["our_peak_increase_gw"] = c.peak_demand_gw - c.weather_year.map(base_peaks)
    c["fes_peak_increase_gw"] = c.fes_peak_gw - c.fes_peak_2024_gw
    check = c.groupby(["pathway", "year"]).agg(
        our_peak_increase_median=("our_peak_increase_gw", "median"), our_peak_increase_min=("our_peak_increase_gw", "min"),
        our_peak_increase_max=("our_peak_increase_gw", "max"), fes_peak_increase=("fes_peak_increase_gw", "first"),
        hp_at_peak_median=("hp_at_peak_gw", "median"), fes_hp_peak_increment=("fes_hp_peak_increment_gw", "first"),
        ev_at_peak_median=("ev_at_peak_gw", "median"), fes_ev_peak_increment=("fes_ev_peak_increment_gw", "first"),
        demand_twh=("demand_twh", "median"), peak_demand_median=("peak_demand_gw", "median"),
        peak_demand_max=("peak_demand_gw", "max"), peak_net_median=("peak_net_gw", "median"),
        peak_net_max=("peak_net_gw", "max"), min_net_median=("min_net_gw", "median"),
        surplus_twh_median=("surplus_twh", "median"), surplus_hours_median=("surplus_hours", "median"),
        max_3h_ramp_median=("max_3h_net_ramp_gw", "median"), battery_gw=("battery_mw", lambda s: s.iloc[0] / 1e3),
        battery_gwh=("battery_gwh", "first"), ldes_gw=("ldes_mw", lambda s: s.iloc[0] / 1e3), ldes_gwh=("ldes_gwh", "first"),
    ).round(1)
    check.to_csv(OUT / "summary_by_pathway_year.csv")
    sens = grid[grid.pathway == "Holistic Transition"].groupby(["case", "year"]).agg(
        peak_demand_median=("peak_demand_gw", "median"), ev_at_peak_median=("ev_at_peak_gw", "median"),
        peak_net_median=("peak_net_gw", "median")).round(1)
    sens.to_csv(OUT / "sensitivity_holistic.csv")
    meta = {"commit": git_commit(), "cold_still_window": [str(cs0.date()), str(cs1.date())],
            "low_renewable_window": [str(lr0.date()), str(lr1.date())], "n_runs": len(grid)}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2))
    figures(check, examples, cs0, cs1)
    print(json.dumps(meta, indent=1))
    print(check[["our_peak_increase_median", "fes_peak_increase", "hp_at_peak_median", "fes_hp_peak_increment",
                 "ev_at_peak_median", "fes_ev_peak_increment", "peak_net_median", "peak_net_max", "surplus_twh_median"]].to_string())
    print(st.round(1).to_string())
    print(sens.to_string())


def figures(check, examples, cs0, cs1):
    FIG.mkdir(parents=True, exist_ok=True)
    # 1. Peak demand increase: ours (median, weather-year range) vs FES.
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.8), sharey=True)
    for ax, p in zip(axes, check.index.get_level_values(0).unique()):
        c = check.loc[p]
        ax.errorbar(c.index, c.our_peak_increase_median, yerr=[c.our_peak_increase_median - c.our_peak_increase_min,
                    c.our_peak_increase_max - c.our_peak_increase_median], fmt="o-", capsize=3, label="this model (13 weather years)")
        ax.plot(c.index, c.fes_peak_increase, "s--", color="#d62728", label="FES 2025")
        ax.set_title(p, fontsize=10); ax.set_xticks(list(c.index))
    axes[0].set_ylabel("increase in peak demand vs 2024 (GW)"); axes[0].legend(fontsize=7)
    fig.suptitle("Consistency check: modelled peak growth vs FES 2025", fontsize=11); fig.tight_layout()
    fig.savefig(FIG / "b5_peak_check_vs_fes.png", dpi=120); plt.close(fig)
    # 2. Composition of demand in the cold-still week, Holistic Transition 2035 & 2050 (weather year of the window).
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=False)
    for ax, y in zip(axes, (2035, 2050)):
        x = examples.get(("Holistic Transition", y))
        if x is None:
            continue
        w = x.loc["2024-01-08":"2024-01-14"]
        ax.stackplot(w.index, w.base / 1e3, w.hp / 1e3, w.ev / 1e3, w.flat / 1e3, labels=["existing demand", "new heat pumps", "new EVs", "electrolysis + data centres"], alpha=0.8)
        ax.plot(w.index, (w.wind + w.solar + w.nuclear) / 1e3, color="black", lw=1.2, label="wind + solar + nuclear")
        ax.set_ylabel("GW"); ax.set_title(f"Holistic Transition {y}, weather year 2024, week of 8-14 Jan", fontsize=10)
    axes[0].legend(fontsize=7, ncol=5, loc="upper left"); fig.tight_layout()
    fig.savefig(FIG / "b5_week_composition.png", dpi=120); plt.close(fig)


if __name__ == "__main__":
    main()
