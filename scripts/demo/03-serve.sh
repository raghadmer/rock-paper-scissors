#!/usr/bin/env bash
set -euo pipefail

# Starts the game server in SPIFFE mTLS mode.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_spire_env

REPO_DIR="${REPO_DIR:-$HOME/rock-paper-scissors}"
BIND="${BIND:-0.0.0.0:9002}"
CERT_DIR="${CERT_DIR:-$HOME/rps/certs}"
SPIFFE_ID="${SPIFFE_ID:-spiffe://$TRUST_DOMAIN/game-server}"

require_dir "$REPO_DIR"
require_dir "$CERT_DIR"

cd "$REPO_DIR"
PY="$(python_bin)"

exec "$PY" src/app/cli.py serve \
  --bind "$BIND" \
  --spiffe-id "$SPIFFE_ID" \
  --mtls --cert-dir "$CERT_DIR"
