#!/usr/bin/env bash
set -euo pipefail

#
# Usage:
#   ./scripts/demo/demo-all.sh serve
#   PUBLIC_URL=https://<your-ip>:9002 ./scripts/demo/demo-all.sh play <peer_url> <peer_spiffe_id> [move]
#
# This script:
# - sources ~/spire-lab.conf if present
# - generates helper.conf if missing
# - fetches certs via spiffe-helper
# - starts server OR challenges a peer

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

MODE="${1:-}"
shift || true

if [[ -z "$MODE" || "$MODE" == "-h" || "$MODE" == "--help" ]]; then
  cat <<'EOF'
Usage:
  demo-all.sh serve
  demo-all.sh play <peer_url> <peer_spiffe_id> [move]

Env vars (optional):
  REPO_DIR   (default: $HOME/rock-paper-scissors)
  BIND       (default: 0.0.0.0:9002)
  SPIFFE_ID  (default: spiffe://$TRUST_DOMAIN/game-server)
  CERT_DIR   (default: $HOME/rps/certs)
  HELPER_BIN (default: $HOME/rps/spiffe-helper)
  HELPER_CONF(default: $HOME/rps/helper.conf)
  PUBLIC_URL (required for play; callback URL for /response)

Quick start:
  cd ~/rock-paper-scissors
  chmod +x scripts/demo/*.sh
  ./scripts/demo/demo-all.sh serve

  # In another terminal (or after server is running):
  export PUBLIC_URL=https://<your-public-ip>:9002
  ./scripts/demo/demo-all.sh play https://<peer-ip>:9002 spiffe://<peer-domain>/game-server rock
EOF
  exit 0
fi

load_spire_env

REPO_DIR="${REPO_DIR:-$HOME/rock-paper-scissors}"
BIND="${BIND:-0.0.0.0:9002}"
CERT_DIR="${CERT_DIR:-$HOME/rps/certs}"
HELPER_BIN="${HELPER_BIN:-$HOME/rps/spiffe-helper}"
HELPER_CONF="${HELPER_CONF:-$HOME/rps/helper.conf}"
SPIFFE_ID="${SPIFFE_ID:-spiffe://$TRUST_DOMAIN/game-server}"

require_dir "$REPO_DIR"

echo "== Federated RPS demo helper =="
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

case "$MODE" in
  serve)
    echo "Starting server..."
    REPO_DIR="$REPO_DIR" BIND="$BIND" CERT_DIR="$CERT_DIR" SPIFFE_ID="$SPIFFE_ID" \
      "$SCRIPT_DIR/03-serve.sh"
    ;;

  play)
    PEER_URL="${1:-}"
    PEER_SPIFFE_ID="${2:-}"
    MOVE="${3:-rock}"

    if [[ -z "$PEER_URL" || -z "$PEER_SPIFFE_ID" ]]; then
      echo "ERROR: play requires <peer_url> and <peer_spiffe_id>" >&2
      exit 1
    fi
    if [[ -z "${PUBLIC_URL:-}" ]]; then
      echo "ERROR: PUBLIC_URL must be set for play." >&2
      echo "Example: export PUBLIC_URL=https://<your-public-ip>:9002" >&2
      exit 1
    fi

    echo "Challenging peer: $PEER_URL"
    echo "Expected peer ID: $PEER_SPIFFE_ID"

    REPO_DIR="$REPO_DIR" BIND="$BIND" CERT_DIR="$CERT_DIR" SPIFFE_ID="$SPIFFE_ID" PUBLIC_URL="$PUBLIC_URL" \
      "$SCRIPT_DIR/04-play.sh" "$PEER_URL" "$PEER_SPIFFE_ID" "$MOVE"
    ;;

  *)
    echo "ERROR: unknown mode: $MODE (expected: serve|play)" >&2
    exit 1
    ;;
esac
