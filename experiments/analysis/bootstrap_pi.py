#!/usr/bin/env python3
"""Prediction intervals and empirical coverage (experiment X7).

Two constructions, deliberately both:

  * delta method -- the lognormal interval of Statement 2, with
    s^2 = u' Sigma u + sigma^2 separating estimation variance from residual
    variance;
  * residual bootstrap -- distribution free, no Gaussianity assumption.

Agreement between the two is evidence that the Gaussian approximation holds.

Validation is by **coverage**, not by average percentage error: the model is
calibrated on n <= n_cal only, intervals are constructed for held-out validator
counts, and we report the fraction of held-out observations that fall inside.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def design(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    X = np.column_stack([np.ones(len(df)), df["log_c"].to_numpy(),
                         -df["log_n"].to_numpy()])
    return X, df["log_tps"].to_numpy()


def fit(df: pd.DataFrame) -> dict:
    X, y = design(df)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = max(len(y) - X.shape[1], 1)
    sigma2 = float(resid @ resid / dof)
    cov = sigma2 * np.linalg.inv(X.T @ X)
    return {"coef": coef, "cov": cov, "sigma": float(np.sqrt(sigma2)),
            "resid": resid, "X": X, "y": y}


def delta_interval(model: dict, log_c: float, log_n: float,
                   level: float) -> tuple[float, float, float]:
    u = np.array([1.0, log_c, -log_n])
    mean = float(u @ model["coef"])
    s = float(np.sqrt(u @ model["cov"] @ u + model["sigma"] ** 2))
    z = stats.norm.ppf(0.5 + level / 2.0)
    return np.exp(mean - z * s), np.exp(mean + z * s), s


def bootstrap_interval(model: dict, log_c: float, log_n: float, level: float,
                       n_boot: int, rng: np.random.Generator) -> tuple[float, float]:
    X, y = model["X"], model["y"]
    centred = model["resid"] - model["resid"].mean()
    u = np.array([1.0, log_c, -log_n])
    draws = np.empty(n_boot)
    fitted = X @ model["coef"]
    for b in range(n_boot):
        y_star = fitted + rng.choice(centred, size=len(y), replace=True)
        coef_b, *_ = np.linalg.lstsq(X, y_star, rcond=None)
        draws[b] = u @ coef_b + rng.choice(centred)
    lo = float(np.exp(np.quantile(draws, (1 - level) / 2)))
    hi = float(np.exp(np.quantile(draws, 1 - (1 - level) / 2)))
    return lo, hi


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--out", dest="out", type=Path, required=True)
    ap.add_argument("--calibrate-max-n", type=int, default=9,
                    help="calibrate on n <= this value")
    ap.add_argument("--levels", default="0.90,0.95")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=20260101)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.inp / "dataset.csv")
    df = df[(df["loss_pct"] == 0) & (df["rtt_ms"] == 0)]
    train = df[df["n"] <= args.calibrate_max_n]
    test = df[df["n"] > args.calibrate_max_n]

    if len(train) < 5 or test.empty:
        raise SystemExit("need at least 5 calibration runs and one held-out run")

    model = fit(train)
    rng = np.random.default_rng(args.seed)
    levels = [float(x) for x in args.levels.split(",")]

    rows = []
    for level in levels:
        hits_delta = hits_boot = 0
        for _, r in test.iterrows():
            lo, hi, _ = delta_interval(model, r["log_c"], r["log_n"], level)
            blo, bhi = bootstrap_interval(model, r["log_c"], r["log_n"], level,
                                          args.n_boot, rng)
            hits_delta += int(lo <= r["tps_norm"] <= hi)
            hits_boot += int(blo <= r["tps_norm"] <= bhi)
            rows.append({
                "level": level, "n": r["n"], "c": r["c"],
                "observed": r["tps_norm"],
                "delta_lo": lo, "delta_hi": hi,
                "boot_lo": blo, "boot_hi": bhi,
                "in_delta": int(lo <= r["tps_norm"] <= hi),
                "in_boot": int(blo <= r["tps_norm"] <= bhi),
            })
        print(f"level={level}: delta coverage="
              f"{hits_delta / len(test):.3f}, bootstrap coverage="
              f"{hits_boot / len(test):.3f}")

    detail = pd.DataFrame(rows)
    detail.to_csv(args.out / "coverage_detail.csv", index=False)

    summary = {
        "calibrate_max_n": args.calibrate_max_n,
        "holdout_n": sorted(int(x) for x in test["n"].unique()),
        "holdout_runs": int(len(test)),
        "coverage": {
            str(level): {
                "delta": float(detail[detail["level"] == level]["in_delta"].mean()),
                "bootstrap": float(detail[detail["level"] == level]["in_boot"].mean()),
            } for level in levels
        },
        "coef": {"log_T0": float(model["coef"][0]),
                 "gamma": float(model["coef"][1]),
                 "beta": float(model["coef"][2])},
        "sigma": model["sigma"],
    }
    (args.out / "coverage.json").write_text(json.dumps(summary, indent=2),
                                            encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
