#!/usr/bin/env python3
"""Generate the paper's figures as vector PDFs.

Produces:
  fig_bifactor.pdf     -- normalized throughput vs n and vs c
  fig_confounding.pdf  -- measured alpha vs the concurrency-path slope lambda,
                          against the theoretical line gamma*lambda - beta
  fig_roc.pdf          -- receiver operating characteristic of the detector
  fig_window.pdf       -- the feasibility window [n_min, n_max]
  fig_sensitivity.pdf  -- window width vs correlation and latency

Only fig_confounding, fig_roc and fig_window are required by the page budget;
the other two are produced for the supplementary material.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

plt.rcParams.update({
    "font.size": 9,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "figure.dpi": 150,
    "savefig.bbox": "tight",
})


def fig_bifactor(proc: Path, out: Path) -> None:
    df = pd.read_csv(proc / "dataset.csv")
    df = df[(df["loss_pct"] == 0) & (df["rtt_ms"] == 0)]
    fit = json.loads((proc / "fit.json").read_text(encoding="utf-8"))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.8))

    c_ref = df["c"].mode().iloc[0]
    d1 = df[df["c"] == c_ref].groupby("n")["tps_norm"].median()
    ax1.loglog(d1.index, d1.values, "o", label="measured")
    ns = np.linspace(d1.index.min(), d1.index.max(), 100)
    ax1.loglog(ns, np.exp(fit["log_T0"] + fit["gamma"] * math.log(c_ref))
               * ns ** (-fit["beta"]), "-",
               label=rf"fit, $\beta={fit['beta']:.2f}$")
    ax1.set_xlabel("validators $n$")
    ax1.set_ylabel(r"normalized throughput $\widetilde{TPS}$")
    ax1.legend(frameon=False)

    n_ref = df["n"].mode().iloc[0]
    d2 = df[df["n"] == n_ref].groupby("c")["tps_norm"].median()
    ax2.loglog(d2.index, d2.values, "s", color="C1", label="measured")
    if math.isfinite(fit.get("c_sat", float("nan"))):
        ax2.axvline(fit["c_sat"], ls="--", color="gray",
                    label=rf"$c^*={fit['c_sat']:.1f}$")
    ax2.set_xlabel("senders $c$")
    ax2.set_ylabel(r"$\widetilde{TPS}$")
    ax2.legend(frameon=False)

    fig.savefig(out / "fig_bifactor.pdf")
    plt.close(fig)


def fig_confounding(proc: Path, out: Path) -> None:
    path = proc / "confounding.csv"
    if not path.exists():
        return
    df = pd.read_csv(path)
    if df.empty:
        return
    fit = json.loads((proc / "fit.json").read_text(encoding="utf-8"))

    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    ax.errorbar(df["lambda"], df["alpha_hat"], yerr=df["alpha_se"],
                fmt="o", capsize=3, label=r"measured $\hat\alpha$")
    lam = np.linspace(df["lambda"].min(), df["lambda"].max(), 100)
    ax.plot(lam, fit["gamma"] * lam - fit["beta"], "-",
            label=r"theory $\gamma\lambda-\beta$")
    ax.axhline(0, color="k", lw=0.8)
    ax.axvline(fit["beta"] / fit["gamma"], ls=":", color="gray",
               label=r"sign change $\lambda=\beta/\gamma$")
    ax.set_xlabel(r"concurrency-path slope $\lambda$")
    ax.set_ylabel(r"single-factor exponent $\hat\alpha$")
    ax.legend(frameon=False, fontsize=8)
    fig.savefig(out / "fig_confounding.pdf")
    plt.close(fig)


def fig_roc(raw: Path, out: Path) -> None:
    points: list[dict] = []
    for path in sorted(raw.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        det = rec.get("detector")
        if not det or not det.get("roc"):
            continue
        for p in det["roc"]:
            points.append({"loss_pct": rec.get("loss_pct", 0), **p})
    if not points:
        return
    df = pd.DataFrame(points)

    fig, ax = plt.subplots(figsize=(3.6, 3.2))
    for loss, d in df.groupby("loss_pct"):
        d = d.groupby("tau")[["p_f", "p_d"]].mean().sort_values("p_f")
        ax.plot(d["p_f"], d["p_d"], "o-", ms=3, label=rf"$\ell={loss:g}\%$")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8, label="chance")
    ax.set_xlabel(r"false-positive rate $p_f$")
    ax.set_ylabel(r"detection probability $p_d$")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.savefig(out / "fig_roc.pdf")
    plt.close(fig)


def fig_window(proc: Path, out: Path) -> None:
    path = proc / "sizing.json"
    if not path.exists():
        return
    s = json.loads(path.read_text(encoding="utf-8"))
    curve = pd.DataFrame(s["curve"])
    fit_path = proc / "fit.json"
    n_cal = None
    if fit_path.exists():
        fit = json.loads(fit_path.read_text(encoding="utf-8"))
        n_cal = fit.get("n_max_measured")

    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    ax.semilogy(curve["n"], curve["lower_tps"], "-",
                label=r"$\underline{TPS}_{1-\varepsilon_p}(n)$")
    ax.axhline(s["demand"], color="C3", ls="--",
               label=rf"demand $D_{{peak}}={s['demand']:g}$")
    if s["n_max"]:
        ax.axvline(s["n_max"], color="C2", ls=":", label=rf"$n_{{max}}={s['n_max']}$")
    if math.isfinite(s["n_min"]):
        ax.axvline(s["n_min"], color="C4", ls=":",
                   label=rf"$n_{{min}}={s['n_min']:.0f}$")
        if s["n_max"] and s["n_min"] <= s["n_max"]:
            ax.axvspan(s["n_min"], s["n_max"], color="C0", alpha=0.12)
    if n_cal is not None:
        ax.axvline(n_cal, color="0.35", ls="-.", lw=1.2,
                   label=rf"calibration limit $n={n_cal}$")
        xmax = float(curve["n"].max())
        if n_cal < xmax:
            ymin, ymax = ax.get_ylim()
            ax.axvspan(n_cal, xmax, color="0.5", alpha=0.06, zorder=0)
            ax.text(0.5 * (n_cal + xmax), ymin * (ymax / ymin) ** 0.08,
                    "extrapolation", ha="center", va="bottom",
                    fontsize=7, color="0.35")
    ax.set_xlabel("validators $n$")
    ax.set_ylabel("throughput (tx/s)")
    ax.legend(frameon=False, fontsize=7)
    fig.savefig(out / "fig_window.pdf")
    plt.close(fig)


def fig_sensitivity(proc: Path, out: Path) -> None:
    path = proc / "sizing.json"
    if not path.exists():
        return
    s = json.loads(path.read_text(encoding="utf-8"))
    fit = json.loads((proc / "fit.json").read_text(encoding="utf-8"))
    if not s["n_max"] or not math.isfinite(s["n_min"]) or s["eps_0"] <= 0:
        return

    rhos = np.linspace(0.0, 0.9, 50)
    k = max(int(round(s["faulty_fraction"] * s["n_max"])), 1)
    n_min_rho = ((1 + (k - 1) * rhos) * math.log(1 / s["eps_s"])
                 / (2 * s["window"] * s["eps_0"] ** 2))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.6))
    ax1.plot(rhos, s["n_max"] - n_min_rho)
    ax1.axhline(0, color="k", lw=0.8)
    ax1.set_xlabel(r"fault correlation $\rho$")
    ax1.set_ylabel(r"window width $n_{max}-n_{min}$")

    by_rtt = fit.get("beta_by_rtt", {})
    if by_rtt:
        rtts = sorted(int(k_) for k_ in by_rtt)
        ax2.plot(rtts, [by_rtt[str(r)] for r in rtts], "o-")
        ax2.set_xlabel("added round-trip time (ms)")
        ax2.set_ylabel(r"consensus exponent $\beta$")
    else:
        ax2.set_visible(False)

    fig.savefig(out / "fig_sensitivity.pdf")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--raw", type=Path, default=Path("data/raw"))
    ap.add_argument("--out", dest="out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    for name, fn, arg in (
        ("fig_bifactor", fig_bifactor, args.inp),
        ("fig_confounding", fig_confounding, args.inp),
        ("fig_roc", fig_roc, args.raw),
        ("fig_window", fig_window, args.inp),
        ("fig_sensitivity", fig_sensitivity, args.inp),
    ):
        try:
            fn(arg, args.out)
            print(f"wrote {name}")
        except Exception as exc:  # noqa: BLE001
            print(f"skipped {name}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
