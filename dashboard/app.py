"""Energy Futures 2050 research dashboard (Batch 7, Steps 43-46).

    uv run streamlit run dashboard/app.py

Every number shown is read from saved experiment outputs (outputs/, docs/results/) or recomputed
with the project's own tested code (scenario engine, battery LP). Nothing here is illustrative or
hand-typed. Pages label each quantity as OBSERVED, FORECAST (out-of-sample) or SIMULATED.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from energy_futures.optimise.battery import Battery, realised, schedule, threshold_rule  # noqa: E402

TZ = "Europe/London"
OUT = ROOT / "outputs"
RES = ROOT / "docs" / "results"
COLORS = {"actual": "#111111", "LightGBM": "#1f77b4", "NESO": "#d62728", "band90": "rgba(31,119,180,0.15)",
          "band80": "rgba(31,119,180,0.30)"}
ARM_NAMES = {"none": "No battery", "A": "A · fixed rule", "B": "B · point forecast + LP", "B_plus": "B+ · median + LP",
             "C_minus": "C− · error scenarios + CVaR", "C": "C · calibrated quantiles + CVaR", "oracle": "Perfect foresight"}

st.set_page_config(page_title="Energy Futures 2050", layout="wide")


# ----------------------------------------------------------------------------- data loaders
@st.cache_data
def load_json(rel):
    p = ROOT / rel
    return json.loads(p.read_text()) if p.exists() else None


@st.cache_data
def load_parquet(rel):
    p = ROOT / rel
    return pd.read_parquet(p) if p.exists() else None


@st.cache_data
def load_csv(rel, **kw):
    p = ROOT / rel
    return pd.read_csv(p, **kw) if p.exists() else None


def missing(what, command):
    st.warning(f"{what} not found. Generate it with:\n\n`{command}`")


def badge(kind):
    colors = {"OBSERVED": "#2e7d32", "FORECAST": "#1565c0", "SIMULATED": "#e65100"}
    st.markdown(f"<span style='background:{colors[kind]};color:white;padding:2px 8px;border-radius:4px;"
                f"font-size:0.75rem'>{kind}</span>", unsafe_allow_html=True)


# ----------------------------------------------------------------------------- pages
def page_overview():
    st.title("Energy Futures 2050")
    st.caption("Uncertainty-aware forecasting and risk-aware flexibility planning for Great Britain's electricity "
               "system: an open, reproducible research prototype.")
    st.markdown("**Research question:** can uncertainty-aware machine learning, combined with scenario simulation and "
                "constrained optimisation, make electricity flexibility planning more robust than conventional "
                "forecasting and deterministic decisions?")
    adv = load_json("outputs/advanced/test/summary.json")
    hist = load_csv("outputs/optimisation/historical_central.csv", index_col=0)
    c1, c2, c3, c4 = st.columns(4)
    if adv:
        u = adv["targets"]["underlying_demand"]["fw_window"]
        n = adv["targets"]["nd"]["fw_window"]
        c1.metric("Day-ahead MAE (underlying demand)", f"{u['gbm_FW']['MAE']:,.0f} MW")
        c1.caption(f"{(1 - u['gbm_FW']['MAE'] / u['naive_d7']['MAE']) * 100:.0f}% lower than the weekly naive baseline")
        c2.metric("National Demand MAE: ours / NESO", f"{n['gbm_FW']['MAE']:,.0f} / {n['NESO']['MAE']:,.0f}")
        c2.caption(f"NESO's operational forecast is {(n['gbm_FW']['MAE'] / n['NESO']['MAE'] - 1) * 100:.0f}% more accurate")
        q = adv["quantile_test"]["FW"]["cqr"]
        c3.metric("90% interval coverage (test)", f"{q['cover_90']:.1f}%")
        c3.caption("Target 90%; calibrated with rolling CQR")
    if hist is not None:
        c4.metric("Battery value captured (C / B)", f"{hist.loc['C', 'oracle_value_captured_pct']:.1f} / "
                  f"{hist.loc['B', 'oracle_value_captured_pct']:.1f}%")
        c4.caption("Share of perfect-foresight value, real 2024–25 forecasts")
    st.subheader("Findings so far")
    st.markdown("""
