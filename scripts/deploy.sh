#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy.sh [ssh-host]

Defaults:
  ssh-host:    sh.ydx.ru1
  REMOTE_DIR:  /home/stasrised/shredder-node-monitor

Environment overrides:
  REMOTE_DIR=/path/on/server
  SSH_KEY_SOURCE=~/.ssh/id_ed25519
  SSH_CONFIG_SOURCE=~/.ssh/config
  DOCKER_COMPOSE="docker compose"
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

REMOTE_HOST="${1:-sh.ydx.ru1}"
REMOTE_DIR="${REMOTE_DIR:-/home/stasrised/shredder-node-monitor}"
SSH_KEY_SOURCE="${SSH_KEY_SOURCE:-$HOME/.ssh/id_ed25519}"
SSH_CONFIG_SOURCE="${SSH_CONFIG_SOURCE:-$HOME/.ssh/config}"
DOCKER_COMPOSE="${DOCKER_COMPOSE:-docker compose}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

die() {
  echo "ERROR: $*" >&2
  exit 1
}

[[ -f "$ROOT_DIR/.env" ]] || die "$ROOT_DIR/.env not found"
[[ -f "$ROOT_DIR/nodes.yaml" ]] || die "$ROOT_DIR/nodes.yaml not found"
[[ -f "$SSH_KEY_SOURCE" ]] || die "$SSH_KEY_SOURCE not found"
[[ -f "$SSH_KEY_SOURCE.pub" ]] || die "$SSH_KEY_SOURCE.pub not found"
[[ -f "$SSH_CONFIG_SOURCE" ]] || die "$SSH_CONFIG_SOURCE not found"

echo "[deploy] target: $REMOTE_HOST:$REMOTE_DIR"
ssh "$REMOTE_HOST" "mkdir -p '$REMOTE_DIR/ssh'"

echo "[deploy] syncing project files"
rsync -az --delete \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude '.env' \
  --exclude 'nodes.yaml' \
  --exclude 'ssh/' \
  "$ROOT_DIR/" "$REMOTE_HOST:$REMOTE_DIR/"

echo "[deploy] uploading local env, node overrides and ssh key"
scp "$ROOT_DIR/.env" "$REMOTE_HOST:$REMOTE_DIR/.env"
scp "$ROOT_DIR/nodes.yaml" "$REMOTE_HOST:$REMOTE_DIR/nodes.yaml"
scp "$SSH_KEY_SOURCE" "$REMOTE_HOST:$REMOTE_DIR/ssh/id_ed25519"
scp "$SSH_KEY_SOURCE.pub" "$REMOTE_HOST:$REMOTE_DIR/ssh/id_ed25519.pub"
scp "$SSH_CONFIG_SOURCE" "$REMOTE_HOST:$REMOTE_DIR/ssh/config"

ssh "$REMOTE_HOST" "chmod 700 '$REMOTE_DIR/ssh' && chmod 600 '$REMOTE_DIR/ssh/id_ed25519' '$REMOTE_DIR/ssh/config' && chmod 644 '$REMOTE_DIR/ssh/id_ed25519.pub'"

echo "[deploy] building and starting container"
ssh "$REMOTE_HOST" "cd '$REMOTE_DIR' && $DOCKER_COMPOSE up -d --build"

echo "[deploy] done"
echo "ssh $REMOTE_HOST \"cd '$REMOTE_DIR' && $DOCKER_COMPOSE logs -f --tail=100\""
