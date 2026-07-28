#!/usr/bin/env python3
"""Run one design point end to end and emit a single JSON record.

Sequence: generate network -> start containers -> apply faults -> drive load ->
run the detector (if faults were injected) -> tear down -> write the record.

The record is the unit of analysis; ``analysis/fit_bifactor.py`` consumes a
directory of these files.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def compose(network_dir: Path, *args: str) -> None:
    run(["docker", "compose", "-f", str(network_dir / "docker-compose.yml"),
         *args])


def wait_for_rpc(url: str, timeout: int = 180) -> None:
    import requests
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.post(url, json={"jsonrpc": "2.0", "id": 1,
                                         "method": "eth_blockNumber",
                                         "params": []}, timeout=5)
            if r.ok and "result" in r.json():
                print("rpc is up", flush=True)
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    raise SystemExit("timed out waiting for the JSON-RPC endpoint")


def wait_for_progress(url: str, timeout: int = 240) -> None:
    """Block until the chain has produced at least two blocks."""
    import requests
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.post(url, json={"jsonrpc": "2.0", "id": 1,
                                     "method": "eth_blockNumber",
                                     "params": []}, timeout=5)
        if int(r.json()["result"], 16) >= 2:
            print("chain is producing blocks", flush=True)
            return
        time.sleep(2)
    raise SystemExit("chain did not start producing blocks")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--experiment", default="X1")
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--q", "--quota", dest="quota", type=float, default=0.25)
    ap.add_argument("--c", "--concurrency", dest="concurrency", type=int,
                    default=16)
    ap.add_argument("--replicate", type=int, default=0)
    ap.add_argument("--rtt-ms", type=int, default=0)
    ap.add_argument("--loss-pct", type=float, default=0.0)
    ap.add_argument("--duplicate-pct", type=float, default=0.0)
    ap.add_argument("--faulty-nodes", type=int, default=-1,
                    help="-1 selects floor((n-1)/3) when loss > 0")
    ap.add_argument("--block-period", type=int, default=2)
    ap.add_argument("--chain-id", type=int, default=1337)
    ap.add_argument("--jvm-heap-mb", type=int, default=512)
    ap.add_argument("--mem-limit-mb", type=int, default=900)
    ap.add_argument("--image", default="hyperledger/besu:24.10.0")
    ap.add_argument("--warmup", type=int, default=60)
    ap.add_argument("--duration", type=int, default=300)
    ap.add_argument("--drain", type=int, default=30)
    ap.add_argument("--detector-window", type=int, default=30)
    ap.add_argument("--detector-windows", type=int, default=8)
    ap.add_argument("--detector-tau", type=float, default=0.5)
    ap.add_argument("--workdir", type=Path, default=Path("network"))
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    faulty = args.faulty_nodes
    if faulty < 0:
        faulty = math.floor((args.n - 1) / 3) if args.loss_pct > 0 else 0

    rpc_port = 8545
    rpc_url = f"http://localhost:{rpc_port}"
    work = args.workdir

    record: dict = {
        "experiment": args.experiment,
        "n": args.n,
        "quota": args.quota,
        "concurrency": args.concurrency,
        "replicate": args.replicate,
        "rtt_ms": args.rtt_ms,
        "loss_pct": args.loss_pct,
        "duplicate_pct": args.duplicate_pct,
        "faulty_nodes": faulty,
        "block_period": args.block_period,
        "image": args.image,
        "status": "started",
    }

    try:
        run([sys.executable, str(HERE / "docker" / "gen_network.py"),
             "--n", str(args.n),
             "--quota", str(args.quota),
             "--mem-limit-mb", str(args.mem_limit_mb),
             "--jvm-heap-mb", str(args.jvm_heap_mb),
             "--block-period", str(args.block_period),
             "--chain-id", str(args.chain_id),
             "--accounts", str(max(args.concurrency + 1, 8)),
             "--image", args.image,
             "--rpc-base-port", str(rpc_port),
             "--out", str(work)])

        compose(work, "up", "-d")
        wait_for_rpc(rpc_url)
        wait_for_progress(rpc_url)

        # Wide-area emulation applies to every validator.
        if args.rtt_ms > 0:
            names = ",".join(f"validator{i}" for i in range(args.n))
            run(["bash", str(HERE / "faults" / "apply_netem.sh"),
                 "delay", names, str(args.rtt_ms)])

        # Omission + duplication applies to the designated faulty subset.
        # Node 0 is left healthy: it hosts the RPC endpoint we measure from.
        faulty_idx = list(range(1, 1 + faulty))
        if faulty > 0 and args.loss_pct > 0:
            names = ",".join(f"validator{i}" for i in faulty_idx)
            run(["bash", str(HERE / "faults" / "apply_netem.sh"),
                 "apply", names, str(args.loss_pct),
                 str(args.duplicate_pct), str(args.rtt_ms)])

        load_out = work / "load.json"
        run([sys.executable, str(HERE / "load" / "loadgen.py"),
             "--rpc", rpc_url,
             "--accounts", str(work / "accounts.json"),
             "--concurrency", str(args.concurrency),
             "--chain-id", str(args.chain_id),
             "--warmup", str(args.warmup),
             "--duration", str(args.duration),
             "--drain", str(args.drain),
             "--out", str(load_out)])
        load = json.loads(load_out.read_text(encoding="utf-8"))
        load.pop("block_detail", None)
        record["load"] = load
        record["tps"] = load["tps"]
        record["tps_normalized"] = load["tps"] / args.quota

        if faulty > 0:
            det_out = work / "detector.json"
            run([sys.executable,
                 str(HERE / "detector" / "signer_metrics_detector.py"),
                 "--rpc", rpc_url,
                 "--network", str(work / "network.json"),
                 "--faulty", ",".join(str(i) for i in faulty_idx),
                 "--window", str(args.detector_window),
                 "--windows", str(args.detector_windows),
                 "--tau", str(args.detector_tau),
                 "--out", str(det_out)])
            det = json.loads(det_out.read_text(encoding="utf-8"))
            det.pop("observations", None)
            record["detector"] = det

        record["status"] = "ok"

    except subprocess.CalledProcessError as exc:
        record["status"] = "failed"
        record["error"] = f"{exc.cmd} exited with {exc.returncode}"
    except SystemExit as exc:
        record["status"] = "failed"
        record["error"] = str(exc)
    finally:
        try:
            logs = work / "besu.log"
            with logs.open("w", encoding="utf-8") as fh:
                subprocess.run(["docker", "compose", "-f",
                                str(work / "docker-compose.yml"),
                                "logs", "--no-color", "--tail", "400"],
                               stdout=fh, stderr=subprocess.STDOUT, check=False)
            compose(work, "down", "-v")
        except Exception as exc:  # noqa: BLE001
            print(f"teardown warning: {exc}", file=sys.stderr)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in record.items()
                      if k in ("status", "n", "quota", "concurrency", "tps")},
                     indent=2))

    # Never fail the CI job on a single design point: fail-fast is disabled and
    # a failed record is itself data (it marks the memory ceiling).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
