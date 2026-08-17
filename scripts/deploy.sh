#!/usr/bin/env bash
# Deploy FluentLoop to the VPS.
#
# Adapted from aiprojects/openclaw_firststeps/scripts/deploy-telethon-digest.sh.
# Steps:
#   1. Rsync the repo (excluding .git, .env, data, caches) to /opt/fluentloop-bot/.
#   2. Rsync the local .env separately with mode 600.
#   3. Build image, run Alembic migrations, then run `docker compose up -d`.
#   4. Tail logs for 15s to confirm startup.
#
# Codex may modify this script if a missing piece is discovered (e.g. needs to
# create /opt/fluentloop-bot/data/ pre-deploy). Document any such change in
# MORNING_REPORT.md.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_ENV="${REPO_ROOT}/.env"
DEPLOY_ENV="${DEPLOY_ENV:-${REPO_ROOT}/secrets/deploy.env}"

if [[ -f "$DEPLOY_ENV" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$DEPLOY_ENV"
  set +a
fi

VPS_USER="${VPS_USER:-deploy}"
VPS_HOST="${VPS_HOST:-}"
VPS_PORT="${VPS_PORT:-22}"
REMOTE_DIR="${REMOTE_DIR:-/opt/fluentloop-bot}"

if [[ ! -f "$LOCAL_ENV" ]]; then
  echo "FAIL: local .env missing at ${LOCAL_ENV}" >&2
  exit 1
fi

if [[ -z "$VPS_HOST" ]]; then
  echo "FAIL: VPS_HOST must be set via env or ${DEPLOY_ENV}" >&2
  exit 1
fi

ssh_cmd=(
  ssh
  -o BatchMode=yes
  -o ConnectTimeout=10
  -o ServerAliveInterval=30
  -o ServerAliveCountMax=20
  -p "$VPS_PORT"
  "${VPS_USER}@${VPS_HOST}"
)

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
  -e "ssh -o BatchMode=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=20 -p ${VPS_PORT}" \
  "${REPO_ROOT}/" \
  "${VPS_USER}@${VPS_HOST}:${REMOTE_DIR}/"

echo "==> Rsync .env (mode 600)"
rsync -az \
  -e "ssh -o BatchMode=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=20 -p ${VPS_PORT}" \
  "${LOCAL_ENV}" \
  "${VPS_USER}@${VPS_HOST}:${REMOTE_DIR}/.env"
"${ssh_cmd[@]}" "chmod 600 ${REMOTE_DIR}/.env"

echo "==> Backup SQLite before migrations when present"
# BACKUP_RETENTION_DAYS only prunes the scheduled db-*.sqlite snapshots, so
# without the trim below every deploy leaves a ~30MB file behind forever.
PRE_MIGRATION_KEEP="${PRE_MIGRATION_KEEP:-5}"
"${ssh_cmd[@]}" "
  cd ${REMOTE_DIR}
  if [ -f data/fluentloop.sqlite ]; then
    cp data/fluentloop.sqlite data/backups/pre-migration-\$(date +%Y%m%d-%H%M%S).sqlite
    ls -1t data/backups/pre-migration-*.sqlite 2>/dev/null \
      | tail -n +\$((${PRE_MIGRATION_KEEP} + 1)) \
      | xargs -r rm -f
  fi
"

echo "==> Build image"
"${ssh_cmd[@]}" "cd ${REMOTE_DIR} && timeout 600 docker compose build fluentloop"

echo "==> Run Alembic migrations"
"${ssh_cmd[@]}" "cd ${REMOTE_DIR} && timeout 120 docker compose run --rm fluentloop alembic upgrade head"

echo "==> Start container"
"${ssh_cmd[@]}" "cd ${REMOTE_DIR} && timeout 300 docker compose up -d"

echo "==> Tail logs (15s)"
"${ssh_cmd[@]}" "cd ${REMOTE_DIR} && timeout 15 docker compose logs --tail=50 --follow || true"

echo "==> Done. Smoke-test next: python ${REPO_ROOT}/scripts/smoke_telegram.py"