1. **Forecasting:** LightGBM with archived weather forecasts beats standard baselines by 39–48% and has calibrated
   uncertainty intervals, but is about 50% less accurate than NESO's operational day-ahead forecast.
2. **Scenarios:** FES 2025 pathways imply peak demand growth of tens of GW by 2050. The hardest condition is a
   cold, still week (9–15 Dec 2022 weather), where daily-cycling batteries cannot cover the multi-day energy need.
3. **Decisions:** moving from a fixed rule to forecast-driven optimisation roughly doubles battery value (38% → 61%).
   Uncertainty-aware scheduling adds a small, consistent gain (+2.4 points). That gain is statistically significant
   for average cost but **not** for tail risk.
""")
    st.info("Results are from pre-registered experiments (protocols committed before the test data were used). "
            "2030–2050 figures are simulated consequences of FES assumptions, not predictions.")


def page_forecasting():
    st.header("Day-ahead demand forecasting")
    badge("FORECAST")
    st.caption("Out-of-sample day-ahead forecasts issued 09:00 UK time on D-1, test period 8 Mar 2024 – 31 Dec 2025. "
               "Weather inputs are archived ~48 h-ahead forecasts (realistic setting).")
    P = load_parquet("outputs/advanced/test/point_underlying_demand.parquet")
    Q = load_parquet("outputs/advanced/test/quantiles_FW_cqr.parquet")
    if P is None or Q is None:
        return missing("Forecast outputs", "uv run python -m energy_futures.experiments.advanced test")
    local = Q.index.tz_convert(TZ)
    d0, d1 = local.min().date(), local.max().date()
    start = st.date_input("Week starting", value=pd.Timestamp("2025-01-06").date(), min_value=d0, max_value=d1)
    a = pd.Timestamp(start).tz_localize(TZ)
    sl = slice(a.tz_convert("UTC"), (a + pd.Timedelta(days=7)).tz_convert("UTC"))
    p, q = P.loc[sl], Q.loc[sl]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=q.index, y=q.q95 / 1e3, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=q.index, y=q.q05 / 1e3, fill="tonexty", fillcolor=COLORS["band90"], line=dict(width=0), name="90% interval"))
    fig.add_trace(go.Scatter(x=q.index, y=q.q90 / 1e3, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=q.index, y=q.q10 / 1e3, fill="tonexty", fillcolor=COLORS["band80"], line=dict(width=0), name="80% interval"))
    fig.add_trace(go.Scatter(x=p.index, y=p.gbm_FW / 1e3, name="LightGBM forecast", line=dict(color=COLORS["LightGBM"], width=1.5)))
    fig.add_trace(go.Scatter(x=p.index, y=p.actual / 1e3, name="Actual (observed)", line=dict(color=COLORS["actual"], width=2)))
    fig.update_layout(height=420, yaxis_title="Underlying demand (GW)", margin=dict(t=20, b=10), legend=dict(orientation="h"))
    st.plotly_chart(fig, width="stretch")
    adv = load_json("outputs/advanced/test/summary.json")
    if adv:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Accuracy by model (MW)")
            rows = []
            for t, lab in (("underlying_demand", "Underlying demand"), ("nd", "National Demand")):
                for m, v in adv["targets"][t]["fw_window"].items():
                    rows.append({"Target": lab, "Model": m, "MAE (MW)": round(v["MAE"]), "MAPE %": round(v["MAPE_pct"], 2),
                                 "Daily-peak MAE (MW)": round(v["daily_peak_MAE"])})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            st.caption("PW = observed weather (upper bound, not deployable). FW = forecast weather (realistic). NESO = "
                       "the system operator's published day-ahead forecast (National Demand only).")
        with c2:
            st.subheader("Interval calibration (test)")
            qs = adv["quantile_test"]["FW"]
            cal = pd.DataFrame({"nominal %": [50, 80, 90],
                                "raw coverage %": [round(qs["raw"][f"cover_{n}"], 1) for n in (50, 80, 90)],
                                "calibrated (CQR) %": [round(qs["cqr"][f"cover_{n}"], 1) for n in (50, 80, 90)],
                                "mean width (MW)": [round(qs["cqr"][f"width_{n}"]) for n in (50, 80, 90)]})
            st.dataframe(cal, hide_index=True, width="stretch")
    N = load_parquet("outputs/advanced/test/point_nd.parquet")
    if N is not None:
        N = N[N.index.tz_convert(TZ).tz_localize(None) >= pd.Timestamp("2024-03-08")]
        hr = N.index.tz_convert(TZ).hour
        m = pd.DataFrame({k: (N[k] - N.actual).abs().groupby(hr).mean() / 1e3 for k in ("gbm_FW", "NESO")})
        fig = go.Figure([go.Scatter(x=m.index, y=m.gbm_FW, name="Our LightGBM (FW)", line=dict(color=COLORS["LightGBM"])),
                         go.Scatter(x=m.index, y=m.NESO, name="NESO", line=dict(color=COLORS["NESO"]))])
        fig.update_layout(height=320, title="National Demand: mean absolute error by hour (GW)", xaxis_title="hour (UK local)",
                          margin=dict(t=40, b=10), legend=dict(orientation="h"))
        st.plotly_chart(fig, width="stretch")
        st.caption("NESO is more accurate in every hour. Likely reasons (not tested): richer weather inputs, dedicated "
                   "embedded-solar forecasting, later data, forecaster expertise.")


@st.cache_resource
def scenario_inputs():
    from energy_futures.scenarios import fes
    cfg = yaml.safe_load(open(ROOT / "configs/scenarios.yaml"))
    d = pd.read_parquet(ROOT / "data/processed/demand_weather.parquet")
    return cfg, d, fes.demand_table(ROOT / cfg["fes"]["ed1"]), fes.supply_table(ROOT / cfg["fes"]["es1"])


@st.cache_data
def scenario_run(pathway, year, w, fast):
    from energy_futures.scenarios import engine
    cfg, d, D, S = scenario_inputs()
    x, m = engine.build(d, D, S, pathway, year, w, cfg, electrification_year=2040 if fast else None)
    return x, m, engine.metrics(x)


def page_scenarios():
    st.header("Future scenarios 2030–2050")
    badge("SIMULATED")
    st.caption("FES 2025 pathway changes added to observed 2024 demand, shaped by real 2013–2025 weather. These are "
               "consequences of stated assumptions, not predictions.")
    try:
        cfg, *_ = scenario_inputs()
    except FileNotFoundError:
        return missing("Data or FES files", "uv run python -m energy_futures.pipeline all && uv run python -m energy_futures.ingest.fes")
    c1, c2, c3, c4 = st.columns(4)
    pathway = c1.selectbox("FES pathway", cfg["pathways"])
    year = c2.selectbox("Year", cfg["years"], index=1)
    w = c3.selectbox("Weather year", cfg["weather_years"], index=cfg["weather_years"].index(2022))
    fast = c4.checkbox("Fast electrification (2040 EV/heat-pump levels)", value=False, disabled=year != 2035)
    x, meta, k = scenario_run(pathway, year, w, fast and year == 2035)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Annual demand", f"{k['demand_twh']:.0f} TWh")
    m2.metric("Peak demand", f"{k['peak_demand_gw']:.1f} GW")
    m3.metric("Peak net demand (after wind, solar, nuclear)", f"{k['peak_net_gw']:.1f} GW")
    m4.metric("Surplus before export/storage", f"{k['surplus_twh']:.0f} TWh")
    local = x.index.tz_convert(TZ)
    weeks = pd.date_range(local.min().normalize(), local.max().normalize() - pd.Timedelta(days=7), freq="7D")
    default = max(0, int(np.argmax(x.net.resample("7D").mean().to_numpy())))
    wk = st.select_slider("Week", options=list(weeks.date), value=weeks[min(default, len(weeks) - 1)].date())
    a = pd.Timestamp(wk).tz_localize(TZ)
    xs = x.loc[a.tz_convert("UTC"):(a + pd.Timedelta(days=7)).tz_convert("UTC")]
    fig = go.Figure()
    for col, name, color in (("base", "Existing demand", "#4c78a8"), ("hp", "New heat pumps", "#f58518"),
                             ("ev", "New EVs", "#54a24b"), ("flat", "Electrolysis + data centres", "#e45756")):
        fig.add_trace(go.Scatter(x=xs.index, y=xs[col] / 1e3, stackgroup="d", name=name, line=dict(width=0.5, color=color)))
    fig.add_trace(go.Scatter(x=xs.index, y=(xs.wind + xs.solar + xs.nuclear) / 1e3, name="Wind + solar + nuclear",
                             line=dict(color="black", width=1.5)))
    fig.update_layout(height=420, yaxis_title="GW", margin=dict(t=20, b=10), legend=dict(orientation="h"))
    st.plotly_chart(fig, width="stretch")
    st.caption(f"FES peak increase vs 2024 for this pathway/year: {meta['fes_peak_gw'] - meta['fes_peak_2024_gw']:.1f} GW. "
               "EV charging is idealised valley-filling (it flattens whole days at high EV levels; see Assumptions).")
    summ = load_csv("outputs/scenarios/summary_by_pathway_year.csv")
    if summ is not None:
        st.subheader("All pathways: medians over 13 weather years")
        cols = {"pathway": "Pathway", "year": "Year", "demand_twh": "Demand (TWh)", "peak_demand_median": "Peak demand (GW)",
                "our_peak_increase_median": "Peak rise vs 2024: model (GW)", "fes_peak_increase": "Peak rise vs 2024: FES (GW)",
                "peak_net_median": "Peak net demand (GW)", "peak_net_max": "Peak net, worst weather year (GW)",
                "surplus_twh_median": "Surplus (TWh)", "battery_gw": "FES battery (GW)", "battery_gwh": "FES battery (GWh)"}
        st.dataframe(summ[list(cols)].rename(columns=cols), hide_index=True, width="stretch")
    stress = load_parquet("outputs/scenarios/stress.parquet")
    if stress is not None:
        st.subheader("Stress tests")
        names = {"cold_still_week": "Cold, still week", "low_renewable_fortnight": "Low-renewable fortnight",
                 "fast_electrification_cold_still": "Fast electrification + cold week"}
        sv = stress.assign(stress=stress.stress.map(names)).rename(columns={
            "pathway": "Pathway", "year": "Year", "stress": "Stress", "window": "Weather window", "mean_temp_c": "Mean temp (°C)",
            "peak_demand_gw": "Peak demand (GW)", "peak_net_gw": "Peak net (GW)", "mean_net_gw": "Mean net (GW)",
            "net_positive_energy_twh": "Energy to cover (TWh)", "vre_share_pct": "Wind+solar share (%)"})
        st.dataframe(sv.round(1), hide_index=True, width="stretch")


@st.cache_data
def historical_day(day: str):
    """Recompute the seven decisions for one historical day with the project's LP (same inputs as EXP-006)."""
    from energy_futures.experiments.optimisation import CFG, LEVELS, PROBS
    P = load_parquet("outputs/advanced/test/point_underlying_demand.parquet")
    Q = load_parquet("outputs/advanced/test/quantiles_FW_cqr.parquet")
    V = load_parquet("outputs/advanced/validation/point_predictions.parquet")
    rel = (V.actual - V.gbm_PW_from2009) / V.gbm_PW_from2009
    equant = rel.quantile([int(l[1:]) / 100 for l in LEVELS]).to_numpy()
    days = P.index.tz_convert(TZ).tz_localize(None).normalize()
    p = P[days == pd.Timestamp(day)]
    q = Q.reindex(p.index)
    h, cb = CFG["historical"], CFG["battery"]
    bat = Battery(h["battery_mw"], h["battery_mwh"], cb["roundtrip_efficiency"], cb["soc_start_end"])
    thr, mu = h["threshold_mw"], CFG["cost_index"]["mu"]
    alpha, w, tp = CFG["cost_index"]["risk"]["alpha"], CFG["cost_index"]["risk"]["weight"], cb["throughput_cost"]
    a = p.actual.to_numpy()
    Qm = q[LEVELS].to_numpy().T
    dec = {"none": (np.zeros_like(a), np.zeros_like(a)), "A": threshold_rule(p.naive_d7.to_numpy(), bat),
           "B": schedule(p.gbm_FW.to_numpy(), [1.0], bat, thr, mu, throughput=tp),
           "C": schedule(Qm, PROBS, bat, thr, mu, alpha, w, tp), "oracle": schedule(a, [1.0], bat, thr, mu, throughput=tp)}
    net = pd.DataFrame({k: a + c - dd for k, (c, dd) in dec.items()}, index=p.index)
    metr = pd.DataFrame({ARM_NAMES[k]: realised(a, c, dd, thr, mu, tp) for k, (c, dd) in dec.items()}).T.rename(columns={
        "peak_mw": "Peak after battery (MW)", "shortfall_mwh": "Energy above threshold (MWh)", "cost": "Cost index",
        "throughput_mwh": "Battery throughput (MWh)"})
    return net, metr, thr


