#!/usr/bin/env python3
"""Participation detector built on Besu's ``qbft_getSignerMetrics``.

Rationale. Besu's devp2p/RLPx transport is encrypted, so consensus messages
cannot be observed or filtered selectively without patching the client. We
therefore detect faulty validators from an *externally visible* signal: the
number of blocks each validator proposed over a window of block heights, which
``qbft_getSignerMetrics`` reports directly.

Under QBFT the proposer rotates round-robin, so over a window of ``w`` blocks
each of the ``n`` validators is expected to propose roughly ``w / n`` blocks. A
validator whose share falls below ``tau`` times its expected share is flagged.

Because the set of degraded containers is known by construction, each run
produces ground-truth labels, from which the detection probability ``p_d``, the
false-positive rate ``p_f``, the exchangeable correlation ``rho`` and a full ROC
curve are estimated.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests


def rpc(url: str, method: str, params: list, rid: int = 1):
    r = requests.post(url, json={"jsonrpc": "2.0", "id": rid,
                                 "method": method, "params": params}, timeout=15)
    r.raise_for_status()
    body = r.json()
    if "error" in body:
        raise RuntimeError(body["error"])
    return body["result"]


def signer_metrics(url: str, lo: int, hi: int) -> dict[str, int]:
    """Map lower-case validator address -> proposedBlockCount over [lo, hi]."""
    res = rpc(url, "qbft_getSignerMetrics", [hex(lo), hex(hi)])
    out: dict[str, int] = {}
    for entry in res:
        addr = entry["address"].lower()
        out[addr] = int(str(entry["proposedBlockCount"]), 16 if
                        str(entry["proposedBlockCount"]).startswith("0x") else 10)
    return out


def evaluate_window(counts: dict[str, int], validators: list[str],
                    window: int, tau: float) -> dict[str, int]:
    """Indicator X_i = 1 iff validator i is flagged in this window."""
    expected = window / max(len(validators), 1)
    return {v: int(counts.get(v, 0) < tau * expected) for v in validators}


def collect(url: str, validators: list[str], window: int, windows: int,
            tau: float, poll_seconds: float) -> list[dict]:
    """Observe consecutive, non-overlapping windows of ``window`` blocks."""
    observations: list[dict] = []
    head = int(rpc(url, "eth_blockNumber", []), 16)
    lo = head + 1
    for _ in range(windows):
        hi = lo + window - 1
        while int(rpc(url, "eth_blockNumber", []), 16) < hi:
            time.sleep(poll_seconds)
        counts = signer_metrics(url, lo, hi)
        observations.append({
            "lo": lo, "hi": hi,
            "counts": counts,
            "flags": evaluate_window(counts, validators, window, tau),
        })
        lo = hi + 1
    return observations


def rates(observations: list[dict], validators: list[str],
          faulty: list[str]) -> dict:
    """Detection probability, false-positive rate and exchangeable correlation."""
    faulty_set = {a.lower() for a in faulty}
    honest = [v for v in validators if v not in faulty_set]
    byz = [v for v in validators if v in faulty_set]

    tp = sum(obs["flags"][v] for obs in observations for v in byz)
    n_byz = len(byz) * len(observations)
    fp = sum(obs["flags"][v] for obs in observations for v in honest)
    n_hon = len(honest) * len(observations)

    p_d = tp / n_byz if n_byz else float("nan")
    p_f = fp / n_hon if n_hon else float("nan")

    # Exchangeable correlation among faulty-validator indicators:
    # rho = (mean pairwise product - p_d^2) / (p_d (1 - p_d)).
    rho = float("nan")
    if len(byz) > 1 and 0.0 < p_d < 1.0:
        pairs, acc = 0, 0
        for obs in observations:
            for i in range(len(byz)):
                for j in range(i + 1, len(byz)):
                    acc += obs["flags"][byz[i]] * obs["flags"][byz[j]]
                    pairs += 1
        rho = ((acc / pairs) - p_d ** 2) / (p_d * (1.0 - p_d)) if pairs else rho

    b_hat = [sum(obs["flags"].values()) / len(validators) for obs in observations]
    return {
        "p_d": p_d,
        "p_f": p_f,
        "rho": rho,
        "n_faulty": len(byz),
        "n_honest": len(honest),
        "windows": len(observations),
        "b_hat_mean": sum(b_hat) / len(b_hat) if b_hat else float("nan"),
        "b_hat_series": b_hat,
    }


def roc(observations_by_tau: dict[float, list[dict]], validators: list[str],
        faulty: list[str]) -> list[dict]:
    points = []
    for tau, obs in sorted(observations_by_tau.items()):
        r = rates(obs, validators, faulty)
        points.append({"tau": tau, "p_d": r["p_d"], "p_f": r["p_f"]})
    return points


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rpc", required=True)
    ap.add_argument("--network", type=Path, required=True,
                    help="network/network.json from gen_network.py")
    ap.add_argument("--faulty", default="",
                    help="comma-separated validator indices that were degraded")
    ap.add_argument("--window", type=int, default=30, help="blocks per window")
    ap.add_argument("--windows", type=int, default=10)
    ap.add_argument("--tau", type=float, default=0.5,
                    help="flag if share < tau * expected share")
    ap.add_argument("--tau-sweep", default="0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9",
                    help="thresholds for the ROC curve")
    ap.add_argument("--poll-seconds", type=float, default=1.0)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    net = json.loads(args.network.read_text(encoding="utf-8"))
    validators = [v["address"].lower() if v["address"].startswith("0x")
                  else ("0x" + v["address"]).lower()
                  for v in net["validators"]]
    idx = [int(i) for i in args.faulty.split(",") if i.strip() != ""]
    faulty = [validators[i] for i in idx]

    observations = collect(args.rpc, validators, args.window, args.windows,
                           args.tau, args.poll_seconds)

    taus = [float(t) for t in args.tau_sweep.split(",")]
    by_tau = {
        t: [{**obs,
             "flags": evaluate_window(obs["counts"], validators, args.window, t)}
            for obs in observations]
        for t in taus
    }

    result = {
        "tau": args.tau,
        "window": args.window,
        "windows": args.windows,
        "validators": validators,
        "faulty": faulty,
        "faulty_indices": idx,
        **rates(observations, validators, faulty),
        "roc": roc(by_tau, validators, faulty),
        "observations": observations,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"p_d={result['p_d']:.3f} p_f={result['p_f']:.3f} rho={result['rho']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
