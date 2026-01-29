#!/usr/bin/env bash
set -euo pipefail

# Pre-demo health checks for the VM environment.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_spire_env

SPIRE_SERVER_BIN="${SPIRE_SERVER_BIN:-/opt/spire/bin/spire-server}"
SPIFFE_AGENT_SOCKET="${SPIFFE_AGENT_SOCKET:-/tmp/spire-agent/public/api.sock}"
BUNDLE_ENDPOINT="${BUNDLE_ENDPOINT:-https://${TRUST_DOMAIN}:8443}"
RPS_PORT="${RPS_PORT:-9002}"

GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
NC="\033[0m"

ok() { echo -e "${GREEN}OK${NC} $*"; }
warn() { echo -e "${YELLOW}WARN${NC} $*"; }
fail() { echo -e "${RED}FAIL${NC} $*"; }

require_cmd curl

# SPIRE server binary
if [[ -x "$SPIRE_SERVER_BIN" ]]; then
  ok "SPIRE server binary found: $SPIRE_SERVER_BIN"
else
  fail "SPIRE server binary not found: $SPIRE_SERVER_BIN"
fi

# Workload API socket
if [[ -S "$SPIFFE_AGENT_SOCKET" ]]; then
  ok "SPIRE Workload API socket: $SPIFFE_AGENT_SOCKET"
else
  fail "SPIRE Workload API socket missing: $SPIFFE_AGENT_SOCKET"
fi

# Bundle endpoint reachability
if curl -kfsS --max-time 5 "$BUNDLE_ENDPOINT" >/dev/null; then
  ok "Bundle endpoint reachable: $BUNDLE_ENDPOINT"
else
  warn "Bundle endpoint not reachable: $BUNDLE_ENDPOINT"
fi

# Ports (best-effort)
if command -v ss >/dev/null 2>&1; then
  if ss -tln | awk '{print $4}' | grep -q ":$RPS_PORT$"; then
    ok "Port $RPS_PORT is listening"
  else
    warn "Port $RPS_PORT not listening yet (start server/container)"
  fi
else
  warn "ss not available; skipped port check"
fi

# Certs (if present)
CERT_DIR="${CERT_DIR:-$HOME/rps/certs}"
if [[ -f "$CERT_DIR/svid.pem" && -f "$CERT_DIR/svid_key.pem" && -f "$CERT_DIR/svid_bundle.pem" ]]; then
  ok "SPIFFE certs present in $CERT_DIR"
else
  warn "SPIFFE certs not found in $CERT_DIR (run 02-fetch-certs.sh or container)"
fi

echo
ok "Healthcheck complete"
