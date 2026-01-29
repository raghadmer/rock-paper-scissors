#!/usr/bin/env bash
set -euo pipefail

# Registers the game workload identity in SPIRE.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/_common.sh"

load_spire_env

SPIRE_SERVER_BIN="${SPIRE_SERVER_BIN:-/opt/spire/bin/spire-server}"
SERVER_SOCKET="${SERVER_SOCKET:-/tmp/spire-server/private/api.sock}"

SPIFFE_ID="${SPIFFE_ID:-spiffe://$TRUST_DOMAIN/game-server}"
PARENT_ID="${PARENT_ID:-spiffe://$TRUST_DOMAIN/agent}"
SELECTOR_UID="${SELECTOR_UID:-$(id -u)}"
SELECTOR_PATH="${SELECTOR_PATH:-/usr/local/bin/spiffe-helper}"
SVID_TTL="${SVID_TTL:-300}"

if [[ ! -x "$SPIRE_SERVER_BIN" ]]; then
  echo "ERROR: spire-server not found at $SPIRE_SERVER_BIN" >&2
  exit 1
fi

sudo "$SPIRE_SERVER_BIN" entry create \
  -socketPath "$SERVER_SOCKET" \
  -spiffeID "$SPIFFE_ID" \
  -parentID "$PARENT_ID" \
  -selector "unix:uid:$SELECTOR_UID" \
  -selector "unix:path:$SELECTOR_PATH" \
  -x509SVIDTTL "$SVID_TTL"

sudo "$SPIRE_SERVER_BIN" entry show -socketPath "$SERVER_SOCKET" | grep -A8 -B2 "$SPIFFE_ID" || true

echo "Registered: $SPIFFE_ID"
