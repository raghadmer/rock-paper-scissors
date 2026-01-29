#!/usr/bin/env bash
set -euo pipefail

# Runs spiffe-helper once to fetch SVID+bundle into cert_dir.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/common.sh"

HELPER_BIN="${1:-$HOME/rps/spiffe-helper}"
HELPER_CONF="${2:-$HOME/rps/helper.conf}"
CERT_DIR="${3:-$HOME/rps/certs}"

if [[ ! -x "$HELPER_BIN" ]]; then
	HELPER_BIN="$(ensure_spiffe_helper)"
fi
require_file "$HELPER_CONF"
chmod +x "$HELPER_BIN"

"$HELPER_BIN" -config "$HELPER_CONF" -daemon-mode=false

require_file "$CERT_DIR/svid.pem"
require_file "$CERT_DIR/svid_key.pem"
require_file "$CERT_DIR/svid_bundle.pem"

echo "OK: wrote certs to $CERT_DIR"
ls -la "$CERT_DIR"
