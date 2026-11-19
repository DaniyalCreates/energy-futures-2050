"""Read FES 2025 (ED1 demand, ES1 supply) into tidy per-pathway, per-year values (Step 31)."""
import pandas as pd

ED1_ITEMS = {
    "total_gwh": "GBFES System Demand: Total",
    "peak_gw": "GBFES Peak Customer Demand: Total Consumption plus Losses",
    "ev_res_gwh": "Residential Electric Vehicles Demand (EVs)",
    "ev_com_gwh": "Commercial Electric Vehicles Demand (EVs)",
    "hp_res_gwh": "Residential Heat Pumps",
    "electrolysis_gwh": "GBFES Customer Demand: Networked Electrolysis",
    "datacentre_gwh": "Data Centre Demand",
    "ev_res_peak_gw": "Residential EVs at Peak",
    "ev_com_peak_gw": "Commercial EVs at Peak",
    "hp_res_peak_gw": "Residential Heat Pumps at Peak",
    "hp_com_peak_gw": "Commercial Heat Pumps at Peak",
}
ES1_TECH = {"offshore_wind": "Offshore Wind", "onshore_wind": "Onshore Wind", "solar": "Solar PV", "nuclear": "Nuclear"}
STORAGE = {"battery": "Battery", "ldes": "Long Duration Energy Storage"}


def demand_table(path) -> pd.DataFrame:
    """Rows = (pathway, year); columns = ED1_ITEMS keys. Units as in FES (GWh fiscal year, GW)."""
    e = pd.read_csv(path)
    e["Data item"] = e["Data item"].str.strip()
    years = [c for c in e.columns if c.isdigit()]
    rows = []
    for key, item in ED1_ITEMS.items():
        sub = e[e["Data item"] == item]
        if sub.empty:
            raise KeyError(f"FES ED1 item not found: {item}")
        for _, r in sub.iterrows():
            for y in years:
                rows.append({"pathway": r["Pathway"], "year": int(y), "key": key, "value": r[y]})
    t = pd.DataFrame(rows).pivot_table(index=["pathway", "year"], columns="key", values="value")
    t["ev_gwh"] = t.ev_res_gwh + t.ev_com_gwh
    t["flat_gwh"] = t.electrolysis_gwh + t.datacentre_gwh
    t["ev_peak_gw"] = t.ev_res_peak_gw + t.ev_com_peak_gw
    t["hp_peak_gw"] = t.hp_res_peak_gw + t.hp_com_peak_gw
    return t


def supply_table(path) -> pd.DataFrame:
    """Rows = (pathway, year); generation and curtailment (TWh), capacity (MW), storage (MW, GWh)."""
    s = pd.read_csv(path)
    years = [c for c in s.columns if c.isdigit()]
    long = s.melt(id_vars=["Connection", "Pathway", "Variable", "Category", "Type", "SubType"], value_vars=years,
                  var_name="year", value_name="value")
    long["year"] = long["year"].astype(int)
    g = long.groupby(["Pathway", "year", "Variable", "Type"])["value"].sum()
    out = {}
    for k, tech in ES1_TECH.items():
        out[f"{k}_gen_twh"] = g.xs(("Generation (TWh)", tech), level=("Variable", "Type"))
        out[f"{k}_cap_mw"] = g.xs(("Capacity (MW)", tech), level=("Variable", "Type"))
        if k != "nuclear":
            out[f"{k}_curt_twh"] = g.xs(("Curtailment (TWh)", tech), level=("Variable", "Type"))
    for k, tech in STORAGE.items():
        out[f"{k}_cap_mw"] = g.xs(("Capacity (MW)", tech), level=("Variable", "Type"))
        out[f"{k}_gwh"] = g.xs(("Storage Capacity (GWh)", tech), level=("Variable", "Type"))
    t = pd.DataFrame(out).fillna(0.0)
    t.index = t.index.set_names(["pathway", "year"])
    return t
