"""Scenario engine (Steps 32-34).

For pathway P, future year Y and historical weather year W, half-hourly demand is built ADDITIVELY
from our own 2024 underlying demand and the FES change since the base year (D-031):

    demand(t) = base_W(t) + EV(t) + HP(t) + FLAT
    base_W(t) = UD_W(t) * (E_UD,2024 + dOTHER) / E_UD,W      (weather year W, scaled to 2024 level)
    EV(t)     = dEV  * ev_shape(t)          dEV  = FES EV energy (res+com), Y minus base year
    HP(t)     = dHP  * hp_shape_W(t)        dHP  = FES residential heat-pump energy, Y minus base year
    FLAT      = dFLAT / hours               dFLAT = electrolysis + data centres, Y minus base year
    dOTHER    = dTOTAL - dEV - dHP - dFLAT  (everything else follows the historical shape)

Supply: wind and solar = FES (generation + curtailment) energy x historical capacity-factor shape of
weather year W; nuclear flat at FES energy. Net demand = demand - wind - solar - nuclear.

Using FES *changes* rather than levels avoids mixing two different demand definitions (FES system
demand incl. losses vs our underlying demand). Energy is preserved exactly: the annual demand change
equals the FES change by construction (tested).
"""
import numpy as np
import pandas as pd

from energy_futures.scenarios import profiles

TZ = "Europe/London"
MWH_PER_GWH, MWH_PER_TWH = 1e3, 1e6


def weather_year_frame(d: pd.DataFrame, w: int) -> pd.DataFrame:
    local_year = d.index.tz_convert(TZ).year
    return d[local_year == w]


def energy_mwh(mw: pd.Series) -> float:
    return float(mw.sum() / 2)


def build(d: pd.DataFrame, D: pd.DataFrame, S: pd.DataFrame, pathway: str, year: int, w: int, cfg: dict,
          electrification_year: int | None = None) -> tuple[pd.DataFrame, dict]:
    base_y = cfg["fes"]["base_year"]
    hp_cfg, ev_cfg = cfg["heat_pumps"], cfg["ev"]
    ey = electrification_year or year
    f0, fY, fE = D.loc[(pathway, base_y)], D.loc[(pathway, year)], D.loc[(pathway, ey)]

    # Electrification increments come from year `ey` (= year normally; later for the fast-electrification
    # stress test); everything else ("other") always comes from year `year`.
    dEV = (fE.ev_gwh - f0.ev_gwh) * MWH_PER_GWH
    dHP = (fE.hp_res_gwh - f0.hp_res_gwh) * MWH_PER_GWH
    dFLAT = (fE.flat_gwh - f0.flat_gwh) * MWH_PER_GWH
    dOTHER = ((fY.total_gwh - f0.total_gwh) - (fY.ev_gwh - f0.ev_gwh) - (fY.hp_res_gwh - f0.hp_res_gwh)
              - (fY.flat_gwh - f0.flat_gwh)) * MWH_PER_GWH

    W = weather_year_frame(d, w)
    ref = weather_year_frame(d, base_y)
    E_ref, E_w = energy_mwh(ref.underlying_demand), energy_mwh(W.underlying_demand)
    base = W.underlying_demand * (E_ref + dOTHER) / E_w

    temp = W.temperature_2m_gb_mean.interpolate(limit_direction="both")
    hp = 2 * dHP * profiles.heat_pump_shape(temp, hp_cfg["base_temp_c"], hp_cfg["flow_temp_c"], hp_cfg["hot_water_share"])
    flat = pd.Series(dFLAT / (len(W) / 2), index=W.index)

    unmanaged = profiles.window_shape(W.index, *ev_cfg["unmanaged_window_local"])
    pre_ev = base + hp + flat
    target = max(0.0, (fE.ev_peak_gw - f0.ev_peak_gw) * 1e3)
    # EV charging: `smart_share` of the energy is valley-filled (idealised managed charging), the rest
    # charges in the unmanaged evening window. Central case 1.0; sensitivity lower (D-033).
    share = float(ev_cfg["smart_share"])
    if dEV > 0:
        unm = 2 * dEV * (1 - share) * unmanaged
        ev = unm + (profiles.valley_fill(pre_ev + unm, dEV * share) if share > 0 else 0.0)
    else:
        ev = pd.Series(0.0, index=W.index)

    demand = base + ev + hp + flat
    sY = S.loc[(pathway, year)]
    wind_shape = profiles.capacity_factor_shape(W.embedded_wind_generation, W.embedded_wind_capacity)
    solar_shape = profiles.capacity_factor_shape(W.embedded_solar_generation, W.embedded_solar_capacity)
    wind_off = 2 * (sY.offshore_wind_gen_twh + sY.offshore_wind_curt_twh) * MWH_PER_TWH * wind_shape
    wind_on = 2 * (sY.onshore_wind_gen_twh + sY.onshore_wind_curt_twh) * MWH_PER_TWH * wind_shape
    solar = 2 * (sY.solar_gen_twh + sY.solar_curt_twh) * MWH_PER_TWH * solar_shape
    nuclear = pd.Series(sY.nuclear_gen_twh * MWH_PER_TWH / (len(W) / 2), index=W.index)
    out = pd.DataFrame({"base": base, "ev": ev, "hp": hp, "flat": flat, "demand": demand,
                        "wind": wind_off + wind_on, "solar": solar, "nuclear": nuclear,
                        "temp": temp})
    out["net"] = out.demand - out.wind - out.solar - out.nuclear
    meta = {"pathway": pathway, "year": year, "weather_year": w, "electrification_year": ey,
            "dEV_TWh": dEV / 1e6, "dHP_TWh": dHP / 1e6, "dFLAT_TWh": dFLAT / 1e6, "dOTHER_TWh": dOTHER / 1e6,
            "ev_smart_share": share,
            "fes_peak_gw": float(fY.peak_gw), "fes_peak_2024_gw": float(f0.peak_gw),
            "fes_ev_peak_increment_gw": target / 1e3,
            "fes_hp_peak_increment_gw": float((fE.hp_peak_gw - f0.hp_peak_gw)),
            "battery_mw": float(sY.battery_cap_mw), "battery_gwh": float(sY.battery_gwh),
            "ldes_mw": float(sY.ldes_cap_mw), "ldes_gwh": float(sY.ldes_gwh)}
    return out, meta


def metrics(x: pd.DataFrame) -> dict:
    pk = x.demand.idxmax()
    npk = x.net.idxmax()
    net_daily = x.net.resample("D").mean()
    ramp3h = x.net.diff(6).max()
    surplus = x.net.clip(upper=0)
    return {
        "demand_twh": energy_mwh(x.demand) / 1e6,
        "peak_demand_gw": x.demand.max() / 1e3,
        "peak_time_utc": str(pk),
        "ev_at_peak_gw": x.ev.loc[pk] / 1e3, "hp_at_peak_gw": x.hp.loc[pk] / 1e3,
        "peak_net_gw": x.net.max() / 1e3, "peak_net_time_utc": str(npk),
        "min_net_gw": x.net.min() / 1e3,
        "surplus_hours": float((x.net < 0).sum() / 2), "surplus_twh": -energy_mwh(surplus) / 1e6,
        "max_7day_mean_net_gw": net_daily.rolling(7).mean().max() / 1e3,
        "max_3h_net_ramp_gw": float(ramp3h / 1e3),
        "vre_share_pct": float((x.wind.sum() + x.solar.sum()) / x.demand.sum() * 100),
    }
