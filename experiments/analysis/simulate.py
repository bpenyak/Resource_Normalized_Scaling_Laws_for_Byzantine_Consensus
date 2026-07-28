#!/usr/bin/env python3
"""Discrete-event QBFT model for validator counts beyond the measurable range.

Calibrated on experiments X1--X4: per-message processing time, link latency and
per-validator service capacity are taken from the measured fit. The model
reproduces the three-phase QBFT exchange (pre-prepare, prepare, commit) with its
O(n^2) message complexity.

This is a SIMULATION. It is never reported as a measurement; its role in the
paper is to show that the n^(-beta) shape persists beyond the range we can
actually run.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import simpy


def quorum(n: int) -> int:
    f = (n - 1) // 3
    return math.ceil((n + f + 1) / 2)


def run_one(n: int, msg_service_s: float, link_latency_s: float,
            block_period_s: float, tx_capacity: int, horizon_s: float,
            seed: int) -> dict:
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    # Each validator processes messages serially: this is the CPU quota q.
    cpus = {i: simpy.Resource(env, capacity=1) for i in range(n)}
    committed = {"blocks": 0, "tx": 0, "latencies": []}
    q = quorum(n)

    def deliver(dst: int, arrivals: list[float]):
        yield env.timeout(max(rng.normal(link_latency_s, link_latency_s * 0.1),
                              0.0))
        with cpus[dst].request() as req:
            yield req
            yield env.timeout(max(rng.normal(msg_service_s,
                                             msg_service_s * 0.2), 0.0))
        arrivals.append(env.now)

    def phase(n_senders: int):
        """One all-to-all broadcast round; completes when a quorum is reached."""
        arrivals: list[float] = []
        for dst in range(n):
            for _ in range(n_senders):
                env.process(deliver(dst, arrivals))
        while len(arrivals) < q:
            yield env.timeout(msg_service_s / 4.0)

    def consensus():
        while True:
            start = env.now
            yield env.timeout(block_period_s)
            yield env.process(phase(1))    # pre-prepare: proposer -> all
            yield env.process(phase(q))    # prepare
            yield env.process(phase(q))    # commit
            committed["blocks"] += 1
            committed["tx"] += tx_capacity
            committed["latencies"].append(env.now - start)

    env.process(consensus())
    env.run(until=horizon_s)

    elapsed = horizon_s
    return {
        "n": n,
        "blocks": committed["blocks"],
        "tx": committed["tx"],
        "tps": committed["tx"] / elapsed if elapsed else 0.0,
        "block_time_mean": (float(np.mean(committed["latencies"]))
                            if committed["latencies"] else None),
        "quorum": q,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--out", dest="out", type=Path, required=True)
    ap.add_argument("--ns", default="20,30,50,75,100,150,200,300,500")
    ap.add_argument("--horizon", type=float, default=600.0,
                    help="simulated seconds per configuration")
    ap.add_argument("--replicates", type=int, default=5)
    ap.add_argument("--msg-service-ms", type=float, default=0.8)
    ap.add_argument("--link-latency-ms", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=20260101)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    fit = json.loads((args.inp / "fit.json").read_text(encoding="utf-8"))
    dataset = pd.read_csv(args.inp / "dataset.csv")
    clean = dataset[(dataset["loss_pct"] == 0) & (dataset["rtt_ms"] == 0)]

    block_period = float(clean["block_interval_mean"].median()) \
        if clean["block_interval_mean"].notna().any() else 2.0
    # Calibrate the per-block transaction capacity from the smallest measured n.
    n0 = int(clean["n"].min())
    ref = clean[clean["n"] == n0]
    tx_capacity = max(int(round(float(ref["tps"].median()) * block_period)), 1)

    rows = []
    for n in [int(x) for x in args.ns.split(",") if x.strip()]:
        for r in range(args.replicates):
            rows.append(run_one(n, args.msg_service_ms / 1000.0,
                                args.link_latency_ms / 1000.0, block_period,
                                tx_capacity, args.horizon,
                                args.seed + 1000 * n + r) | {"replicate": r})

    sim = pd.DataFrame(rows)
    sim.to_csv(args.out / "simulation.csv", index=False)

    agg = sim.groupby("n")["tps"].median()
    slope = float(np.polyfit(np.log(agg.index.to_numpy(float)),
                             np.log(agg.to_numpy()), 1)[0])
    (args.out / "simulation_fit.json").write_text(json.dumps({
        "beta_simulated": -slope,
        "beta_measured": fit["beta"],
        "block_period_s": block_period,
        "tx_capacity_per_block": tx_capacity,
        "calibration_n": n0,
        "note": "simulation only; not reported as measurement",
    }, indent=2), encoding="utf-8")

    print(f"simulated beta={-slope:.4f} vs measured beta={fit['beta']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
