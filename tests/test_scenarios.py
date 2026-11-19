"""Batch 5 tests: energy conservation, base reproduction, shapes, valley filling, FES parsing."""
import numpy as np
import pandas as pd
import pytest
import yaml

from energy_futures.config import ROOT
from energy_futures.scenarios import engine, fes, profiles


@pytest.fixture(scope="module")
def setup():
    if not (ROOT / "data/raw/fes/fes2025_ed1_v006.csv").exists():
        pytest.skip("FES data not downloaded")
    cfg = yaml.safe_load(open(ROOT / "configs/scenarios.yaml"))
    d = pd.read_parquet(ROOT / "data/processed/demand_weather.parquet")
    return cfg, d, fes.demand_table(ROOT / cfg["fes"]["ed1"]), fes.supply_table(ROOT / cfg["fes"]["es1"])


def test_base_year_reproduces_history(setup):
    cfg, d, D, S = setup
    x, _ = engine.build(d, D, S, "Holistic Transition", 2024, 2024, cfg)
    actual = engine.weather_year_frame(d, 2024).underlying_demand
    assert np.allclose(x.demand, actual) and x.ev.abs().max() == 0 and x.hp.abs().max() == 0


@pytest.mark.parametrize("pathway,year,w", [("Holistic Transition", 2035, 2018), ("Electric Engagement", 2050, 2013),
                                            ("Falling Behind", 2040, 2022)])
def test_annual_energy_change_equals_fes_change(setup, pathway, year, w):
    cfg, d, D, S = setup
    x, _ = engine.build(d, D, S, pathway, year, w, cfg)
    ref = engine.energy_mwh(engine.weather_year_frame(d, 2024).underlying_demand)
    fes_change = (D.loc[(pathway, year)].total_gwh - D.loc[(pathway, 2024)].total_gwh) * 1e3
    assert engine.energy_mwh(x.demand) - ref == pytest.approx(fes_change, rel=1e-6)


def test_supply_energy_equals_fes(setup):
    cfg, d, D, S = setup
    x, _ = engine.build(d, D, S, "Holistic Transition", 2050, 2019, cfg)
    s = S.loc[("Holistic Transition", 2050)]
    assert engine.energy_mwh(x.solar) / 1e6 == pytest.approx(s.solar_gen_twh + s.solar_curt_twh, rel=1e-6)
    assert engine.energy_mwh(x.nuclear) / 1e6 == pytest.approx(s.nuclear_gen_twh, rel=1e-6)


def test_fast_electrification_only_changes_new_loads(setup):
    cfg, d, D, S = setup
    a, _ = engine.build(d, D, S, "Holistic Transition", 2035, 2020, cfg)
    b, _ = engine.build(d, D, S, "Holistic Transition", 2035, 2020, cfg, electrification_year=2040)
    assert np.allclose(a.base, b.base) and engine.energy_mwh(b.ev) > engine.energy_mwh(a.ev)


def test_cop_range_plausible():
    cop = profiles.staffell_ashp_cop(pd.Series([-5.0, 0.0, 7.0, 15.0]), 45.0)
    assert cop.is_monotonic_increasing and 2.0 < cop.iloc[0] < 3.0 and 3.0 < cop.iloc[-1] < 4.5


def test_valley_fill_conserves_energy_and_fills_troughs():
    idx = pd.date_range("2024-01-01", periods=96, freq="30min", tz="UTC")
    load = pd.Series(np.tile(np.r_[np.full(24, 20.0), np.full(24, 40.0)], 2), index=idx)
    ev = profiles.valley_fill(load, annual_mwh=200.0)
    assert ev.sum() / 2 == pytest.approx(200.0)
    assert (ev[load == 40.0] == 0).all() and (load + ev).max() == pytest.approx(40.0)


def test_shapes_sum_to_one():
    idx = pd.date_range("2024-01-01", periods=48 * 3, freq="30min", tz="UTC")
    t = pd.Series(np.linspace(-3, 12, len(idx)), index=idx)
    assert profiles.heat_pump_shape(t, 15.5, 45, 0.2).sum() == pytest.approx(1.0)
    assert profiles.window_shape(idx, 17, 22).sum() == pytest.approx(1.0)
