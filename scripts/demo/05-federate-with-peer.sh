#!/usr/bin/env bash
set -euo pipefail

# Creates a SPIRE federation relationship to a peer trust domain.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

load_spire_env

SPIRE_SERVER_BIN="${SPIRE_SERVER_BIN:-/opt/spire/bin/spire-server}"
SERVER_SOCKET="${SERVER_SOCKET:-/tmp/spire-server/private/api.sock}"

PEER_TRUST_DOMAIN="${1:-}"
PEER_BUNDLE_ENDPOINT_URL="${2:-}"
PEER_ENDPOINT_SPIFFE_ID="${3:-}"
PEER_BUNDLE_JSON="${4:-}"

if [[ -z "$PEER_TRUST_DOMAIN" || -z "$PEER_BUNDLE_ENDPOINT_URL" || -z "$PEER_ENDPOINT_SPIFFE_ID" || -z "$PEER_BUNDLE_JSON" ]]; then
  echo "Usage: $0 <peer_trust_domain> <peer_bundle_endpoint_url> <peer_endpoint_spiffe_id> <peer_bundle_json_file>" >&2
  echo "Example: $0 bob.inter-cloud-thi.de https://bob.inter-cloud-thi.de:8443 spiffe://bob.inter-cloud-thi.de/spire/server /tmp/bob.bundle" >&2
  exit 1
fi

require_file "$SPIRE_SERVER_BIN"
require_file "$PEER_BUNDLE_JSON"

sudo "$SPIRE_SERVER_BIN" federation create \
  -socketPath "$SERVER_SOCKET" \
  -trustDomain "$PEER_TRUST_DOMAIN" \
  -bundleEndpointURL "$PEER_BUNDLE_ENDPOINT_URL" \
  -bundleEndpointProfile https_spiffe \
  -endpointSpiffeID "$PEER_ENDPOINT_SPIFFE_ID" \
  -trustDomainBundlePath "$PEER_BUNDLE_JSON" \
  -trustDomainBundleFormat spiffe

sudo "$SPIRE_SERVER_BIN" federation list -socketPath "$SERVER_SOCKET"
