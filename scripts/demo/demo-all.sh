#!/usr/bin/env bash
set -euo pipefail

#
# Usage:
#   ./scripts/demo/demo-all.sh
#
# This script:
# - sources ~/spire.conf (auto-generates if missing)
# - generates helper.conf if missing
# - fetches certs via spiffe-helper
# - launches the unified interactive RPS CLI
#
# Once the rps> prompt appears, use:
#   challenge <peer_url> <peer_spiffe_id>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Usage:
  demo-all.sh

Env vars (optional):
  REPO_DIR    (default: $HOME/rock-paper-scissors)
  BIND        (default: 0.0.0.0:9002)
  SPIFFE_ID   (default: spiffe://$TRUST_DOMAIN/game-server-noah)
  CERT_DIR    (default: $HOME/rps/certs)
  HELPER_BIN  (default: $HOME/rps/spiffe-helper)
  HELPER_CONF (default: $HOME/rps/helper.conf)
  PUBLIC_URL  (optional; advertised callback URL)

Quick start:
  cd ~/rock-paper-scissors
  chmod +x scripts/demo/*.sh
  ./scripts/demo/demo-all.sh

  # At the rps> prompt, challenge a peer:
  rps> challenge https://<peer-ip>:9002 spiffe://<peer-domain>/game-server-noah
EOF
  exit 0
fi

load_spire_env

REPO_DIR="${REPO_DIR:-$HOME/rock-paper-scissors}"
BIND="${BIND:-0.0.0.0:9002}"
CERT_DIR="${CERT_DIR:-$HOME/rps/certs}"
HELPER_BIN="${HELPER_BIN:-$HOME/rps/spiffe-helper}"
HELPER_CONF="${HELPER_CONF:-$HOME/rps/helper.conf}"
SPIFFE_ID="${SPIFFE_ID:-spiffe://$TRUST_DOMAIN/game-server-noah}"

require_dir "$REPO_DIR"

echo "== Federated RPS demo =="
echo "TRUST_DOMAIN: $TRUST_DOMAIN"
echo "SPIFFE_ID:    $SPIFFE_ID"
echo "BIND:         $BIND"
echo "CERT_DIR:     $CERT_DIR"

# Ensure helper.conf exists (but don't overwrite if user customized it).
if [[ ! -f "$HELPER_CONF" ]]; then
  echo "helper.conf not found; generating: $HELPER_CONF"
  "$SCRIPT_DIR/01-gen-helper-conf.sh" "$CERT_DIR" "$HELPER_CONF"
fi

# Ensure certs are present/updated.
if [[ ! -f "$CERT_DIR/svid.pem" || ! -f "$CERT_DIR/svid_key.pem" || ! -f "$CERT_DIR/svid_bundle.pem" ]]; then
  echo "Certs not found; fetching via spiffe-helper"
  "$SCRIPT_DIR/02-fetch-certs.sh" "$HELPER_BIN" "$HELPER_CONF" "$CERT_DIR"
else
  echo "Certs already exist. If you just changed federation, re-run:"
  echo "  $SCRIPT_DIR/02-fetch-certs.sh"
fi

echo
echo "Launching interactive RPS CLI..."
echo "Use 'challenge <peer_url> <peer_spiffe_id>' at the rps> prompt to play."
echo

REPO_DIR="$REPO_DIR" BIND="$BIND" CERT_DIR="$CERT_DIR" SPIFFE_ID="$SPIFFE_ID" \
  "$SCRIPT_DIR/03-serve.sh"
