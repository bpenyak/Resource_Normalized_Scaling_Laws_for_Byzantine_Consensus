#!/usr/bin/env python3
"""Algorithm 2: chance-constrained validator-set sizing, and the X8 ablation.

Two constraints:

  (P)  Pr( TPS(n, c) >= D_peak ) >= 1 - eps_p
       deterministic equivalent (Lemma 1):
           log T0 + gamma log c - beta log n - z_{1-eps_p} s(n, c) >= log D

  (S)  p_miss(n, w) <= eps_s
       with p_miss <= exp(-2 n_eff w eps_0^2), n_eff = n / (1 + (k-1) rho)
       giving  n >= n_min = (1 + (k-1) rho) ln(1/eps_s) / (2 w eps_0^2)

Theorem 2 states the feasible set is the closed interval [n_min, n_max]; an
empty interval is a certificate that no validator-set size meets the
requirement.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import curve_fit


def g_of_c(c: float, gamma: float, c_sat: float, theta: float) -> float:
    if not math.isfinite(c_sat) or not math.isfinite(theta):
        return c ** gamma
    return c ** gamma / (1.0 + (c / c_sat) ** theta)


class Sizer:
    def __init__(self, fit: dict, eps_p: float):
        self.log_T0 = fit["log_T0"]
        self.gamma = fit["gamma"]
        self.beta = fit["beta"]
        self.sigma = fit["sigma"]
        self.cov = np.array(fit["cov"], dtype=float)
        self.c_sat = fit.get("c_sat", float("nan"))
        self.theta = fit.get("theta", float("nan"))
        self.z = stats.norm.ppf(1.0 - eps_p)

    def s(self, n: float, c: float) -> float:
        u = np.array([1.0, math.log(c), -math.log(n)])
        return float(np.sqrt(u @ self.cov @ u + self.sigma ** 2))

    def h(self, n: float, c: float, demand: float) -> float:
        """Constraint (P) in the form h(n) >= 0. Strictly decreasing in n."""
        mean = (self.log_T0 + self.gamma * math.log(c)
                - self.beta * math.log(n))
        # Saturation correction relative to the pure power law in c.
        mean += math.log(max(g_of_c(c, self.gamma, self.c_sat, self.theta), 1e-300)) \
            - self.gamma * math.log(c)
        return mean - self.z * self.s(n, c) - math.log(demand)

    def lower_bound_tps(self, n: float, c: float) -> float:
        mean = (self.log_T0 + math.log(max(g_of_c(c, self.gamma, self.c_sat,
                                                  self.theta), 1e-300))
                - self.beta * math.log(n))
        return float(math.exp(mean - self.z * self.s(n, c)))

    def n_max(self, c: float, demand: float, hi: int = 100000) -> int | None:
        """Bisection; correctness certified by strict monotonicity of h."""
        lo = 4
        if self.h(lo, c, demand) < 0:
            return None
        if self.h(hi, c, demand) >= 0:
            return hi
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if self.h(mid, c, demand) >= 0:
                lo = mid
            else:
                hi = mid
        return lo


def n_min_from_safety(p_d: float, p_f: float, faulty_fraction: float,
                      rho: float, w: int, tau: float,
                      eps_s: float, k_hint: int = 1) -> tuple[float, float]:
    """Corollary 3. Returns (n_min, eps_0)."""
    mu_b = p_d * faulty_fraction + p_f * (1.0 - faulty_fraction)
    eps_0 = mu_b - tau
    if eps_0 <= 0:
        return float("inf"), eps_0
    design_effect = 1.0 + max(k_hint - 1, 0) * max(rho, 0.0)
    return (design_effect * math.log(1.0 / eps_s)
            / (2.0 * w * eps_0 ** 2)), eps_0


def ablation(dataset: pd.DataFrame, fit: dict, demand: float, c: float,
             eps_p: float, cost_per_node: float) -> pd.DataFrame:
    """X8: sizing decision and provisioning cost under competing models."""
    d = dataset[(dataset["loss_pct"] == 0) & (dataset["rtt_ms"] == 0)]
    ns = d["n"].to_numpy(float)
    ys = d["tps_norm"].to_numpy(float)
    rows = []

    def truth(n: float) -> float:
        """Best available estimate of achievable throughput at n."""
        return math.exp(fit["log_T0"]
                        + math.log(max(g_of_c(c, fit["gamma"],
                                              fit.get("c_sat", float("nan")),
                                              fit.get("theta", float("nan"))),
                                       1e-300))
                        - fit["beta"] * math.log(n))

    def record(name: str, n_rec: float | None):
        if n_rec is None or not math.isfinite(n_rec):
            rows.append({"model": name, "n": None, "meets_demand": False,
                         "cost": float("nan"),
                         "note": "no feasible size"})
            return
        n_rec = max(4, int(round(n_rec)))
        achieved = truth(n_rec)
        rows.append({"model": name, "n": n_rec,
                     "meets_demand": bool(achieved >= demand),
                     "achieved_tps": achieved,
                     "cost": cost_per_node * n_rec})

    # Linear model: assumes throughput does not degrade -> pick the largest n
    # the operator can afford; here, the largest measured.
    record("linear", float(ns.max()))

    # Single-factor power law fitted to the same data (the first prior paper).
    slope, intercept, *_ = stats.linregress(np.log(ns), np.log(ys))
    if slope > 0:
        # alpha > 0 predicts throughput growing with n: the model recommends
        # the smallest n that meets demand, which it always believes it can.
        n_single = math.exp((math.log(demand) - intercept) / slope)
    else:
        n_single = math.exp((intercept - math.log(demand)) / (-slope))
    record("single_factor", n_single)

    # USL.
    try:
        popt, _ = curve_fit(
            lambda n, T, s_, k_: T * n / (1 + s_ * (n - 1) + k_ * n * (n - 1)),
            ns, ys, p0=[ys.mean(), 0.1, 0.01],
            bounds=([1e-9, 0, 0], [np.inf, 1, 1]), maxfev=20000)
        cand = [n for n in range(4, 1001)
                if popt[0] * n / (1 + popt[1] * (n - 1)
                                  + popt[2] * n * (n - 1)) >= demand]
        record("usl", max(cand) if cand else None)
    except Exception:  # noqa: BLE001
        record("usl", None)

    sizer = Sizer(fit, eps_p)
    record("chance_constrained", sizer.n_max(c, demand))
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--out", dest="out", type=Path, required=True)
    ap.add_argument("--demand", type=float, default=2100.0,
                    help="peak demand in transactions per second")
    ap.add_argument("--concurrency", type=float, default=64.0)
    ap.add_argument("--eps-p", type=float, default=0.05)
    ap.add_argument("--eps-s", type=float, default=0.01)
    ap.add_argument("--window", type=int, default=30)
    ap.add_argument("--tau", type=float, default=0.10,
                    help="alarm threshold on the estimated faulty fraction")
    ap.add_argument("--faulty-fraction", type=float, default=0.20)
    ap.add_argument("--cost-per-node", type=float, default=1.0)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    fit = json.loads((args.inp / "fit.json").read_text(encoding="utf-8"))
    dataset = pd.read_csv(args.inp / "dataset.csv")
    det = fit.get("detector", {})

    sizer = Sizer(fit, args.eps_p)
    n_max = sizer.n_max(args.concurrency, args.demand)

    k_hint = max(int(round(args.faulty_fraction * (n_max or 10))), 1)
    n_min, eps_0 = n_min_from_safety(
        det.get("p_d", float("nan")), det.get("p_f", float("nan")),
        args.faulty_fraction, det.get("rho", 0.0), args.window, args.tau,
        args.eps_s, k_hint)

    feasible = (n_max is not None and math.isfinite(n_min)
                and max(4, math.ceil(n_min)) <= n_max)
    n_opt = max(4, math.ceil(n_min)) if feasible else None

    result = {
        "demand": args.demand,
        "concurrency": args.concurrency,
        "eps_p": args.eps_p,
        "eps_s": args.eps_s,
        "window": args.window,
        "tau": args.tau,
        "faulty_fraction": args.faulty_fraction,
        "eps_0": eps_0,
        "n_min": n_min,
        "n_max": n_max,
        "n_opt": n_opt,
        "feasible": bool(feasible),
        "certificate": None if feasible else
        "empty feasibility window: no validator-set size meets both constraints",
        "curve": [
            {"n": n,
             "lower_tps": sizer.lower_bound_tps(n, args.concurrency),
             "h": sizer.h(n, args.concurrency, args.demand)}
            for n in range(4, 201)
        ],
    }
    (args.out / "sizing.json").write_text(json.dumps(result, indent=2),
                                          encoding="utf-8")

    abl = ablation(dataset, fit, args.demand, args.concurrency, args.eps_p,
                   args.cost_per_node)
    if not abl.empty:
        base = abl.loc[abl["model"] == "chance_constrained", "cost"]
        if len(base) and math.isfinite(base.iloc[0]) and base.iloc[0] > 0:
            abl["relative_cost"] = abl["cost"] / base.iloc[0]
    abl.to_csv(args.out / "sizing_ablation.csv", index=False)

    print(f"n_min={n_min:.2f} n_max={n_max} n_opt={n_opt} feasible={feasible}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
