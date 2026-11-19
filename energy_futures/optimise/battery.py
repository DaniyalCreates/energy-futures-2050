"""Aggregated battery scheduling as a linear programme (Steps 37, 39, 40).

One day, T half-hours (46/48/50). Decision variables shared by all scenarios (a single day-ahead
schedule): charge c_t, discharge d_t (MW) and state of charge s_t (MWh). For each load scenario s:

    net_st = L_st + c_t - d_t
    z_s   >= net_st                      daily peak (MW)
    u_st  >= net_st - T, u_st >= 0       load above threshold (MW)
    cost_s = z_s + mu * 0.5 * sum_t u_st (stylised cost index)

Objective: (1-w) * sum_s p_s cost_s + w * CVaR_alpha(cost) + throughput cost.
CVaR uses the Rockafellar-Uryasev linearisation. With one scenario this is the deterministic problem.
Physical constraints: 0 <= c, d <= P; 0 <= s <= E; s_{t+1} = s_t + 0.5*eta_c*c_t - 0.5*d_t/eta_d;
s_0 = s_T = soc0 * E.
"""
from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix


@dataclass(frozen=True)
class Battery:
    power_mw: float
    energy_mwh: float
    roundtrip: float = 0.88
    soc0: float = 0.5

    @property
    def eta(self) -> float:
        return float(np.sqrt(self.roundtrip))


def schedule(L: np.ndarray, p: np.ndarray, bat: Battery, threshold: float, mu: float,
             alpha: float = 0.9, w: float = 0.0, throughput: float = 1e-3) -> tuple[np.ndarray, np.ndarray]:
    """L: (S, T) load scenarios in MW; p: (S,) probabilities. Returns (charge, discharge) MW arrays."""
    L = np.atleast_2d(np.asarray(L, float))
    S, T = L.shape
    p = np.asarray(p, float) / np.sum(p)
    eta = bat.eta
    # variable index offsets
    ic, id_, is_ = 0, T, 2 * T
    iz = is_ + T + 1
    iu = iz + S
    ieta = iu + S * T
    ixi = ieta + 1
    n = ixi + S

    rows, cols, vals, b_ub = [], [], [], []
    r = 0
    for s in range(S):
        for t in range(T):
            # c_t - d_t - z_s <= -L_st
            rows += [r, r, r]; cols += [ic + t, id_ + t, iz + s]; vals += [1, -1, -1]; b_ub.append(-L[s, t]); r += 1
            # c_t - d_t - u_st <= T - L_st
            rows += [r, r, r]; cols += [ic + t, id_ + t, iu + s * T + t]; vals += [1, -1, -1]; b_ub.append(threshold - L[s, t]); r += 1
        # cost_s - eta - xi_s <= 0
        rows += [r, r, r]; cols += [iz + s, ieta, ixi + s]; vals += [1, -1, -1]; b_ub.append(0.0)
        for t in range(T):
            rows.append(r); cols.append(iu + s * T + t); vals.append(0.5 * mu)
        r += 1
    A_ub = coo_matrix((vals, (rows, cols)), shape=(r, n)).tocsr()

    erows, ecols, evals, b_eq = [], [], [], []
    for t in range(T):
        erows += [t, t, t, t]; ecols += [is_ + t + 1, is_ + t, ic + t, id_ + t]
        evals += [1, -1, -0.5 * eta, 0.5 / eta]; b_eq.append(0.0)
    erows += [T, T + 1]; ecols += [is_, is_ + T]; evals += [1, 1]; b_eq += [bat.soc0 * bat.energy_mwh] * 2
    A_eq = coo_matrix((evals, (erows, ecols)), shape=(T + 2, n)).tocsr()

    cobj = np.zeros(n)
    cobj[ic:ic + 2 * T] = 0.5 * throughput
    cobj[iz:iz + S] = (1 - w) * p
    cobj[iu:iu + S * T] = (1 - w) * np.repeat(p, T) * 0.5 * mu
    cobj[ieta] = w
    cobj[ixi:ixi + S] = w * p / (1 - alpha)

    bounds = ([(0, bat.power_mw)] * (2 * T) + [(0, bat.energy_mwh)] * (T + 1) + [(None, None)] * S
              + [(0, None)] * (S * T) + [(None, None)] + [(0, None)] * S)
    res = linprog(cobj, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if res.status != 0:
        raise RuntimeError(f"LP failed: {res.message}")
    x = res.x
    return x[ic:ic + T], x[id_:id_ + T]


def soc_path(c: np.ndarray, d: np.ndarray, bat: Battery) -> np.ndarray:
    eta = bat.eta
    return bat.soc0 * bat.energy_mwh + np.concatenate([[0], np.cumsum(0.5 * eta * c - 0.5 * d / eta)])


def threshold_rule(L_hat: np.ndarray, bat: Battery) -> tuple[np.ndarray, np.ndarray]:
    """Arm A heuristic: discharge above a level chosen so the forecast peak is shaved using the energy
    available above the starting SoC; recharge in the lowest forecast periods by the same energy
    (after losses). Then enforce SoC bounds chronologically (any infeasible part is dropped)."""
    L_hat = np.asarray(L_hat, float)
    T = len(L_hat)
    eta = bat.eta
    e_out = bat.soc0 * bat.energy_mwh                 # stored energy available at the start of the day
    # discharge level by bisection on sum(min(P, max(L-lvl,0)))*0.5 = e_out*eta
    lo, hi = L_hat.min(), L_hat.max()
    for _ in range(60):
        lvl = (lo + hi) / 2
        de = np.minimum(bat.power_mw, np.maximum(L_hat - lvl, 0)).sum() * 0.5
        lo, hi = (lvl, hi) if de > e_out * eta else (lo, lvl)
    d = np.minimum(bat.power_mw, np.maximum(L_hat - hi, 0))
    e_in_needed = d.sum() * 0.5 / eta / eta          # grid energy to restore the SoC
    lo, hi = L_hat.min(), L_hat.max()
    for _ in range(60):
        lvl = (lo + hi) / 2
        ce = np.minimum(bat.power_mw, np.maximum(lvl - L_hat, 0)).sum() * 0.5
        lo, hi = (lo, lvl) if ce > e_in_needed else (lvl, hi)
    c = np.minimum(bat.power_mw, np.maximum(lo - L_hat, 0))
    c[d > 0] = 0
    return project_feasible(c, d, bat)


def project_feasible(c, d, bat: Battery):
    """Walk through the day enforcing 0 <= SoC <= E; trims any action that would breach a bound.
    End-of-day SoC is not forced back to soc0 here (the rule may end slightly off target)."""
    c, d = np.array(c, float), np.array(d, float)
    eta, s = bat.eta, bat.soc0 * bat.energy_mwh
    for t in range(len(c)):
        if c[t] > 0:
            c[t] = min(c[t], (bat.energy_mwh - s) / (0.5 * eta))
        if d[t] > 0:
            d[t] = min(d[t], s * eta / 0.5)
        s += 0.5 * eta * c[t] - 0.5 * d[t] / eta
    return c, d


def realised(L: np.ndarray, c: np.ndarray, d: np.ndarray, threshold: float, mu: float, throughput: float = 1e-3) -> dict:
    net = np.asarray(L) + c - d
    short = 0.5 * np.maximum(net - threshold, 0).sum()
    return {"peak_mw": float(net.max()), "shortfall_mwh": float(short),
            "cost": float(net.max() + mu * short + 0.5 * throughput * (c.sum() + d.sum())),
            "throughput_mwh": float(0.5 * (c.sum() + d.sum()))}
