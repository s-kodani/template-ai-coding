#!/usr/bin/env bash
# Per-boot runtime reconciliation for Cloud Agents.
# Brings up the Docker daemon so `make -C infra up` and `docker build` work inside the
# nested Cloud Agent VM. Idempotent: a second run is a no-op when Docker already responds.
set -euo pipefail

# In this nested VM the kernel cannot use the overlay2 storage driver, and intra-bridge
# container traffic is dropped when bridged frames traverse the iptables FORWARD chain.
# Load br_netfilter and disable bridge-nf so containers on the same compose network can
# reach each other (e.g. mcp-server -> app-postgres).
# NOTE: run the writes under root; the sysctl nodes are root-owned, and a redirect in an
# unprivileged shell (even with a sudo command) would be opened by the non-root shell.
disable_bridge_nf() {
  sudo modprobe br_netfilter 2>/dev/null || true
  for f in bridge-nf-call-iptables bridge-nf-call-ip6tables; do
    sudo sh -c "[ -e /proc/sys/net/bridge/$f ] && echo 0 > /proc/sys/net/bridge/$f" 2>/dev/null || true
  done
}

disable_bridge_nf

# Start the Docker daemon if it is not already responding.
if ! sudo docker info >/dev/null 2>&1; then
  sudo sh -c 'nohup dockerd --storage-driver=fuse-overlayfs >/var/log/dockerd.log 2>&1 &'
  for _ in $(seq 1 60); do
    sudo docker info >/dev/null 2>&1 && break
    sleep 1
  done
fi

# Re-assert the sysctl once the docker0 bridge exists, then confirm readiness.
disable_bridge_nf

disable_bridge_nf

if sudo docker info >/dev/null 2>&1; then
  echo "start.sh: docker ready ($(sudo docker info --format '{{.ServerVersion}} driver={{.Driver}}'))"
else
  echo "start.sh: docker failed to start; see /var/log/dockerd.log" >&2
  exit 1
fi

# Containers cannot SNAT to the public internet while bridge-nf is 0. A host
# CONNECT proxy lets mcp-server / chainlit reach allowlisted HTTPS (api.openai.com).
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if ! ss -lntp 2>/dev/null | grep -q ':8888 '; then
  nohup python3 "$ROOT/.cursor/egress-proxy.py" >/tmp/cursor-egress-proxy.log 2>&1 &
  echo "start.sh: egress proxy on :8888"
fi
