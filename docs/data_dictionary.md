# Data dictionary

_Verified 2026-11-18 against the NESO Data Portal field definitions (Historic Demand Data 2025 page)._

## NESO Historic Demand Data

- **Source:** https://www.neso.energy/data-portal/historic-demand-data (one CSV per year; URLs resolved via the CKAN API at download time).
- **Licence:** NESO Open Data Licence (based on OGL v3). Attribution: "Supported by National Energy SO Open Data".
- **Coverage:** Great Britain (England, Wales, Scotland); Northern Ireland is not included. Yearly files from 2001; this project uses **2009–2025** (D-011).
- **Resolution:** half-hourly settlement periods. Period 1 = 00:00–00:30 **local time**; days have 46 (March clock change), 48 or 50 (October) periods. Settlement date follows the clock change.
- **Units:** MW (average power over the half hour).

| Column | Meaning | Measured or estimated | Used for |
| --- | --- | --- | --- |
| SETTLEMENT_DATE, SETTLEMENT_PERIOD | Local date and half-hour index | — | → `timestamp_utc` (period start, UTC) |
| ND | National Demand: GB generation requirement; sum of transmission-metered generation, **excluding** station load, pump-storage pumping and interconnector exports | Metered | Target component |
| TSD | Transmission System Demand = ND + station load + pumping + exports; includes an **assumed** station load of 500 MW (BST) / 600 MW (GMT) | Metered + assumption | Secondary / cross-check |
| ENGLAND_WALES_DEMAND | ND for England and Wales only | Metered | Not used in MVP |
| EMBEDDED_WIND_GENERATION / _CAPACITY | Wind on the distribution network, invisible to NESO | **Modelled estimate** | Target component |
| EMBEDDED_SOLAR_GENERATION / _CAPACITY | Rooftop and distribution-connected solar PV | **Modelled estimate** | Target component |
| NON_BM_STOR | Short-term operating reserve outside the Balancing Mechanism | Metered | Not used |
| PUMP_STORAGE_PUMPING | Pumped-hydro pumping load | Metered | Not used |
| SCOTTISH_TRANSFER, *_FLOW | Scotland→E&W transfer and interconnector flows (+ import, − export) | Metered | Not used in MVP; relevant to Phase 2 |
| FORECAST_ACTUAL_INDICATOR | 'A' actual or 'F' forecast (recent files only) | — | **'F' rows excluded** (leakage risk) |

### Derived target (D-010)

`underlying_demand = ND + EMBEDDED_SOLAR_GENERATION + EMBEDDED_WIND_GENERATION` (MW).

This approximates demand before local generation offsets it, so growth in rooftop solar doesn't show up as a fall in demand. **Caveat:** two of the three terms are NESO model estimates, so the target inherits NESO's estimation error. ND is kept as an alternative target for comparison.

## Open-Meteo Historical Weather API

- **Source:** https://archive-api.open-meteo.com/v1/archive (ERA5 / ERA5-Land reanalysis plus ECMWF IFS analysis from 2017).
- **Licence:** CC BY 4.0. **The free API is for non-commercial use only**; any industry use needs a paid licence or raw ERA5 from Copernicus.
- **Locations:** London, Birmingham, Manchester, Newcastle, Glasgow, Cardiff (`configs/data.yaml`). Equal-weight GB mean for now (D-012).
- **Resolution:** hourly, UTC. Aligned to half-hour period starts (see `clean/weather.py`):

| Variable | Unit | Definition | Alignment |
| --- | --- | --- | --- |
| temperature_2m | °C | Instantaneous at the hour | Linear interpolation |
| wind_speed_10m | km/h | Instantaneous | Linear interpolation |
| cloud_cover | % | Instantaneous | Linear interpolation |
| shortwave_radiation | W/m² | Mean of the **preceding** hour | Value of the hour containing the period |

**Leakage caveat:** reanalysis is weather *as it happened*. A real day-ahead forecaster only has weather *forecasts*. Forecasting experiments must label results that use this data as "perfect-weather", and compare with NESO's forecast only in a realistic-weather setting (D-009).
