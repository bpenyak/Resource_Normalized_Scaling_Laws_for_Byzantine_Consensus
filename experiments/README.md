# Experiments — Resource-Normalized Scaling Laws for BFT Consensus

Reproduction package for the paper. Everything runs on a **single 4-vCPU / 16 GB
GitHub Actions runner**. No dedicated hardware, no cloud credits.

> **Make the repository public.** Public repositories get unlimited Actions
> minutes; private ones get 2000 min/month, which is not enough for the full
> matrix.

---

## Layout

```
experiments/
  configs/matrix.yaml            # the experimental design matrix
  docker/gen_network.py          # QBFT genesis + keys + docker-compose generator
  load/loadgen.py                # c independent senders, per-sender nonce pool
  detector/signer_metrics_detector.py  # qbft_getSignerMetrics participation detector
  faults/apply_netem.sh          # omission + duplication injection via tc netem
  faults/byz_proxy.py            # fallback: per-peer TCP proxy
  analysis/fit_bifactor.py       # OLS in log-space -> T0, gamma, beta
  analysis/bootstrap_pi.py       # prediction intervals + coverage
  analysis/sizing.py             # Algorithm 2: feasibility window
  analysis/simulate.py           # SimPy QBFT model for large n
  analysis/make_figures.py       # figures/*.pdf
  analysis/emit_numbers_tex.py   # -> numbers.tex
  workflows/experiment.yml       # copy to .github/workflows/
  run_one.py                     # one design point end-to-end
  requirements.txt
  Makefile
```

---

## Quick start (local)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r experiments/requirements.txt

# one design point: 4 validators, quota 0.25, 4 senders, 90 s
python experiments/run_one.py --n 4 --q 0.25 --c 4 --duration 90 \
       --out data/raw/smoke.json
```

Requires Docker with the `hyperledger/besu` image available.

## Full campaign (CI)

```bash
cp experiments/workflows/experiment.yml .github/workflows/
git push
gh workflow run experiment.yml
gh run watch
gh run download -D data/raw
```

## Analysis

```bash
make analyze     # fit -> bootstrap -> sizing -> figures -> numbers.tex
```

---

## The RNM protocol in one paragraph

Running `n` validators on 4 cores means `n` processes competing for 4 cores.
A naive throughput-vs-`n` curve therefore mixes consensus overhead with CPU
contention. We give every validator a **fixed CPU quota `q`** regardless of `n`
(`cpus: 0.25` in compose, enforced by the cgroup CFS quota) and report the
normalized throughput `TPS/q`. The `q`-invariance of the fitted exponent is
**tested** (experiment X2), not assumed. Absolute TPS values are consequently
small and are not comparable with published benchmarks — no claim in the paper
depends on them.

---

## Fault model — read this

Besu's devp2p/RLPx transport is **encrypted**. A TCP proxy cannot selectively
drop consensus messages; it only sees ciphertext. We therefore inject faults at
the network layer with `tc netem` (`loss` = omission, `duplicate` = repetition)
and honestly call the fault class **omission + duplication**, a strict subset of
Byzantine behaviour. Equivocation is **not** modelled. This is stated in the
paper's Limitations section.

The detector reads `qbft_getSignerMetrics`, which reports `proposedBlockCount`
per validator over a block range. Since we know which containers were degraded,
every run yields ground truth, from which `p_d`, `p_f`, `rho` and the ROC curve
are estimated — **without patching Besu**.

---

## Security notes

* Validator keys are generated on the fly by `besu operator
  generate-blockchain-config` and are **development keys only**. Never reuse
  them anywhere.
* `.gitignore` excludes `*.key`, `networkFiles/`, `data/keys/`.
* JSON-RPC is bound to the loopback interface inside the job and is never exposed.
* No secrets are echoed into CI logs.
