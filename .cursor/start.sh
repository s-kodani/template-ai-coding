#!/usr/bin/env bash
# Per-boot runtime reconciliation for Cloud Agents.
# Brings up the Docker daemon so `make -C infra up` and `docker build` work inside the
# nested Cloud Agent VM. Idempotent: a second run is a no-op when Docker already responds.
set -euo pipefail

# In this nested VM the kernel cannot use the overlay2 storage driver, and intra-bridge
# container traffic is dropped when bridged frames traverse the iptables FORWARD chain.
# Load br_netfilter and disable bridge-nf so containers on the same compose network can
# reach each other (e.g. mcp-server -> app-postgres).
sudo modprobe br_netfilter 2>/dev/null || true
for f in bridge-nf-call-iptables bridge-nf-call-ip6tables; do
  [ -w "/proc/sys/net/bridge/$f" ] && echo 0 | sudo tee "/proc/sys/net/bridge/$f" >/dev/null || true
done

# Start the Docker daemon if it is not already responding.
if ! sudo docker info >/dev/null 2>&1; then
  sudo mkdir -p /var/log
  sudo nohup dockerd --storage-driver=fuse-overlayfs >/var/log/dockerd.log 2>&1 &
  for _ in $(seq 1 60); do
    sudo docker info >/dev/null 2>&1 && break
    sleep 1
  done
fi

# Re-assert the sysctl once the docker0 bridge exists, then confirm readiness.
for f in bridge-nf-call-iptables bridge-nf-call-ip6tables; do
  [ -w "/proc/sys/net/bridge/$f" ] && echo 0 | sudo tee "/proc/sys/net/bridge/$f" >/dev/null || true
done

if sudo docker info >/dev/null 2>&1; then
  echo "start.sh: docker ready ($(sudo docker info --format '{{.ServerVersion}} driver={{.Driver}}'))"
else
  echo "start.sh: docker failed to start; see /var/log/dockerd.log" >&2
  exit 1
fi
