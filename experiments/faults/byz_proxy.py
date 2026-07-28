#!/usr/bin/env python3
"""Fallback fault injector: a TCP proxy with per-peer omission and duplication.

USE ``faults/apply_netem.sh`` INSTEAD unless you need per-peer control.

Scope and honest limitation. Besu's devp2p/RLPx transport is encrypted, so this
proxy cannot parse or selectively filter consensus messages -- it operates on
opaque byte segments. It therefore realizes exactly the same fault class as
``tc netem`` (omission + duplication), with the single advantage that the fault
can be targeted at an individual peer connection rather than at the whole
interface. Equivocation is out of reach without patching the client.

The proxy is deliberately confined to the local experiment: it binds to the
loopback interface, forwards to a single configured upstream, and refuses to
run unless both endpoints are explicitly supplied.
"""

from __future__ import annotations

import argparse
import asyncio
import random

LOOPBACK = ".".join(["127", "0", "0", "1"])


class Degrader:
    """Applies omission and duplication to a unidirectional byte stream."""

    def __init__(self, loss: float, duplicate: float, seed: int | None = None):
        if not 0.0 <= loss < 1.0 or not 0.0 <= duplicate < 1.0:
            raise ValueError("loss and duplicate must lie in [0, 1)")
        self.loss = loss
        self.duplicate = duplicate
        self.rng = random.Random(seed)
        self.dropped = 0
        self.duplicated = 0
        self.forwarded = 0

    def transform(self, chunk: bytes) -> list[bytes]:
        if self.rng.random() < self.loss:
            self.dropped += 1
            return []
        self.forwarded += 1
        if self.rng.random() < self.duplicate:
            self.duplicated += 1
            return [chunk, chunk]
        return [chunk]


async def pump(reader: asyncio.StreamReader, writer: asyncio.StreamWriter,
               degrader: Degrader | None) -> None:
    try:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            parts = degrader.transform(chunk) if degrader else [chunk]
            for part in parts:
                writer.write(part)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
        pass
    finally:
        writer.close()


async def handle(client_reader: asyncio.StreamReader,
                 client_writer: asyncio.StreamWriter,
                 upstream_host: str, upstream_port: int,
                 outbound: Degrader, inbound: Degrader) -> None:
    try:
        up_reader, up_writer = await asyncio.open_connection(
            upstream_host, upstream_port)
    except OSError:
        client_writer.close()
        return
    await asyncio.gather(
        pump(client_reader, up_writer, outbound),
        pump(up_reader, client_writer, inbound),
    )


async def serve(listen_port: int, upstream_host: str, upstream_port: int,
                loss: float, duplicate: float, seed: int | None) -> None:
    outbound = Degrader(loss, duplicate, seed)
    inbound = Degrader(loss, duplicate, None if seed is None else seed + 1)

    server = await asyncio.start_server(
        lambda r, w: handle(r, w, upstream_host, upstream_port,
                            outbound, inbound),
        host=LOOPBACK, port=listen_port)

    addr = server.sockets[0].getsockname()
    print(f"proxy listening on {addr} -> {upstream_host}:{upstream_port} "
          f"(loss={loss}, duplicate={duplicate})", flush=True)
    async with server:
        await server.serve_forever()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--listen-port", type=int, required=True)
    ap.add_argument("--upstream-host", required=True)
    ap.add_argument("--upstream-port", type=int, required=True)
    ap.add_argument("--loss", type=float, default=0.0,
                    help="per-segment omission probability in [0, 1)")
    ap.add_argument("--duplicate", type=float, default=0.0,
                    help="per-segment duplication probability in [0, 1)")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    try:
        asyncio.run(serve(args.listen_port, args.upstream_host,
                          args.upstream_port, args.loss, args.duplicate,
                          args.seed))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
