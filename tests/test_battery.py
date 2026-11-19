"""Batch 6 tests: LP physics, hand-checkable optimum, oracle bound, rule feasibility."""
import numpy as np
import pytest

from energy_futures.optimise.battery import Battery, project_feasible, realised, schedule, soc_path, threshold_rule

BAT = Battery(power_mw=10.0, energy_mwh=20.0, roundtrip=1.0, soc0=0.5)


def test_soc_bounds_and_daily_balance():
    rng = np.random.default_rng(0)
    L = 100 + 20 * np.sin(np.linspace(0, 2 * np.pi, 48)) + rng.normal(0, 2, 48)
    b = Battery(10, 20, 0.88)
    c, d = schedule(L, [1.0], b, threshold=115, mu=2)
    s = soc_path(c, d, b)
    assert s.min() >= -1e-6 and s.max() <= 20 + 1e-6
    assert s[-1] == pytest.approx(s[0], abs=1e-6)
    assert (c <= 10 + 1e-9).all() and (d <= 10 + 1e-9).all()


def test_hand_checkable_peak_shave():
    # Flat 50 MW with a 2-period spike to 70 MW; lossless battery with 10 MWh available above start
    # (soc0=0.5 of 20 MWh) and 10 MW power: the optimum discharges 10 MW during both spike periods
    # (10 MWh in 1 h) and recharges elsewhere, so the peak falls from 70 to 60 MW.
    L = np.full(48, 50.0)
    L[20:22] = 70.0
    c, d = schedule(L, [1.0], BAT, threshold=1e9, mu=0, throughput=0)
    net = L + c - d
    assert net.max() == pytest.approx(60.0, abs=1e-6)


def test_oracle_is_best_on_realised_cost():
    rng = np.random.default_rng(1)
    actual = 100 + 25 * np.sin(np.linspace(0, 2 * np.pi, 48)) + rng.normal(0, 3, 48)
    forecast = actual + rng.normal(0, 5, 48)
    b = Battery(15, 30, 0.88)
    oc, od = schedule(actual, [1.0], b, 118, 2.0)
    fc, fd = schedule(forecast, [1.0], b, 118, 2.0)
    assert realised(actual, oc, od, 118, 2.0)["cost"] <= realised(actual, fc, fd, 118, 2.0)["cost"] + 1e-6


def test_cvar_weight_zero_equals_expected_value():
    L = np.vstack([np.full(48, 50.0), np.full(48, 60.0)])
    L[:, 30] += 15
    c1, d1 = schedule(L, [0.5, 0.5], BAT, 62, 2.0, alpha=0.9, w=0.0)
    c2, d2 = schedule(L, [0.5, 0.5], BAT, 62, 2.0, alpha=0.5, w=0.0)
    assert np.allclose(c1 - d1, c2 - d2, atol=1e-6)


def test_rule_is_feasible():
    L = 100 + 30 * np.sin(np.linspace(0, 2 * np.pi, 48))
    b = Battery(10, 20, 0.88)
    c, d = threshold_rule(L, b)
    s = soc_path(c, d, b)
    assert s.min() >= -1e-6 and s.max() <= 20 + 1e-6 and d.sum() > 0
