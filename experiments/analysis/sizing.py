#!/usr/bin/env python3
"""Chance-constrained validator-set sizing (Problem 1) and the X8 ablation.

Two constraints:

  (P)  Pr( kappa * TPS_RNM(n, c) >= D_peak ) >= 1 - eps_p
       deterministic equivalent:
           log kappa + log T0 + log g(c) - beta log n
             - z_{1-eps_p} s(n, c) >= log D

  (S)  p_miss(n, w) <= eps_s   (design-effect heuristic, paper eq. (nmin))
       with p_miss <~ exp(-2 w k (p_d - tau)^2 / (1 + (k-1) rho)),  k = ceil(phi n)
       where p_d, tau are PER-ROUND failure probabilities of a faulty validator
       and the detector threshold on the failure rate. They are NOT the flag
       rates (TPR/FPR) measured by X5, which are properties of a classifier at
       one operating point. (S) is therefore evaluated only when per-round
       parameters are supplied (--round-pd, --round-tau); otherwise it is
       relaxed and n_min = 4 (= 3f+1 with f = 1).

kappa is the production scale-up from RNM-normalized throughput (TPS/q) to the
absolute units of D_peak. Default ``auto`` sets kappa so that the lower
prediction bound at n=4 just meets demand — the minimal hardware class that
admits any validator set — and then n_max follows by bisection.

The operating concurrency defaults to the largest calibrated level, so the
prediction needs no extrapolation in c. The grid argmax of the fitted g(c)
(which uses the saturation parameters) is reported only as a sensitivity.
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


def g_of_c(c: float, gamma: float, c_sat: float, theta: float,
           c_cal: float = 0.0) -> float:
    """Concurrency factor. Within the OLS grid (c <= c_cal) the fitted
    log-linear form c**gamma is used, so (c_sat, theta) enter only beyond it."""
    if c <= c_cal or not math.isfinite(c_sat) or not math.isfinite(theta):
        return c ** gamma
    return c ** gamma / (1.0 + (c / c_sat) ** theta)


def c_star(fit: dict, candidates: list[float] | None = None) -> float:
    """Operating concurrency that maximises g(c)."""
    if candidates is None:
        candidates = [1, 2, 4, 8, 16, 32, 64]
    gamma = fit["gamma"]
    c_sat = fit.get("c_sat", float("nan"))
    theta = fit.get("theta", float("nan"))
    return float(max(candidates,
                     key=lambda c: g_of_c(c, gamma, c_sat, theta)))


class Sizer:
    def __init__(self, fit: dict, eps_p: float, kappa: float = 1.0,
                 c_cal: float | None = None):
        if kappa <= 0 or not math.isfinite(kappa):
            raise ValueError(f"kappa must be positive and finite, got {kappa}")
        if fit["beta"] <= 0:
            raise ValueError(
                f"beta must be positive for a finite n_max, got {fit['beta']}")
        self.log_T0 = fit["log_T0"]
        self.gamma = fit["gamma"]
        self.beta = fit["beta"]
        self.sigma = fit["sigma"]
        self.cov = np.array(fit["cov"], dtype=float)
        self.c_sat = fit.get("c_sat", float("nan"))
        self.theta = fit.get("theta", float("nan"))
        self.c_cal = (float(c_cal) if c_cal is not None
                      else float(max(fit.get("calibration_c") or [0.0])))
        self.kappa = float(kappa)
        self.z = stats.norm.ppf(1.0 - eps_p)

    def s(self, n: float, c: float) -> float:
        u = np.array([1.0, math.log(c), -math.log(n)])
        return float(np.sqrt(u @ self.cov @ u + self.sigma ** 2))

    def log_mean_norm(self, n: float, c: float) -> float:
        return (self.log_T0
                + math.log(max(g_of_c(c, self.gamma, self.c_sat, self.theta,
                                      self.c_cal), 1e-300))
                - self.beta * math.log(n))

    def h(self, n: float, c: float, demand: float) -> float:
        """Constraint (P) in the form h(n) >= 0. Strictly decreasing in n."""
        return (math.log(self.kappa) + self.log_mean_norm(n, c)
                - self.z * self.s(n, c) - math.log(demand))

    def lower_bound_tps(self, n: float, c: float) -> float:
        """Absolute (scaled) one-sided lower prediction bound."""
        return float(math.exp(
            math.log(self.kappa) + self.log_mean_norm(n, c)
            - self.z * self.s(n, c)))

    def lower_bound_norm(self, n: float, c: float) -> float:
        """RNM-normalized lower bound (kappa = 1)."""
        return float(math.exp(self.log_mean_norm(n, c) - self.z * self.s(n, c)))

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


def resolve_kappa(sizer_unit: Sizer, c: float, demand: float,
                  scale: str) -> tuple[float, str]:
    """Return (kappa, mode). ``auto`` = minimal scale with h(4)>=0."""
    if scale != "auto":
        return float(scale), "fixed"
    lb = sizer_unit.lower_bound_norm(4, c)
    if lb <= 0 or not math.isfinite(lb):
        raise SystemExit("cannot auto-scale: non-positive RNM lower bound at n=4")
    # Small epsilon so h(4) is strictly positive under floating-point noise.
    return float(demand / lb * (1.0 + 1e-9)), "auto_min_admissible"


def n_min_per_round(round_pd: float, tau: float, faulty_fraction: float,
                    rho: float, w: int, eps_s: float, k_hint: int) -> float:
    """Detection cut from per-round failure probability ``round_pd`` of a
    faulty validator and detector threshold ``tau`` (paper eq. (nmin))."""
    margin = round_pd - tau
    if not (math.isfinite(margin) and margin > 0):
        return float("inf")
    design_effect = 1.0 + max(k_hint - 1, 0) * max(rho, 0.0)
    return (design_effect / faulty_fraction * math.log(1.0 / eps_s)
            / (2.0 * w * margin ** 2))


def ablation(dataset: pd.DataFrame, fit: dict, demand: float, c: float,
             eps_p: float, cost_per_node: float, kappa: float) -> pd.DataFrame:
    """X8: sizing decision and provisioning cost under competing models."""
    d = dataset[(dataset["loss_pct"] == 0) & (dataset["rtt_ms"] == 0)]
    ns = d["n"].to_numpy(float)
    ys = d["tps_norm"].to_numpy(float) * kappa
    rows = []

    def truth(n: float) -> float:
        return kappa * math.exp(
            fit["log_T0"]
            + math.log(max(g_of_c(c, fit["gamma"],
                                  fit.get("c_sat", float("nan")),
                                  fit.get("theta", float("nan")),
                                  float(max(fit.get("calibration_c") or [0.0]))),
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

    record("linear", float(ns.max()))

    slope, intercept, *_ = stats.linregress(np.log(ns), np.log(np.maximum(ys, 1e-300)))
    if slope > 0:
        n_single = math.exp((math.log(demand) - intercept) / slope)
    else:
        n_single = math.exp((intercept - math.log(demand)) / (-slope))
    record("single_factor", n_single)

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

    sizer = Sizer(fit, eps_p, kappa=kappa)
    record("chance_constrained", sizer.n_max(c, demand))
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--out", dest="out", type=Path, required=True)
    ap.add_argument("--demand", type=float, default=2100.0,
                    help="peak demand in absolute transactions per second")
    ap.add_argument("--concurrency", type=float, default=None,
                    help="operating concurrency; default = largest calibrated "
                         "level (no extrapolation in c)")
    ap.add_argument("--eps-p", type=float, default=0.05)
    ap.add_argument("--eps-s", type=float, default=0.01)
    ap.add_argument("--window", type=int, default=30)
    ap.add_argument("--round-pd", type=float, default=None,
                    help="per-round failure probability of a faulty validator; "
                         "enables the detection constraint (needs --round-tau)")
    ap.add_argument("--round-tau", type=float, default=None,
                    help="detector threshold on the per-round failure rate")
    ap.add_argument("--faulty-fraction", type=float, default=0.20)
    ap.add_argument("--cost-per-node", type=float, default=1.0)
    ap.add_argument("--scale", default="auto",
                    help="production scale-up kappa, or 'auto' for the minimal "
                         "kappa that makes n=4 throughput-feasible")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    fit = json.loads((args.inp / "fit.json").read_text(encoding="utf-8"))
    dataset = pd.read_csv(args.inp / "dataset.csv")
    det = fit.get("detector", {})

    c_cal = float(max(fit.get("calibration_c") or [16]))
    c = float(args.concurrency) if args.concurrency is not None else c_cal
    unit = Sizer(fit, args.eps_p, kappa=1.0)
    kappa, kappa_mode = resolve_kappa(unit, c, args.demand, args.scale)
    sizer = Sizer(fit, args.eps_p, kappa=kappa)
    n_max = sizer.n_max(c, args.demand)

    k_hint = max(int(round(args.faulty_fraction * (n_max or 10))), 1)
    rho = det.get("rho", 0.0)
    if rho is None or (isinstance(rho, float) and not math.isfinite(rho)):
        rho = 0.0

    # Detection constraint: evaluated only from PER-ROUND parameters. The X5
    # flag rates (TPR/FPR) do not identify them, so by default it is relaxed.
    detection_enforced = (args.round_pd is not None
                          and args.round_tau is not None)
    n_min_detector = (n_min_per_round(args.round_pd, args.round_tau,
                                      args.faulty_fraction, rho, args.window,
                                      args.eps_s, k_hint)
                      if detection_enforced else None)
    n_min = float(max(4, math.ceil(n_min_detector))
                  if detection_enforced and math.isfinite(n_min_detector)
                  else (float("inf") if detection_enforced else 4))

    # Sensitivity of kappa to the operating concurrency: grid argmax of the
    # fitted g(c), which lies beyond the OLS grid and uses (c_sat, theta).
    c_arg = c_star(fit)
    kappa_arg, _ = resolve_kappa(unit, c_arg, args.demand, "auto")

    # Sensitivity of kappa to curvature in log n: refit on small counts only.
    small_fit = fit.get("small_n_fit")
    kappa_small = None
    if small_fit and small_fit.get("beta", 0) > 0:
        kappa_small, _ = resolve_kappa(
            Sizer(small_fit, args.eps_p, kappa=1.0, c_cal=c_cal),
                                       c, args.demand, "auto")

    feasible = (n_max is not None and math.isfinite(n_min) and n_min <= n_max)
    n_opt = int(n_min) if feasible else None

    result = {
        "demand": args.demand,
        "concurrency": c,
        "kappa": kappa,
        "kappa_mode": kappa_mode,
        "eps_p": args.eps_p,
        "eps_s": args.eps_s,
        "window": args.window,
        "detector_thr": det.get("thr"),
        "faulty_fraction": args.faulty_fraction,
        "detection_enforced": bool(detection_enforced),
        "round_pd": args.round_pd,
        "round_tau": args.round_tau,
        "n_min": n_min,
        "n_min_detector": n_min_detector,
        "concurrency_calib_max": c_cal,
        "concurrency_argmax_g": c_arg,
        "kappa_argmax_g": kappa_arg,
        "kappa_small_n": kappa_small,
        "n_max": n_max,
        "n_opt": n_opt,
        "feasible": bool(feasible),
        "certificate": None if feasible else
        "empty feasibility window: no validator-set size meets both constraints",
        "curve": [
            {"n": n,
             "lower_tps": sizer.lower_bound_tps(n, c),
             "h": sizer.h(n, c, args.demand)}
            for n in range(4, 201)
        ],
    }
    (args.out / "sizing.json").write_text(json.dumps(result, indent=2),
                                          encoding="utf-8")

    abl = ablation(dataset, fit, args.demand, c, args.eps_p,
                   args.cost_per_node, kappa)
    if not abl.empty:
        base = abl.loc[abl["model"] == "chance_constrained", "cost"]
        if len(base) and math.isfinite(base.iloc[0]) and base.iloc[0] > 0:
            abl["relative_cost"] = abl["cost"] / base.iloc[0]
    abl.to_csv(args.out / "sizing_ablation.csv", index=False)

    print(f"kappa={kappa:.4g} ({kappa_mode}) c*={c:g} "
          f"n_min={result['n_min']} n_max={n_max} n_opt={n_opt} "
          f"feasible={feasible}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
