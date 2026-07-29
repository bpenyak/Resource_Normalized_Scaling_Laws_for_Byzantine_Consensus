#!/usr/bin/env python3
"""Emit ``numbers.tex`` from the analysis outputs.

Every numeric value quoted in the manuscript flows through this file. Nothing is
transcribed by hand, and any value the pipeline could not produce is written as
a visible ``\\TODO`` marker so that it cannot silently reach the submitted PDF.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

HEADER = r"""%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%% numbers.tex -- AUTO-GENERATED. DO NOT EDIT BY HAND.
%%
%% Regenerate with:
%%     python experiments/analysis/emit_numbers_tex.py \
%%            --in data/processed --out numbers.tex
%%
%% Any macro that still expands to a \TODO marker means the corresponding
%% quantity was not produced by the analysis pipeline.
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
"""


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def load_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


class Emitter:
    def __init__(self) -> None:
        self.lines: list[str] = [HEADER]
        self.missing: list[str] = []

    def section(self, title: str) -> None:
        self.lines.append("")
        self.lines.append(f"%--- {title} " + "-" * max(0, 76 - len(title)))

    def num(self, macro: str, value, fmt: str = "{:.3f}",
            todo: str | None = None) -> None:
        if value is None or (isinstance(value, float) and not math.isfinite(value)):
            self.missing.append(macro)
            body = rf"\TODO{{{todo or macro}}}"
        else:
            body = fmt.format(value)
        self.lines.append(rf"\newcommand{{\{macro}}}{{{body}}}")

    def raw(self, macro: str, text: str | None, todo: str | None = None) -> None:
        if not text:
            self.missing.append(macro)
            text = rf"\TODO{{{todo or macro}}}"
        self.lines.append(rf"\newcommand{{\{macro}}}{{{text}}}")

    def render(self) -> str:
        return "\n".join(self.lines) + "\n"


def pct(x: float | None) -> float | None:
    return None if x is None else 100.0 * x


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--out", dest="out", type=Path, required=True)
    ap.add_argument("--core-hours", type=float, default=None,
                    help="measured CI core-hours; omit to leave a TODO")
    args = ap.parse_args()

    fit = load_json(args.inp / "fit.json")
    qinv = load_json(args.inp / "qinvariance.json")
    cov = load_json(args.inp / "coverage.json")
    sizing = load_json(args.inp / "sizing.json")
    conf = load_csv(args.inp / "confounding.csv")
    abl = load_csv(args.inp / "sizing_ablation.csv")
    cmp = load_csv(args.inp / "model_comparison.csv")

    e = Emitter()

    # -- bi-factor calibration -------------------------------------------------
    e.section("bi-factor calibration (X1, X3)")
    e.num("resBeta", fit.get("beta"), todo="beta")
    e.num("resBetaSE", fit.get("se_beta"), todo="se(beta)")
    e.num("resGamma", fit.get("gamma"), todo="gamma")
    e.num("resGammaSE", fit.get("se_gamma"), todo="se(gamma)")
    e.num("resCsat", fit.get("c_sat"), "{:.1f}", todo="c*")
    e.num("resTheta", fit.get("theta"), todo="theta")
    e.num("resTzero", fit.get("T0"), "{:.1f}", todo="T0")
    e.num("resRsq", fit.get("r2"), todo="R2")
    e.num("resSigmaRes", fit.get("sigma"), todo="sigma")

    # -- confounding check (Theorem 1) ----------------------------------------
    e.section("confounding check (Theorem 1)")
    beta = fit.get("beta")
    gamma = fit.get("gamma")
    if (isinstance(beta, (int, float)) and isinstance(gamma, (int, float))
            and math.isfinite(beta) and math.isfinite(gamma) and gamma > 0):
        e.num("resLambda", beta / gamma, "{:.2f}")  # predicted sign-change
    else:
        e.num("resLambda", None, todo="beta/gamma")
    if not conf.empty:
        # Prefer the lambda=1 path (load scaled with n): the classical confound.
        row1 = conf.loc[(conf["lambda"] - 1.0).abs().idxmin()]
        e.num("resAlphaHat", float(row1["alpha_hat"]))
        e.num("resAlphaPred", float(row1["alpha_predicted"]))
        for lam, macro in ((0.0, "resAlphaHatLzero"), (1.0, "resAlphaHatLone"),
                           (2.0, "resAlphaHatLtwo")):
            hit = conf.loc[(conf["lambda"] - lam).abs() < 1e-9]
            e.num(macro,
                  float(hit.iloc[0]["alpha_hat"]) if len(hit) else None,
                  todo=f"alpha(lambda={lam:g})")
    else:
        e.num("resAlphaHat", None, todo="alpha-hat")
        e.num("resAlphaPred", None, todo="gamma*lambda-beta")
        e.num("resAlphaHatLzero", None, todo="alpha(lambda=0)")
        e.num("resAlphaHatLone", None, todo="alpha(lambda=1)")
        e.num("resAlphaHatLtwo", None, todo="alpha(lambda=2)")

    # Model-comparison holdout log-RMSE (X8 ablation costs are separate).
    e.section("model comparison holdout log-RMSE")
    def rmse(model: str):
        if cmp.empty or "holdout_log_rmse" not in cmp.columns:
            return None
        sel = cmp[cmp["model"] == model]["holdout_log_rmse"]
        return float(sel.iloc[0]) if len(sel) and math.isfinite(sel.iloc[0]) else None
    e.num("resRmseLinear", rmse("linear"), todo="rmse-linear")
    e.num("resRmseSingle", rmse("single_factor"), todo="rmse-single")
    e.num("resRmseUsl", rmse("usl"), todo="rmse-usl")
    e.num("resRmseOurs", rmse("bifactor"), todo="rmse-bifactor")

    # -- q-invariance ----------------------------------------------------------
    e.section("q-invariance (X2)")
    by_q = qinv.get("beta_by_quota", {}) or {}

    def beta_at(q: str):
        for key, val in by_q.items():
            if abs(float(key) - float(q)) < 1e-9:
                return val.get("beta")
        return None

    e.num("resBetaQlow", beta_at("0.20"), todo="beta(q=0.20)")
    e.num("resBetaQmid", beta_at("0.25"), todo="beta(q=0.25)")
    e.num("resBetaQhigh", beta_at("0.33"), todo="beta(q=0.33)")
    e.num("resQinvP", qinv.get("p_value"), todo="p-value")

    # -- latency ---------------------------------------------------------------
    e.section("WAN degradation (X4)")
    by_rtt = fit.get("beta_by_rtt", {}) or {}
    e.num("resBetaRttZero", by_rtt.get("0"), todo="beta(0ms)")
    e.num("resBetaRttHigh", by_rtt.get("200"), todo="beta(200ms)")

    # -- detector --------------------------------------------------------------
    e.section("detector characterisation (X5)")
    det = fit.get("detector", {}) or {}
    e.num("resPd", det.get("p_d"), todo="p_d")
    e.num("resPf", det.get("p_f"), todo="p_f")
    e.num("resRho", det.get("rho"), todo="rho")
    e.num("resAuc", det.get("auc"), todo="AUC")

    # -- coverage --------------------------------------------------------------
    e.section("prediction-interval coverage (X7)")
    cov_map = cov.get("coverage", {}) or {}
    c90 = (cov_map.get("0.9") or cov_map.get("0.90") or {}).get("delta")
    c95 = (cov_map.get("0.95") or {}).get("delta")
    e.num("resCovNinety", pct(c90), "{:.1f}\\,\\%", todo="cov90")
    e.num("resCovNinetyFive", pct(c95), "{:.1f}\\,\\%", todo="cov95")
    holdout = cov.get("holdout_n")
    # No $...$: callers wrap as $\resHoldoutN$ (and \n is a letter macro).
    e.raw("resHoldoutN",
          "n \\in \\{" + ", ".join(str(x) for x in holdout) + "\\}"
          if holdout else None,
          todo="n_holdout")

    # -- sizing ----------------------------------------------------------------
    e.section("sizing ablation (X8)")
    e.num("resKappa", sizing.get("kappa"), "{:.2f}", todo="kappa")
    e.raw("resKappaMode", sizing.get("kappa_mode"), todo="kappa_mode")
    e.num("resCstar", sizing.get("concurrency"), "{:.0f}", todo="c*")
    e.num("resNminCase", sizing.get("n_min"), "{:.0f}", todo="n_min")
    e.num("resNmaxCase", sizing.get("n_max"), "{:.0f}", todo="n_max")
    e.num("resNoptCase", sizing.get("n_opt"), "{:.0f}", todo="n*")
    e.num("resDetectorThr", (fit.get("detector") or {}).get("thr"),
          "{:.2f}", todo="detector-thr")

    def rel_cost(model: str):
        if abl.empty or "relative_cost" not in abl.columns:
            return None
        sel = abl[abl["model"] == model]["relative_cost"]
        return float(sel.iloc[0]) if len(sel) and math.isfinite(sel.iloc[0]) else None

    e.num("resCostLinear", rel_cost("linear"), "{:.2f}", todo="cost-linear")
    e.num("resCostSingle", rel_cost("single_factor"), "{:.2f}",
          todo="cost-single-factor")
    e.num("resCostUsl", rel_cost("usl"), "{:.2f}", todo="cost-usl")
    e.num("resCostOurs", rel_cost("chance_constrained"), "{:.2f}",
          todo="cost-ours")

    # -- metadata --------------------------------------------------------------
    e.section("campaign metadata")
    e.num("resNmaxMeasured", fit.get("n_max_measured"), "{:.0f}",
          todo="n_max measured")
    e.num("resTotalRuns", fit.get("total_runs"), "{:.0f}", todo="runs")
    e.num("resCoreHours", args.core_hours, "{:.1f}", todo="core-hours")

    args.out.write_text(e.render(), encoding="utf-8")
    if e.missing:
        print(f"WARNING: {len(e.missing)} value(s) still unresolved: "
              + ", ".join(e.missing))
    else:
        print(f"wrote {args.out} with all values resolved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