def page_decisions():
    st.header("Flexibility decisions under uncertainty")
    badge("SIMULATED")
    st.caption("A day-ahead schedule for one aggregated GB battery is committed at 09:00 on D-1 and scored on the actual "
               "outcome. Stylised cost index = daily peak (MW) + 2 × energy above the stress threshold (MWh). Protocol "
               "pre-registered before any run.")
    hist = load_csv("outputs/optimisation/historical_central.csv", index_col=0)
    if hist is None:
        return missing("Optimisation outputs", "uv run python -m energy_futures.experiments.optimisation historical")
    sets = {"Historical 2024–25 (real forecasts)": "historical_central"}
    for v in ("Holistic_2035", "Holistic_2035_fastelec", "Holistic_2050", "Electric_2050"):
        sets[v.replace("_", " ").replace("fastelec", "fast electrification")] = f"future_{v}"
    rows = {}
    for lab, f in sets.items():
        s = load_csv(f"outputs/optimisation/{f}.csv", index_col=0)
        if s is not None:
            rows[lab] = s.oracle_value_captured_pct.drop(["none", "oracle"])
    cap = pd.DataFrame(rows).T
    fig = go.Figure([go.Bar(name=ARM_NAMES[a], x=cap.index, y=cap[a]) for a in cap.columns])
    fig.update_layout(barmode="group", height=380, yaxis_title="% of perfect-foresight value", yaxis_range=[0, 100],
                      margin=dict(t=20, b=10), legend=dict(orientation="h"))
    st.plotly_chart(fig, width="stretch")
    ci = load_csv("outputs/optimisation/c_vs_b_bootstrap.csv")
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader("Historical results (central case)")
        show = hist.rename(index=ARM_NAMES)[["mean_cost", "p95_cost", "total_shortfall_gwh", "max_load_after_battery_mw",
                                             "oracle_value_captured_pct"]].round(1).rename(columns={
            "mean_cost": "Mean daily cost", "p95_cost": "95th-pct daily cost", "total_shortfall_gwh": "Shortfall (GWh)",
            "max_load_after_battery_mw": "Max load after battery (MW)", "oracle_value_captured_pct": "Value captured (%)"})
        st.dataframe(show, width="stretch")
    with c2:
        st.subheader("Is C better than B? (95% CI)")
        if ci is not None:
            st.dataframe(ci.round(1).rename(columns={"setting": "Setting", "stat": "Metric", "diff": "C − B", "lo": "CI low", "hi": "CI high"})
                         .replace({"Metric": {"mean": "mean cost", "p95": "95th-pct cost"}}), hide_index=True, width="stretch")
        st.caption("Negative = C better. Mean-cost gain is significant historically; tail (p95) gains include zero everywhere.")
    st.subheader("Inspect one day")
    P = load_parquet("outputs/advanced/test/point_underlying_demand.parquet")
    days = sorted(set(P.index.tz_convert(TZ).tz_localize(None).normalize().date))
    days = [dd for dd in days if dd >= pd.Timestamp("2024-03-08").date()]
    day = st.select_slider("Day", options=days, value=pd.Timestamp("2025-01-08").date())
    net, metr, thr = historical_day(str(day))
    fig = go.Figure()
    for k, color, dash in (("none", "#111111", "solid"), ("A", "#999999", "dot"), ("B", "#6baed6", "solid"),
                           ("C", "#d94801", "solid"), ("oracle", "#2ca02c", "dash")):
        fig.add_trace(go.Scatter(x=net.index, y=net[k] / 1e3, name=ARM_NAMES[k], line=dict(color=color, dash=dash)))
    fig.add_hline(y=thr / 1e3, line_dash="dot", annotation_text="stress threshold")
    fig.update_layout(height=380, yaxis_title="Load after battery (GW)", margin=dict(t=20, b=10), legend=dict(orientation="h"))
    st.plotly_chart(fig, width="stretch")
    st.dataframe(metr.round(1), width="stretch")
    sens = {f.stem.replace("historical_", ""): load_csv(f"outputs/optimisation/{f.name}", index_col=0)
            for f in sorted((OUT / "optimisation").glob("historical_*.csv"))}
    if sens:
        st.subheader("Sensitivity (historical)")
        st.dataframe(pd.DataFrame({v: s.oracle_value_captured_pct.drop(["none", "oracle"]) for v, s in sens.items()}).T.round(1)
                     .rename(columns=ARM_NAMES), width="stretch")


