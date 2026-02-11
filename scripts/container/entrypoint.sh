#!/usr/bin/env bash
set -euo pipefail

# Container entrypoint for the RPS game.
# Uses pre-generated SPIFFE certs mounted into the container.

RPS_BIND="${RPS_BIND:-0.0.0.0:9002}"
RPS_SPIFFE_ID="${RPS_SPIFFE_ID:-}"
RPS_PUBLIC_URL="${RPS_PUBLIC_URL:-}"
RPS_MTLS="${RPS_MTLS:-1}"
RPS_CERT_DIR="${RPS_CERT_DIR:-/app/certs}"

if [[ "$RPS_MTLS" == "1" || "$RPS_MTLS" == "true" ]]; then
  if [[ -z "$RPS_SPIFFE_ID" ]]; then
    echo "ERROR: RPS_SPIFFE_ID is required when RPS_MTLS=1" >&2
    exit 1
  fi
  if [[ ! -f "$RPS_CERT_DIR/svid.pem" || ! -f "$RPS_CERT_DIR/svid_key.pem" || ! -f "$RPS_CERT_DIR/svid_bundle.pem" ]]; then
    echo "ERROR: SPIFFE certs not found in $RPS_CERT_DIR" >&2
    echo "Generate them on the VM first and mount the certs directory." >&2
    exit 1
  fi
  RPS_MTLS_ARGS=("--mtls" "--cert-dir" "$RPS_CERT_DIR")
else
  RPS_MTLS_ARGS=()
fi

CMD_ARGS=(
  "--bind" "$RPS_BIND"
  "--spiffe-id" "$RPS_SPIFFE_ID"
)

if [[ -n "$RPS_PUBLIC_URL" ]]; then
  CMD_ARGS+=("--public-url" "$RPS_PUBLIC_URL")
fi

# ACME / Let's Encrypt public scoreboard (WebPKI)
RPS_ACME_CERT="${RPS_ACME_CERT:-}"
RPS_ACME_KEY="${RPS_ACME_KEY:-}"
RPS_ACME_BIND="${RPS_ACME_BIND:-0.0.0.0:443}"
RPS_SIGN_MOVES="${RPS_SIGN_MOVES:-}"

if [[ -n "$RPS_ACME_CERT" && -n "$RPS_ACME_KEY" ]]; then
  CMD_ARGS+=("--acme-cert" "$RPS_ACME_CERT" "--acme-key" "$RPS_ACME_KEY" "--acme-bind" "$RPS_ACME_BIND")
fi

if [[ "$RPS_SIGN_MOVES" == "1" || "$RPS_SIGN_MOVES" == "true" ]]; then
  CMD_ARGS+=("--sign-moves")
fi

exec python /app/cli.py "${CMD_ARGS[@]}" "${RPS_MTLS_ARGS[@]}"
