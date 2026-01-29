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

ensure_spiffe_helper() {
  local version="${SPIFFE_HELPER_VERSION:-0.11.0}"
  local dir="${SPIFFE_HELPER_DIR:-$HOME/rps}"
  local bin="$dir/spiffe-helper"

  if [[ -x "$bin" ]]; then
    echo "$bin"
    return 0
  fi

  mkdir -p "$dir"

  if command -v wget >/dev/null 2>&1; then
    wget -q -O "$dir/spiffe-helper.tgz" \
      "https://github.com/spiffe/spiffe-helper/releases/download/v${version}/spiffe-helper_v${version}_Linux-x86_64.tar.gz"
  elif command -v curl >/dev/null 2>&1; then
    curl -sSL -o "$dir/spiffe-helper.tgz" \
      "https://github.com/spiffe/spiffe-helper/releases/download/v${version}/spiffe-helper_v${version}_Linux-x86_64.tar.gz"
  else
    echo "ERROR: missing wget or curl to download spiffe-helper" >&2
    exit 1
  fi

  tar -xzf "$dir/spiffe-helper.tgz" -C "$dir"
  chmod +x "$bin"
  rm -f "$dir/spiffe-helper.tgz"

  echo "$bin"
}

python_bin() {
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
  else
    echo "python"
  fi
}
