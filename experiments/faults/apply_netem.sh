#!/usr/bin/env bash
# apply_netem.sh -- inject omission and duplication faults into selected
# validator containers.
#
# WHY NOT A PROXY: Besu's devp2p/RLPx transport is encrypted, so a TCP proxy
# cannot selectively drop *consensus* messages -- it sees ciphertext only.
# Kernel-level loss/duplication achieves the same fault class with far less
# machinery and without patching the client.
#
# FAULT CLASS: omission + duplication. This is a strict subset of Byzantine
# behaviour; equivocation and signature forgery are NOT modelled. The paper
# states this in its Limitations section.
#
# Usage:
#   ./apply_netem.sh apply  "validator1,validator2" 20 10 0
#   ./apply_netem.sh delay  "validator0,...,validatorN" 50      # RTT ms, all nodes
#   ./apply_netem.sh clear  "validator1,validator2"
#
# Containers must be started with cap_add: NET_ADMIN (gen_network.py does this).

set -euo pipefail

MODE="${1:?usage: apply_netem.sh <apply|delay|clear> <containers> [args]}"
CONTAINERS="${2:?comma-separated container names required}"

in_container() {
    local name="$1"; shift
    # iproute2 is not in the besu image; install once, quietly, per container.
    docker exec -u 0 "$name" sh -c \
        'command -v tc >/dev/null 2>&1 || (apt-get update -qq && apt-get install -y -qq iproute2 >/dev/null)'
    docker exec -u 0 "$name" sh -c "$*"
}

clear_qdisc() {
    local name="$1"
    in_container "$name" "tc qdisc del dev eth0 root 2>/dev/null || true"
}

case "$MODE" in
  apply)
    LOSS_PCT="${3:?loss percentage required}"
    DUP_PCT="${4:-0}"
    RTT_MS="${5:-0}"
    HALF_RTT=$(( RTT_MS / 2 ))
    IFS=',' read -ra NAMES <<< "$CONTAINERS"
    for name in "${NAMES[@]}"; do
        [ -z "$name" ] && continue
        clear_qdisc "$name"
        if [ "$HALF_RTT" -gt 0 ]; then
            in_container "$name" \
              "tc qdisc add dev eth0 root netem loss ${LOSS_PCT}% duplicate ${DUP_PCT}% delay ${HALF_RTT}ms 5ms distribution normal"
        else
            in_container "$name" \
              "tc qdisc add dev eth0 root netem loss ${LOSS_PCT}% duplicate ${DUP_PCT}%"
        fi
        echo "netem applied to ${name}: loss=${LOSS_PCT}% duplicate=${DUP_PCT}% rtt=${RTT_MS}ms"
    done
    ;;

  delay)
    RTT_MS="${3:?RTT in milliseconds required}"
    HALF_RTT=$(( RTT_MS / 2 ))
    IFS=',' read -ra NAMES <<< "$CONTAINERS"
    for name in "${NAMES[@]}"; do
        [ -z "$name" ] && continue
        clear_qdisc "$name"
        if [ "$HALF_RTT" -gt 0 ]; then
            in_container "$name" \
              "tc qdisc add dev eth0 root netem delay ${HALF_RTT}ms 5ms distribution normal"
        fi
        echo "netem delay applied to ${name}: rtt=${RTT_MS}ms"
    done
    ;;

  clear)
    IFS=',' read -ra NAMES <<< "$CONTAINERS"
    for name in "${NAMES[@]}"; do
        [ -z "$name" ] && continue
        clear_qdisc "$name"
        echo "netem cleared on ${name}"
    done
    ;;

  *)
    echo "unknown mode: $MODE" >&2
    exit 2
    ;;
esac
