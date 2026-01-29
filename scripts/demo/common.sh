#!/usr/bin/env bash
set -euo pipefail

# Shared helpers for VM demo scripts.

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: missing required command: $1" >&2
    exit 1
  }
}

require_file() {
  [[ -f "$1" ]] || {
    echo "ERROR: missing file: $1" >&2
    exit 1
  }
}

require_dir() {
  [[ -d "$1" ]] || {
    echo "ERROR: missing directory: $1" >&2
    exit 1
  }
}

# Load lab environment variables if present.
load_spire_env() {
  local conf="${1:-$HOME/spire-lab.conf}"
  if [[ -f "$conf" ]]; then
    # shellcheck disable=SC1090
    source "$conf"
  fi
  : "${TRUST_DOMAIN:=${TRUST_DOMAIN:-}}"
  if [[ -z "${TRUST_DOMAIN:-}" ]]; then
    echo "ERROR: TRUST_DOMAIN not set. Source ~/spire-lab.conf or export TRUST_DOMAIN." >&2
    exit 1
  fi
}

python_bin() {
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
  else
    echo "python"
  fi
}
