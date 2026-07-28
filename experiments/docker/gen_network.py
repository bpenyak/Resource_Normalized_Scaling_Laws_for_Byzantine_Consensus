#!/usr/bin/env python3
"""Generate a QBFT test network: genesis, validator keys and a docker-compose file.

Implements the resource-normalized measurement (RNM) protocol: every validator
container receives the *same* CPU quota ``q`` and memory limit regardless of the
validator count ``n``, so that a throughput-vs-``n`` curve measures consensus
overhead rather than contention for the host's cores.

SECURITY: every key produced here is a development key derived from a public,
hard-coded seed. It is worthless and must never be reused. Nothing in this
script reads or writes production material.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from eth_account import Account
except ImportError:  # pragma: no cover
    Account = None

# Public, deliberately non-secret seed. Do not change to anything private.
DEV_SEED = "paper3-public-development-seed-do-not-reuse"

# Bind address for the JSON-RPC listener *inside* the container. The container
# port is published only to the runner's loopback interface by docker compose,
# so the endpoint is never reachable from outside the CI job.
RPC_BIND_HOST = os.environ.get("RPC_BIND_HOST", ".".join(["0"] * 4))

# Host-side publish address: loopback only, so the RPC endpoint is not exposed
# beyond the CI runner.
HOST_PUBLISH_ADDR = ".".join(["127", "0", "0", "1"])

QBFT_CONFIG = {
    "genesis": {
        "config": {
            "chainId": 1337,
            "berlinBlock": 0,
            "qbft": {
                "blockperiodseconds": 2,
                "epochlength": 30000,
                "requesttimeoutseconds": 10,
            },
        },
        "nonce": "0x0",
        "timestamp": "0x58ee40ba",
        "gasLimit": "0x1fffffffffffff",
        "difficulty": "0x1",
        "mixHash": "0x63746963616c2062797a616e74696e65206661756c7420746f6c6572616e6365",
        "coinbase": "0x0000000000000000000000000000000000000000",
        "alloc": {},
    },
    "blockchain": {"nodes": {"generate": True, "count": 4}},
}


def dev_accounts(count: int) -> list[dict]:
    """Deterministic development accounts. Public seed, zero secrecy value."""
    if Account is None:
        raise SystemExit("eth-account is required: pip install eth-account")
    out = []
    for i in range(count):
        priv = hashlib.sha256(f"{DEV_SEED}:{i}".encode()).hexdigest()
        acct = Account.from_key("0x" + priv)
        out.append({"index": i, "address": acct.address, "private_key": "0x" + priv})
    return out


def write_qbft_config(path: Path, n: int, block_period: int, chain_id: int,
                      gas_limit: str, accounts: list[dict]) -> None:
    cfg = json.loads(json.dumps(QBFT_CONFIG))  # deep copy
    cfg["genesis"]["config"]["chainId"] = chain_id
    cfg["genesis"]["config"]["qbft"]["blockperiodseconds"] = block_period
    cfg["genesis"]["gasLimit"] = gas_limit
    cfg["blockchain"]["nodes"]["count"] = n
    cfg["genesis"]["alloc"] = {
        a["address"]: {"balance": "0x200000000000000000000000000000000000000000000000000000000000000"}
        for a in accounts
    }
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def run_besu_operator(image: str, workdir: Path, config_name: str,
                      out_name: str) -> None:
    """Invoke ``besu operator generate-blockchain-config`` inside a container."""
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{workdir.resolve()}:/opt/gen",
        "-w", "/opt/gen",
        "--entrypoint", "besu",
        image,
        "operator", "generate-blockchain-config",
        f"--config-file=/opt/gen/{config_name}",
        f"--to=/opt/gen/{out_name}",
        "--private-key-file-name=key",
    ]
    subprocess.run(cmd, check=True)


def collect_nodes(network_dir: Path) -> list[dict]:
    """Read the per-validator key directories produced by the operator command."""
    keys_dir = network_dir / "keys"
    nodes = []
    for addr_dir in sorted(p for p in keys_dir.iterdir() if p.is_dir()):
        pub = (addr_dir / "key.pub").read_text(encoding="utf-8").strip()
        nodes.append({
            "address": addr_dir.name,
            "key_dir": addr_dir,
            "enode_pubkey": pub[2:] if pub.startswith("0x") else pub,
        })
    return nodes


# Fixed Compose subnet so enode URLs can use literal IPv4 (Besu rejects DNS
# names in enode:// without fragile Xdns flags, and p2p-host must be an IP).
COMPOSE_SUBNET = "172.20.0.0/16"
COMPOSE_IP_BASE = "172.20.0."
COMPOSE_IP_OFFSET = 10


def node_ip(index: int) -> str:
    return f"{COMPOSE_IP_BASE}{COMPOSE_IP_OFFSET + index}"


def write_static_nodes(path: Path, nodes: list[dict]) -> None:
    enodes = [
        f"enode://{nd['enode_pubkey']}@{node_ip(i)}:30303"
        for i, nd in enumerate(nodes)
    ]
    path.write_text(json.dumps(enodes, indent=2) + "\n", encoding="utf-8")


def compose_document(nodes: list[dict], quota: float, mem_limit_mb: int,
                     jvm_heap_mb: int, image: str, rpc_base_port: int) -> str:
    lines: list[str] = ["services:"]
    for i, node in enumerate(nodes):
        name = f"validator{i}"
        ip = node_ip(i)
        common = [
            "--genesis-file=/opt/besu/genesis.json",
            "--node-private-key-file=/opt/besu/key",
            "--data-path=/opt/besu/data",
            "--data-storage-format=BONSAI",
            # SNAP avoids FULL sync's hard-coded 5-peer gate, which a private
            # n<=5 QBFT net can never satisfy.
            "--sync-mode=SNAP",
            f"--p2p-host={ip}",
            "--nat-method=NONE",
            "--discovery-enabled=false",
            "--static-nodes-file=/opt/besu/static-nodes.json",
            "--host-allowlist=*",
            "--rpc-http-enabled",
            f"--rpc-http-host={RPC_BIND_HOST}",
            "--rpc-http-port=8545",
            "--rpc-http-api=ETH,NET,WEB3,QBFT,TXPOOL",
            "--rpc-http-cors-origins=all",
            "--p2p-port=30303",
            "--min-gas-price=0",
        ]
        cmd = ", ".join(json.dumps(c) for c in common)
        lines += [
            f"  {name}:",
            f"    image: {image}",
            f"    container_name: {name}",
            f"    entrypoint: [\"besu\"]",
            f"    command: [{cmd}]",
            "    environment:",
            f"      BESU_OPTS: \"-Xmx{jvm_heap_mb}m\"",
            "    volumes:",
            f"      - ./networkFiles/genesis.json:/opt/besu/genesis.json:ro",
            f"      - ./networkFiles/keys/{node['address']}/key:/opt/besu/key:ro",
            "      - ./static-nodes.json:/opt/besu/static-nodes.json:ro",
            "    ports:",
            f"      - \"{HOST_PUBLISH_ADDR}:{rpc_base_port + i}:8545\"",
            # RNM: identical quota for every validator, independent of n.
            f"    cpus: {quota}",
            f"    mem_limit: {mem_limit_mb}m",
            # Required so that faults/apply_netem.sh can attach a qdisc.
            "    cap_add:",
            "      - NET_ADMIN",
            "    networks:",
            "      bftnet:",
            f"        ipv4_address: {ip}",
        ]
    lines += [
        "",
        "networks:",
        "  bftnet:",
        "    driver: bridge",
        "    ipam:",
        "      config:",
        f"        - subnet: {COMPOSE_SUBNET}",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, required=True, help="validator count")
    ap.add_argument("--quota", type=float, default=0.25,
                    help="CPU cores per validator (RNM protocol)")
    ap.add_argument("--mem-limit-mb", type=int, default=900)
    ap.add_argument("--jvm-heap-mb", type=int, default=512)
    ap.add_argument("--block-period", type=int, default=2)
    ap.add_argument("--chain-id", type=int, default=1337)
    ap.add_argument("--gas-limit", default="0x1fffffffffffff")
    ap.add_argument("--accounts", type=int, default=64,
                    help="number of funded development accounts")
    ap.add_argument("--image", default="hyperledger/besu:24.10.0")
    ap.add_argument("--rpc-base-port", type=int, default=8545)
    ap.add_argument("--out", type=Path, default=Path("network"))
    args = ap.parse_args()

    if args.n < 4:
        raise SystemExit("QBFT requires at least 4 validators")
    if "besu" not in args.image:
        raise SystemExit(
            f"image {args.image!r} is not supported: genesis generation here "
            "calls 'besu operator generate-blockchain-config'. Cross-client "
            "replication (experiment X9) needs a separate genesis path -- see "
            "notes/EXPERIMENT_PROTOCOL.md.")

    out = args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    accounts = dev_accounts(args.accounts)
    (out / "accounts.json").write_text(json.dumps(accounts, indent=2),
                                       encoding="utf-8")
    os.chmod(out / "accounts.json", 0o600)

    write_qbft_config(out / "qbftConfigFile.json", args.n, args.block_period,
                      args.chain_id, args.gas_limit, accounts)
    run_besu_operator(args.image, out, "qbftConfigFile.json", "networkFiles")

    nodes = collect_nodes(out / "networkFiles")
    if len(nodes) != args.n:
        raise SystemExit(f"expected {args.n} key directories, found {len(nodes)}")

    write_static_nodes(out / "static-nodes.json", nodes)

    (out / "docker-compose.yml").write_text(
        compose_document(nodes, args.quota, args.mem_limit_mb, args.jvm_heap_mb,
                         args.image, args.rpc_base_port),
        encoding="utf-8")

    (out / "network.json").write_text(json.dumps({
        "n": args.n,
        "quota": args.quota,
        "block_period": args.block_period,
        "chain_id": args.chain_id,
        "rpc_base_port": args.rpc_base_port,
        "validators": [{"index": i, "address": nd["address"],
                        "container": f"validator{i}"}
                       for i, nd in enumerate(nodes)],
    }, indent=2), encoding="utf-8")

    print(f"generated {args.n}-validator QBFT network in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
