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
  local conf="${1:-$HOME/spire.conf}"
  if [[ -f "$conf" ]]; then
    # shellcheck disable=SC1090
    source "$conf"
  fi
  : "${TRUST_DOMAIN:=${TRUST_DOMAIN:-}}"
  if [[ -z "${TRUST_DOMAIN:-}" ]]; then
    echo "ERROR: TRUST_DOMAIN not set. Create ~/spire.conf or export TRUST_DOMAIN." >&2
    echo "Run:  generate_spire_conf  to create it interactively." >&2
    exit 1
  fi
}

generate_spire_conf() {
  local conf="${1:-$HOME/spire.conf}"
  if [[ -f "$conf" ]]; then
    echo "Config already exists: $conf"
    # shellcheck disable=SC1090
    source "$conf"
    return 0
  fi

  echo "=== Generating $conf ==="
  read -rp "Enter your trust domain (e.g. noah.inter-cloud-thi.de): " td
  if [[ -z "$td" ]]; then
    echo "ERROR: Trust domain cannot be empty." >&2
    return 1
  fi
  read -rp "Enter your player name (e.g. noah): " player
  player="${player:-noah}"

  cat > "$conf" <<CONF
# Auto-generated SPIRE configuration for RPS game
export TRUST_DOMAIN="$td"
export SPIRE_SERVER_BIN="\$HOME/spire-1.13.3/bin/spire-server"
export SERVER_SOCKET="/tmp/spire-server/private/api.sock"
export SPIFFE_ID="spiffe://\$TRUST_DOMAIN/game-server-$player"
export PARENT_ID="spiffe://\$TRUST_DOMAIN/agent"
export CERT_DIR="\$HOME/certs"
CONF

  echo "Created $conf"
  # shellcheck disable=SC1090
  source "$conf"
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
