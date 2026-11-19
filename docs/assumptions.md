# Scenario assumptions (Batch 5)

_Every input to the scenario engine, its source, and its status. Inputs from FES are read from the downloaded files at run time; nothing below is typed in by hand except the labelled assumptions._

## FES 2025 inputs (Step 31)

Source: NESO Future Energy Scenarios 2025 data tables, NESO Open Data Licence. Files: `fes2025_ed1_v006.csv` (demand), `fes2025_es1_v006.csv` (supply), `fes2025_ed2_v004.pdf` (definitions); download script `energy_futures/ingest/fes.py`.

Pathways used: **Holistic Transition, Electric Engagement, Hydrogen Evolution, Falling Behind** (Falling Behind does not meet net zero). Ten Year Forecast is excluded because it stops at 2035. FES describes these as pathways, not forecasts.

| Engine input | FES item | Unit |
| --- | --- | --- |
| Total demand change | GBFES System Demand: Total | GWh, fiscal year |
| EV energy | Residential + Commercial Electric Vehicles Demand (EVs) | GWh |
| Heat-pump energy | Residential Heat Pumps | GWh |
| Flat new load | Networked Electrolysis + Data Centre Demand | GWh |
| Peak check | GBFES Peak Customer Demand: Total Consumption plus Losses | GW |
| EV / HP at peak (check) | Residential + Commercial EVs at Peak; Residential + Commercial Heat Pumps at Peak | GW |
| Wind, solar energy | Generation + Curtailment (TWh), Offshore Wind, Onshore Wind, Solar PV | TWh |
| Nuclear | Generation (TWh), Nuclear | TWh |
| Storage (for Batch 6) | Capacity (MW) and Storage Capacity (GWh), Battery and Long Duration Energy Storage | MW, GWh |

Selected FES values, Holistic Transition (for orientation):

| | 2024 | 2035 | 2050 |
| --- | --- | --- | --- |
| System demand (TWh) | 289.7 | 433.4 | 705.2 |
| Peak customer demand (GW) | 58.3 | 74.3 | 120.1 |
| EV energy (TWh) | 6.1 | 73.5 | 126.1 |
| Residential heat pumps (TWh) | 1.1 | 17.0 | 53.9 |
| Electrolysis + data centres (TWh) | 7.6 | 49.1 | 154.0 |
| Offshore + onshore wind generation (TWh) | 92 | 419 | 492 |
| Solar generation (TWh) | 19 | 44 | 83 |
| Battery / LDES energy capacity (GWh) | 9 / 28 | 43 / 126 | 59 / 219 |

## Method decisions (Steps 32–34)

| ID | Assumption | Status | Effect if wrong |
| --- | --- | --- | --- |
| A1 | Demand is built **additively**: our 2024 underlying demand plus the FES change since FES 2024 (D-031) | Method choice | Avoids mixing FES's and NESO-outturn demand definitions. Assumes the FES change applies to our definition. |
| A2 | FES fiscal years are mapped to calendar weather years | Simplification | Energy is shifted by about a quarter-year; immaterial for shapes |
| A3 | Weather years 2013–2025 (13). Each weather year's demand is rescaled to the 2024 energy level | Method choice | The weather-year spread is the uncertainty range shown. Older years carry older behaviour patterns. |
| A4 | Heat pumps: load ∝ heating degree-hours (15.5 °C base) ÷ COP; air-source COP = 6.08 − 0.09ΔT + 0.0005ΔT² (Staffell et al., 2012), flow temperature **45 °C (assumption)**; flat within each day | Assumption | Hot-water share 0.2 sensitivity: −2.8 GW on the 2050 median peak. Within-day heating peaks are ignored. |
| A5 | Only *residential* heat-pump energy has its own shape; commercial heat pumps (no FES GWh figure) follow the existing demand shape | Data limitation | Under-states winter peaks (see check) |
| A6 | EVs: 100% **idealised valley-filling** within each day (central). Sensitivity: 30% unmanaged charging, 17:00–22:00 | Assumption | **Largest lever found:** +11 GW on the 2035 median peak (Holistic). Above about 2040 valley-filling flattens whole days (artefact). |
| A7 | Electrolysis and data centres run flat all year | Assumption | Electrolysis is flexible in reality; this over-states peak demand |
| A8 | Wind (offshore and onshore) uses the historical **embedded-wind** capacity-factor shape; solar uses embedded solar; scaled to FES energy | Data limitation | Offshore output is smoother and higher-yielding; variability is likely over-stated |
| A9 | Nuclear is flat at FES annual energy (no outages) | Simplification | Over-states firm output in some hours |
| A10 | Net demand = demand − wind − solar − nuclear, before exports, storage, curtailment and dispatchable plant | Definition | Surplus is "available for export, storage or curtailment", not wasted energy |

## Stress definitions (Step 35)

- **Cold, still week:** the 7-day window from 2013–2025 with the lowest combined standardised temperature and embedded-wind capacity factor → **9–15 Dec 2022** (GB mean −1.8 °C).
- **Low-renewable fortnight:** the 14-day window with the lowest wind + solar output for the FES 2035 Holistic mix → **2–15 Sep 2014**.
- **Fast electrification:** 2035 demand with the 2040 levels of EV, heat-pump and flat load (same pathway), in the cold, still week.