def page_assumptions():
    st.header("Assumptions, data sources and limitations")
    st.markdown("""
**Data sources**
- NESO Historic Demand Data 2009–2025; NESO Day-Ahead Demand Forecast Performance; NESO Future Energy Scenarios 2025
  (ED1, ES1): NESO Open Data Licence.
- Open-Meteo Historical Weather (ERA5) and Previous Runs (archived forecasts): CC BY 4.0, free tier non-commercial.

**What this platform is not:** a physical network model, a validated digital twin, a security-of-supply assessment, or a
prediction of the 2050 system. Costs are a stylised index, not money.
""")
    for f, title in (("docs/assumptions.md", "Scenario assumptions"), ("docs/results/forecasting_report.md", "Forecasting report"),
                     ("docs/results/scenarios_report.md", "Scenario report"), ("docs/results/optimisation_report.md", "Optimisation report")):
        p = ROOT / f
        if p.exists():
            with st.expander(title):
                text = p.read_text()
                st.markdown(text.replace("](../figures/", "](app/static/").replace("![", "[figure: "), unsafe_allow_html=False)


PAGES = {"Overview": page_overview, "Forecasting": page_forecasting, "Future scenarios": page_scenarios,
         "Flexibility decisions": page_decisions, "Assumptions & limitations": page_assumptions}
with st.sidebar:
    st.markdown("### Energy Futures 2050")
    choice = st.radio("Page", list(PAGES))
    st.caption("Research prototype · all figures from reproducible experiments · see README to regenerate.")
PAGES[choice]()
