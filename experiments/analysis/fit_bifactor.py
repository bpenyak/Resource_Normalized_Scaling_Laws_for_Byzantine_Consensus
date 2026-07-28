#!/usr/bin/env python3
"""Calibrate the bi-factor scaling law and test the identifiability theorem.

Model (Definition 2 in the paper):

    TPS(n, c) = T0 * g(c) * n^(-beta),      g(c) = c^gamma / (1 + (c/c*)^theta)

In the unsaturated regime the model is log-linear,

    log TPS = log T0 + gamma * log c - beta * log n,

so ``T0``, ``gamma`` and ``beta`` come from ordinary least squares; ``c*`` and
``theta`` are then fitted by nonlinear least squares on the full concurrency
sweep with the linear coefficients held fixed.

Also performed here:
  * the q-invariance ANCOVA of Statement 1 (experiment X2);
  * the empirical check of Theorem 1 by re-sampling the factorial grid along
    artificial concurrency paths log c = lambda * log n + mu (experiment X3b);
  * a comparison against the linear, single-factor, Amdahl and USL models.

Outputs (into --out): fit.json, dataset.csv, qinvariance.json,
confounding.csv, model_comparison.csv.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import curve_fit


# --------------------------------------------------------------------------- #
# loading
# --------------------------------------------------------------------------- #

def load_records(raw_dir: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(raw_dir.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        if rec.get("status") != "ok":
            continue
        rows.append({
            "file": path.name,
            "experiment": rec.get("experiment"),
            "n": rec["n"],
            "quota": rec["quota"],
            "c": rec["concurrency"],
            "replicate": rec.get("replicate", 0),
            "rtt_ms": rec.get("rtt_ms", 0),
            "loss_pct": rec.get("loss_pct", 0.0),
            "faulty_nodes": rec.get("faulty_nodes", 0),
            "tps": rec["tps"],
            "tps_norm": rec["tps_normalized"],
            "blocks": rec.get("load", {}).get("blocks"),
            "block_interval_mean": rec.get("load", {}).get("block_interval_mean"),
            "p_d": rec.get("detector", {}).get("p_d"),
            "p_f": rec.get("detector", {}).get("p_f"),
            "rho": rec.get("detector", {}).get("rho"),
        })
    if not rows:
        raise SystemExit(f"no successful records found in {raw_dir}")
    df = pd.DataFrame(rows)
    df = df[df["tps_norm"] > 0].copy()
    df["log_n"] = np.log(df["n"])
    df["log_c"] = np.log(df["c"])
    df["log_tps"] = np.log(df["tps_norm"])
    return df


# --------------------------------------------------------------------------- #
# OLS in log space
# --------------------------------------------------------------------------- #

def ols_logspace(df: pd.DataFrame) -> dict:
    """Fit log TPS = a + gamma*log c - beta*log n. Returns coefficients + cov."""
    X = np.column_stack([np.ones(len(df)), df["log_c"].to_numpy(),
                         -df["log_n"].to_numpy()])
    y = df["log_tps"].to_numpy()
    if len(df) <= X.shape[1]:
        raise SystemExit("not enough observations to fit three coefficients")

    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = len(y) - X.shape[1]
    sigma2 = float(resid @ resid / dof)
    xtx_inv = np.linalg.inv(X.T @ X)
    cov = sigma2 * xtx_inv
    se = np.sqrt(np.diag(cov))
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float(resid @ resid) / ss_tot if ss_tot > 0 else float("nan")

    return {
        "log_T0": float(coef[0]), "gamma": float(coef[1]), "beta": float(coef[2]),
        "se_log_T0": float(se[0]), "se_gamma": float(se[1]), "se_beta": float(se[2]),
        "sigma": float(np.sqrt(sigma2)),
        "cov": cov.tolist(),
        "r2": r2,
        "n_obs": int(len(y)),
        "dof": int(dof),
    }


def unsaturated_subset(df: pd.DataFrame) -> pd.DataFrame:
    """Keep concurrency levels below the empirical throughput knee."""
    by_c = df.groupby("c")["tps_norm"].median().sort_index()
    if len(by_c) < 3:
        return df
    peak_c = by_c.idxmax()
    return df[df["c"] <= peak_c].copy()


def fit_saturation(df: pd.DataFrame, log_T0: float, gamma: float,
                   beta: float) -> dict:
    """Fit c* and theta with the linear coefficients held fixed."""
    sweep = df[df.groupby("n")["c"].transform("nunique") > 3]
    if sweep.empty:
        sweep = df
    if sweep["c"].nunique() < 4:
        return {"c_sat": float("nan"), "theta": float("nan"),
                "se_c_sat": float("nan"), "se_theta": float("nan"),
                "note": "insufficient concurrency levels"}

    c = sweep["c"].to_numpy(dtype=float)
    n = sweep["n"].to_numpy(dtype=float)
    y = sweep["tps_norm"].to_numpy(dtype=float)

    def model(_x, c_sat, theta):
        g = c ** gamma / (1.0 + (c / c_sat) ** theta)
        return np.exp(log_T0) * g * n ** (-beta)

    p0 = [max(float(np.median(c)), 1.0), max(gamma + 0.5, 1.0)]
    try:
        popt, pcov = curve_fit(model, np.zeros_like(y), y, p0=p0,
                               bounds=([1e-3, gamma + 1e-3], [1e6, 50.0]),
                               maxfev=20000)
        se = np.sqrt(np.diag(pcov))
        return {"c_sat": float(popt[0]), "theta": float(popt[1]),
                "se_c_sat": float(se[0]), "se_theta": float(se[1])}
    except Exception as exc:  # noqa: BLE001
        return {"c_sat": float("nan"), "theta": float("nan"),
                "se_c_sat": float("nan"), "se_theta": float("nan"),
                "note": f"nls failed: {exc}"}


# --------------------------------------------------------------------------- #
# X2: q-invariance
# --------------------------------------------------------------------------- #

def q_invariance(df: pd.DataFrame) -> dict:
    """ANCOVA partial F-test of H0: the slope in log n does not depend on q."""
    sub = df[df["quota"].notna()].copy()
    quotas = sorted(sub["quota"].unique())
    if len(quotas) < 2:
        return {"p_value": float("nan"), "note": "single quota level",
                "beta_by_quota": {}}

    beta_by_q = {}
    for q in quotas:
        d = sub[sub["quota"] == q]
        if d["n"].nunique() >= 2:
            slope, _, _, _, stderr = stats.linregress(d["log_n"], d["log_tps"])
            beta_by_q[str(q)] = {"beta": float(-slope), "se": float(stderr)}

    y = sub["log_tps"].to_numpy()
    base = np.column_stack([np.ones(len(sub)), sub["log_n"].to_numpy()])
    inter = [base]
    for q in quotas[1:]:
        inter.append(((sub["quota"] == q).to_numpy().astype(float)
                      * sub["log_n"].to_numpy()).reshape(-1, 1))
        inter.append((sub["quota"] == q).to_numpy().astype(float).reshape(-1, 1))
    full = np.hstack(inter)

    def rss(X):
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        r = y - X @ coef
        return float(r @ r)

    rss_r, rss_f = rss(base), rss(full)
    df1 = full.shape[1] - base.shape[1]
    df2 = len(y) - full.shape[1]
    if df1 <= 0 or df2 <= 0 or rss_f <= 0:
        return {"p_value": float("nan"), "note": "degenerate design",
                "beta_by_quota": beta_by_q}

    f_stat = ((rss_r - rss_f) / df1) / (rss_f / df2)
    p = float(1.0 - stats.f.cdf(f_stat, df1, df2))
    return {"f_stat": float(f_stat), "df1": int(df1), "df2": int(df2),
            "p_value": p, "beta_by_quota": beta_by_q}


# --------------------------------------------------------------------------- #
# X3b: empirical check of Theorem 1
# --------------------------------------------------------------------------- #

def confounding_check(df: pd.DataFrame, gamma: float, beta: float,
                      lambdas=(0.0, 0.25, 0.5, 0.75, 1.0, 1.5)) -> pd.DataFrame:
    """Re-sample along log c = lambda*log n + mu and fit the single-factor model.

    Theorem 1 predicts that the fitted exponent converges to gamma*lambda - beta.
    """
    rows = []
    ns = np.array(sorted(df["n"].unique()), dtype=float)
    cs = np.array(sorted(df["c"].unique()), dtype=float)
    if len(ns) < 3 or len(cs) < 2:
        return pd.DataFrame(rows)

    for lam in lambdas:
        picked = []
        for n in ns:
            target = lam * np.log(n)                     # mu absorbed by scaling
            c_star = cs[np.argmin(np.abs(np.log(cs) - (target + np.log(cs[0]))))]
            d = df[(df["n"] == n) & (df["c"] == c_star)]
            if not d.empty:
                picked.append(d)
        if len(picked) < 3:
            continue
        sel = pd.concat(picked)
        if sel["n"].nunique() < 3:
            continue
        slope, _, r_value, _, stderr = stats.linregress(sel["log_n"],
                                                        sel["log_tps"])
        rows.append({
            "lambda": lam,
            "alpha_hat": float(slope),
            "alpha_se": float(stderr),
            "alpha_predicted": float(gamma * lam - beta),
            "r2": float(r_value ** 2),
            "points": int(len(sel)),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# model comparison
# --------------------------------------------------------------------------- #

def compare_models(df: pd.DataFrame, holdout_n: list[int]) -> pd.DataFrame:
    """Out-of-sample log-RMSE for competing scaling models."""
    train = df[~df["n"].isin(holdout_n)]
    test = df[df["n"].isin(holdout_n)]
    if train.empty or test.empty:
        return pd.DataFrame([])

    ntr, ytr = train["n"].to_numpy(float), train["tps_norm"].to_numpy(float)
    nte, yte = test["n"].to_numpy(float), test["tps_norm"].to_numpy(float)
    out = []

    def score(name, params, pred):
        err = np.log(pred) - np.log(yte)
        out.append({"model": name, "params": params,
                    "holdout_log_rmse": float(np.sqrt(np.mean(err ** 2)))})

    # Linear: throughput independent of n.
    score("linear", 1, np.full_like(nte, ytr.mean()))

    # Single factor TPS = T0 * n^alpha (the model of the first prior paper).
    slope, intercept, *_ = stats.linregress(np.log(ntr), np.log(ytr))
    score("single_factor", 2, np.exp(intercept + slope * np.log(nte)))

    # Amdahl: C(n) = n / (1 + s(n-1)); throughput per unit work.
    try:
        popt, _ = curve_fit(lambda n, T, s: T * n / (1 + s * (n - 1)),
                            ntr, ytr, p0=[ytr.mean(), 0.5],
                            bounds=([1e-9, 0], [np.inf, 1]), maxfev=20000)
        score("amdahl", 2, popt[0] * nte / (1 + popt[1] * (nte - 1)))
    except Exception:  # noqa: BLE001
        out.append({"model": "amdahl", "params": 2,
                    "holdout_log_rmse": float("nan")})

    # USL: C(n) = n / (1 + s(n-1) + k n(n-1)).
    try:
        popt, _ = curve_fit(
            lambda n, T, s, k: T * n / (1 + s * (n - 1) + k * n * (n - 1)),
            ntr, ytr, p0=[ytr.mean(), 0.1, 0.01],
            bounds=([1e-9, 0, 0], [np.inf, 1, 1]), maxfev=20000)
        score("usl", 3, popt[0] * nte /
              (1 + popt[1] * (nte - 1) + popt[2] * nte * (nte - 1)))
    except Exception:  # noqa: BLE001
        out.append({"model": "usl", "params": 3,
                    "holdout_log_rmse": float("nan")})

    # Bi-factor (this work), calibrated on the training subset only.
    fit = ols_logspace(train)
    pred = np.exp(fit["log_T0"] + fit["gamma"] * test["log_c"].to_numpy()
                  - fit["beta"] * np.log(nte))
    score("bifactor", 5, pred)

    return pd.DataFrame(out)


# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--out", dest="out", type=Path, required=True)
    ap.add_argument("--holdout-n", default="13,16",
                    help="validator counts held out of calibration")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    df = load_records(args.inp)
    df.to_csv(args.out / "dataset.csv", index=False)

    clean = df[(df["loss_pct"] == 0) & (df["rtt_ms"] == 0)]
    core = unsaturated_subset(clean)
    fit = ols_logspace(core)
    fit.update(fit_saturation(clean, fit["log_T0"], fit["gamma"], fit["beta"]))
    fit["T0"] = float(np.exp(fit["log_T0"]))
    fit["n_max_measured"] = int(df["n"].max())
    fit["total_runs"] = int(len(df))

    # beta as a function of emulated round-trip latency (experiment X4).
    beta_by_rtt = {}
    for rtt, d in df.groupby("rtt_ms"):
        if d["n"].nunique() >= 2:
            slope, *_ = stats.linregress(d["log_n"], d["log_tps"])
            beta_by_rtt[str(int(rtt))] = float(-slope)
    fit["beta_by_rtt"] = beta_by_rtt

    # Detector characteristics, pooled over fault-injection runs (experiment X5).
    faulty_runs = df[df["p_d"].notna()]
    fit["detector"] = {
        "p_d": float(faulty_runs["p_d"].mean()) if len(faulty_runs) else float("nan"),
        "p_f": float(faulty_runs["p_f"].mean()) if len(faulty_runs) else float("nan"),
        "rho": float(faulty_runs["rho"].mean()) if len(faulty_runs) else float("nan"),
        "runs": int(len(faulty_runs)),
    }

    (args.out / "fit.json").write_text(json.dumps(fit, indent=2),
                                       encoding="utf-8")
    (args.out / "qinvariance.json").write_text(
        json.dumps(q_invariance(clean), indent=2), encoding="utf-8")

    conf = confounding_check(clean, fit["gamma"], fit["beta"])
    conf.to_csv(args.out / "confounding.csv", index=False)

    holdout = [int(x) for x in args.holdout_n.split(",") if x.strip()]
    compare_models(clean, holdout).to_csv(args.out / "model_comparison.csv",
                                          index=False)

    print(f"beta={fit['beta']:.4f} (se {fit['se_beta']:.4f})  "
          f"gamma={fit['gamma']:.4f} (se {fit['se_gamma']:.4f})  "
          f"R2={fit['r2']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
