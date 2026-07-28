#!/usr/bin/env python3
"""Expand configs/matrix.yaml into a GitHub Actions job matrix.

Emits a JSON array of design points on stdout (and, when ``GITHUB_OUTPUT`` is
set, as the ``matrix`` step output). GitHub caps a matrix at 256 jobs; the
script fails loudly rather than silently truncating.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
from pathlib import Path

import yaml

MAX_JOBS = 256


def expand(cfg: dict, only: list[str] | None) -> list[dict]:
    defaults = cfg["defaults"]
    points: list[dict] = []

    for name, spec in cfg["experiments"].items():
        if only and name not in only:
            continue
        grid = spec.get("grid", {})
        keys = list(grid)
        replicates = int(spec.get("replicates", defaults.get("replicates", 1)))

        for combo in itertools.product(*(grid[k] for k in keys)):
            base = dict(zip(keys, combo))
            for r in range(replicates):
                point = {
                    "experiment": name,
                    "n": base.get("n", 4),
                    "quota": base.get("quota", defaults["quota"]),
                    "concurrency": base.get("concurrency",
                                            defaults["concurrency"]),
                    "rtt_ms": base.get("rtt_ms", defaults["rtt_ms"]),
                    "loss_pct": base.get("loss_pct", defaults["loss_pct"]),
                    "replicate": r,
                }
                derived = spec.get("derived", {})
                if "duplicate_pct" in derived:
                    point["duplicate_pct"] = point["loss_pct"] / 2.0
                else:
                    point["duplicate_pct"] = defaults["duplicate_pct"]
                if "faulty_nodes" in derived:
                    point["faulty_nodes"] = (
                        math.floor((point["n"] - 1) / 3)
                        if point["loss_pct"] > 0 else 0)
                else:
                    point["faulty_nodes"] = defaults["faulty_nodes"]
                point["id"] = (f"{name}-n{point['n']}-q{point['quota']}"
                               f"-c{point['concurrency']}-r{point['rtt_ms']}"
                               f"-l{point['loss_pct']:g}-rep{r}")
                points.append(point)

    return points


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", type=Path,
                    default=Path("experiments/configs/matrix.yaml"))
    ap.add_argument("--only", default="",
                    help="comma-separated experiment ids, e.g. X1,X3")
    args = ap.parse_args()

    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    only = [s.strip() for s in args.only.split(",") if s.strip()] or None
    points = expand(cfg, only)

    if not points:
        raise SystemExit("the expanded matrix is empty")
    if len(points) > MAX_JOBS:
        raise SystemExit(f"{len(points)} jobs exceeds the GitHub limit of "
                         f"{MAX_JOBS}; split the run with --only")

    payload = json.dumps(points)
    print(payload)
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as fh:
            fh.write(f"matrix={payload}\n")
            fh.write(f"count={len(points)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
