#!/usr/bin/env bash
set -euo pipefail

# Container entrypoint for the RPS game.
# - Fetches SPIFFE SVIDs using spiffe-helper (if mTLS enabled)
# - Starts the server (default) or play mode

RPS_MODE="${RPS_MODE:-serve}"
RPS_BIND="${RPS_BIND:-0.0.0.0:9002}"
RPS_SPIFFE_ID="${RPS_SPIFFE_ID:-}"
RPS_PEER_URL="${RPS_PEER_URL:-}"
RPS_PEER_ID="${RPS_PEER_ID:-}"
RPS_MOVE="${RPS_MOVE:-rock}"
RPS_PUBLIC_URL="${RPS_PUBLIC_URL:-}"
RPS_MTLS="${RPS_MTLS:-1}"
RPS_CERT_DIR="${RPS_CERT_DIR:-/app/certs}"

SPIFFE_HELPER_CONFIG="${SPIFFE_HELPER_CONFIG:-/app/spiffe-helper.conf}"
SPIFFE_AGENT_SOCKET="${SPIFFE_AGENT_SOCKET:-/tmp/spire-agent/public/api.sock}"

mkdir -p "$RPS_CERT_DIR"

if [[ "$RPS_MTLS" == "1" || "$RPS_MTLS" == "true" ]]; then
  if [[ -z "$RPS_SPIFFE_ID" ]]; then
    echo "ERROR: RPS_SPIFFE_ID is required when RPS_MTLS=1" >&2
    exit 1
  fi

  if [[ ! -f "$SPIFFE_HELPER_CONFIG" ]]; then
    cat >"$SPIFFE_HELPER_CONFIG" <<EOF
agent_address = "$SPIFFE_AGENT_SOCKET"
cmd = ""
cmd_args = ""
cert_dir = "$RPS_CERT_DIR"
svid_file_name = "svid.pem"
svid_key_file_name = "svid_key.pem"
svid_bundle_file_name = "svid_bundle.pem"
EOF
  fi

  # Fetch certs each time (short-lived SVIDs).
  spiffe-helper -config "$SPIFFE_HELPER_CONFIG" -daemon-mode=false

  RPS_MTLS_ARGS=("--mtls" "--cert-dir" "$RPS_CERT_DIR")
else
  RPS_MTLS_ARGS=()
fi

case "$RPS_MODE" in
  serve)
    exec python /app/cli.py serve \
      --bind "$RPS_BIND" \
      --spiffe-id "$RPS_SPIFFE_ID" \
      "${RPS_MTLS_ARGS[@]}"
    ;;
  play)
    if [[ -z "$RPS_PEER_URL" || -z "$RPS_PEER_ID" || -z "$RPS_PUBLIC_URL" ]]; then
      echo "ERROR: RPS_PEER_URL, RPS_PEER_ID, and RPS_PUBLIC_URL are required for play" >&2
      exit 1
    fi
    exec python /app/cli.py play \
      --bind "$RPS_BIND" \
      --public-url "$RPS_PUBLIC_URL" \
      --spiffe-id "$RPS_SPIFFE_ID" \
      --peer "$RPS_PEER_URL" \
      --peer-id "$RPS_PEER_ID" \
      --move "$RPS_MOVE" \
      "${RPS_MTLS_ARGS[@]}"
    ;;
  *)
    echo "ERROR: Unknown RPS_MODE: $RPS_MODE (expected serve|play)" >&2
    exit 1
    ;;
esac
