#!/usr/bin/env bash
# Deploy FluentLoop to the VPS.
#
# Adapted from aiprojects/openclaw_firststeps/scripts/deploy-telethon-digest.sh.
# Steps:
#   1. Rsync the repo (excluding .git, .env, data, caches) to /opt/fluentloop-bot/.
#   2. Rsync the local .env separately with mode 600.
#   3. SSH and run `docker compose up -d --build`.
#   4. Tail logs for 15s to confirm startup.
#
# Codex may modify this script if a missing piece is discovered (e.g. needs to
# create /opt/fluentloop-bot/data/ pre-deploy). Document any such change in
# MORNING_REPORT.md.
set -euo pipefail

VPS_USER="${VPS_USER:-deploy}"
VPS_HOST="${VPS_HOST:-<vps-host>}"
VPS_PORT="${VPS_PORT:-22}"
REMOTE_DIR="${REMOTE_DIR:-/opt/fluentloop-bot}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_ENV="${REPO_ROOT}/.env"

if [[ ! -f "$LOCAL_ENV" ]]; then
  echo "FAIL: local .env missing at ${LOCAL_ENV}" >&2
  exit 1
fi

ssh_cmd=(ssh -o BatchMode=yes -o ConnectTimeout=10 -p "$VPS_PORT" "${VPS_USER}@${VPS_HOST}")

echo "==> Ensuring remote directory exists: ${REMOTE_DIR}"
"${ssh_cmd[@]}" "
  if mkdir -p ${REMOTE_DIR}/data ${REMOTE_DIR}/data/sessions ${REMOTE_DIR}/data/backups 2>/dev/null; then
    true
  else
    sudo mkdir -p ${REMOTE_DIR}/data ${REMOTE_DIR}/data/sessions ${REMOTE_DIR}/data/backups
    sudo chown -R ${VPS_USER}:${VPS_USER} ${REMOTE_DIR}
  fi
"

echo "==> Rsync code to ${VPS_USER}@${VPS_HOST}:${REMOTE_DIR}/"
rsync -az --delete \
  --exclude='.git/' \
  --exclude='.env' \
  --exclude='.env.*' \
  --exclude='data/' \
  --exclude='secrets/' \
  --exclude='__pycache__/' \
  --exclude='.venv/' \
  --exclude='node_modules/' \
  --exclude='.pytest_cache/' \
  --exclude='.mypy_cache/' \
  --exclude='.ruff_cache/' \
  --exclude='*.session' \
  --exclude='*.session-journal' \
  -e "ssh -o BatchMode=yes -p ${VPS_PORT}" \
  "${REPO_ROOT}/" \
  "${VPS_USER}@${VPS_HOST}:${REMOTE_DIR}/"

echo "==> Rsync .env (mode 600)"
rsync -az \
  -e "ssh -o BatchMode=yes -p ${VPS_PORT}" \
  "${LOCAL_ENV}" \
  "${VPS_USER}@${VPS_HOST}:${REMOTE_DIR}/.env"
"${ssh_cmd[@]}" "chmod 600 ${REMOTE_DIR}/.env"

echo "==> Build + (re)start container"
"${ssh_cmd[@]}" "cd ${REMOTE_DIR} && docker compose up -d --build"

echo "==> Tail logs (15s)"
"${ssh_cmd[@]}" "cd ${REMOTE_DIR} && timeout 15 docker compose logs --tail=50 --follow || true"

echo "==> Done. Smoke-test next: python ${REPO_ROOT}/scripts/smoke_telegram.py"
