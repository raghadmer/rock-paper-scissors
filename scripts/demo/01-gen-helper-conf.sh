#!/usr/bin/env bash
set -euo pipefail

# Generates a spiffe-helper config that writes certs to ./certs

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

CERT_DIR="${1:-$HOME/rps/certs}"
HELPER_CONF="${2:-$HOME/rps/helper.conf}"
AGENT_SOCK="${3:-/tmp/spire-agent/public/api.sock}"

mkdir -p "$(dirname "$HELPER_CONF")" "$CERT_DIR"

cat >"$HELPER_CONF" <<EOF
agent_address = "$AGENT_SOCK"
cmd = ""
cmd_args = ""
cert_dir = "$CERT_DIR"
svid_file_name = "svid.pem"
svid_key_file_name = "svid_key.pem"
svid_bundle_file_name = "svid_bundle.pem"
EOF

echo "Wrote $HELPER_CONF"
echo "Certs will be written to $CERT_DIR"
