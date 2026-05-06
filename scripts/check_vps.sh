#!/usr/bin/env bash
# Pre-flight check: SSH to the VPS works and Docker is reachable there.
# Exits 0 on success, non-zero on failure. Quiet on success except for
# "OK" line.
set -euo pipefail

VPS_USER="${VPS_USER:-deploy}"
VPS_HOST="${VPS_HOST:-<vps-host>}"
VPS_PORT="${VPS_PORT:-22}"

if ! command -v ssh >/dev/null 2>&1; then
  echo "FAIL: ssh client not found in PATH" >&2
  exit 1
fi

# BatchMode=yes — never prompt for password (key auth only).
# ConnectTimeout=5 — fail fast if host unreachable.
output=$(ssh \
  -o BatchMode=yes \
  -o ConnectTimeout=5 \
  -o StrictHostKeyChecking=accept-new \
  -p "$VPS_PORT" \
  "${VPS_USER}@${VPS_HOST}" \
  'docker --version 2>&1 && echo "__OK__"' 2>&1) || {
    echo "FAIL: SSH to ${VPS_USER}@${VPS_HOST}:${VPS_PORT} failed" >&2
    echo "$output" >&2
    exit 1
}

if ! grep -q '__OK__' <<<"$output"; then
  echo "FAIL: SSH succeeded but docker not reachable on VPS" >&2
  echo "$output" >&2
  exit 1
fi

docker_version=$(grep '^Docker version' <<<"$output" || echo 'docker (version unknown)')
echo "OK: ${VPS_USER}@${VPS_HOST}:${VPS_PORT} reachable; ${docker_version}"
