#!/usr/bin/env bash
set -euo pipefail

# Challenges a peer and plays until someone wins (ties auto-replay).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_common.sh"

load_spire_env

REPO_DIR="${REPO_DIR:-$HOME/rock-paper-scissors}"
BIND="${BIND:-0.0.0.0:9002}"
CERT_DIR="${CERT_DIR:-$HOME/rps/certs}"
SPIFFE_ID="${SPIFFE_ID:-spiffe://$TRUST_DOMAIN/game-server}"

PEER_URL="${1:-}"
PEER_SPIFFE_ID="${2:-}"
MOVE="${3:-rock}"
PUBLIC_URL="${PUBLIC_URL:-}"

if [[ -z "$PEER_URL" || -z "$PEER_SPIFFE_ID" ]]; then
  echo "Usage: $0 <peer_url> <peer_spiffe_id> [move]" >&2
  echo "Example: $0 https://1.2.3.4:9002 spiffe://alice.inter-cloud-thi.de/game-server rock" >&2
  exit 1
fi

if [[ -z "${PUBLIC_URL}" ]]; then
  echo "ERROR: PUBLIC_URL must be set (peer needs callback for /response)." >&2
  echo "Example: export PUBLIC_URL=https://<your-public-ip>:9002" >&2
  exit 1
fi

require_dir "$REPO_DIR"
require_dir "$CERT_DIR"

cd "$REPO_DIR"
PY="$(python_bin)"

exec "$PY" src/app/cli.py play \
  --bind "$BIND" \
  --public-url "$PUBLIC_URL" \
  --spiffe-id "$SPIFFE_ID" \
  --peer "$PEER_URL" \
  --peer-id "$PEER_SPIFFE_ID" \
  --move "$MOVE" \
  --mtls --cert-dir "$CERT_DIR"
