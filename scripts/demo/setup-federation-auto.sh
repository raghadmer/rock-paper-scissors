#!/usr/bin/env bash
set -euo pipefail

# Automated federation setup using the peer's SPIRE bundle endpoint (port 8443).
#
# This replaces the manual "copy-paste JSON bundle" workflow.
# Both sides must have the bundle_endpoint block in their server.conf.
#
# Usage:
#   ./setup-federation-auto.sh <peer_trust_domain> <peer_ip_or_hostname>
#
# Examples:
#   ./setup-federation-auto.sh raghad.inter-cloud-thi.de 4.185.211.9
#   ./setup-federation-auto.sh sven.inter-cloud-thi.de  4.185.210.163

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_spire_env

PEER_DOMAIN="${1:-}"
PEER_ADDR="${2:-}"

if [[ -z "$PEER_DOMAIN" || -z "$PEER_ADDR" ]]; then
  echo "Usage: $0 <peer_trust_domain> <peer_ip_or_hostname>" >&2
  echo "  e.g. $0 raghad.inter-cloud-thi.de 4.185.211.9" >&2
  exit 1
fi

SPIRE_BIN="${SPIRE_SERVER_BIN:-$HOME/spire-1.13.3/bin/spire-server}"

if [[ ! -x "$SPIRE_BIN" ]]; then
  echo "ERROR: spire-server not found at $SPIRE_BIN" >&2
  exit 1
fi

BUNDLE_FILE="/tmp/${PEER_DOMAIN}.bundle"
BUNDLE_ENDPOINT="https://${PEER_ADDR}:8443"

# ── Step 1: Fetch the peer's trust bundle from their bundle endpoint ──
echo "== Fetching bundle from $BUNDLE_ENDPOINT =="
if ! curl -sk --connect-timeout 5 "$BUNDLE_ENDPOINT" -o "$BUNDLE_FILE"; then
  echo "ERROR: Could not reach $BUNDLE_ENDPOINT" >&2
  echo "Check that the peer's SPIRE server is running and port 8443 is open." >&2
  exit 1
fi

# Sanity check: the file should be valid JSON with keys
if ! jq -e '.keys' "$BUNDLE_FILE" >/dev/null 2>&1; then
  echo "ERROR: Bundle from $BUNDLE_ENDPOINT does not look valid:" >&2
  head -5 "$BUNDLE_FILE" >&2
  exit 1
fi

echo "  Bundle saved to $BUNDLE_FILE"
echo "  Keys in bundle: $(jq '.keys | length' "$BUNDLE_FILE")"

# ── Step 2: Import the bundle into our SPIRE server ───────────────────
echo
echo "== Importing bundle for spiffe://$PEER_DOMAIN =="
sudo "$SPIRE_BIN" bundle set \
  -format spiffe \
  -id "spiffe://$PEER_DOMAIN" \
  -path "$BUNDLE_FILE"

# ── Step 3: Set up automatic refresh via federation relationship ──────
echo
echo "== Creating federation relationship (auto-refresh) =="
# Try create first; if it already exists, fall back to update.
if ! sudo "$SPIRE_BIN" federation create \
  -trustDomain "$PEER_DOMAIN" \
  -bundleEndpointURL "$BUNDLE_ENDPOINT" \
  -bundleEndpointProfile https_spiffe \
  -endpointSpiffeID "spiffe://$PEER_DOMAIN/spire/server" \
  -trustDomainBundlePath "$BUNDLE_FILE" \
  -trustDomainBundleFormat spiffe 2>/dev/null; then

  echo "  (already exists — updating)"
  sudo "$SPIRE_BIN" federation update \
    -trustDomain "$PEER_DOMAIN" \
    -bundleEndpointURL "$BUNDLE_ENDPOINT" \
    -bundleEndpointProfile https_spiffe \
    -endpointSpiffeID "spiffe://$PEER_DOMAIN/spire/server" \
    -trustDomainBundlePath "$BUNDLE_FILE" \
    -trustDomainBundleFormat spiffe
fi

# ── Step 4: Verify ────────────────────────────────────────────────────
echo
echo "== Federation list =="
sudo "$SPIRE_BIN" federation list

echo
echo "== Done =="
echo "Peer $PEER_DOMAIN imported and auto-refresh enabled via $BUNDLE_ENDPOINT."
echo
echo "Next steps:"
echo "  1. Make sure your workload entry includes: -federatesWith spiffe://$PEER_DOMAIN"
echo "  2. Re-fetch certs:  ~/spire-1.13.3/bin/spire-agent api fetch x509 -write ~/certs/"
echo "  3. Combine bundles: cat ~/certs/bundle.0.pem ~/certs/federated_bundle.*.pem > ~/certs/svid_bundle.pem"
echo "  4. Restart the game (it loads certs once at startup)"
