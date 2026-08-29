#!/usr/bin/env bash
# Idempotent repository bootstrap for Cloud Agents.
# Installs the Docker-based runtime and Python toolchain, then syncs dependencies.
# Runs once to build the environment snapshot; per-boot work lives in start.sh.
set -euo pipefail

cd "$(dirname "$0")/.."

export DEBIAN_FRONTEND=noninteractive

# System packages. The base image ships git/make/curl/node/python3 but not Docker or uv.
# Keep existing conffiles (e.g. /etc/fuse.conf) so non-interactive apt does not stall.
sudo apt-get update -qq
sudo apt-get install -y -qq \
  -o Dpkg::Options::=--force-confdef \
  -o Dpkg::Options::=--force-confold \
  docker.io docker-compose-v2 fuse-overlayfs uidmap make curl

# uv: install from PyPI (astral.sh is not in the Cloud Agent egress allowlist).
sudo python3 -m pip install --quiet --upgrade uv

# Python dependencies, including dev extras (pytest, ruff, pyyaml).
uv sync --extra dev

# Local env files consumed by docker compose and the seed/migrate scripts.
# Never overwrite an existing file (may hold real secrets such as OPENAI_API_KEY).
[ -f .env ] || cp .env.example .env
[ -f infra/langfuse/.env ] || cp infra/langfuse/env.example infra/langfuse/.env

echo "install.sh: done"
