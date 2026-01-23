#!/bin/bash
# Generate WireGuard keys on a server
# Usage: ./generate_wireguard_keys.sh [output_dir]
# Output: Creates privatekey and publickey files

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"

# Source library functions if available
if [ -f "$LIB_DIR/common.sh" ]; then
    source "$LIB_DIR/common.sh"
else
    # Minimal logging if common.sh not available
    log_info() { echo "[INFO] $*"; }
    log_success() { echo "[SUCCESS] $*"; }
    log_error() { echo "[ERROR] $*" >&2; }
fi

OUTPUT_DIR="${1:-/tmp/wireguard-keys}"
HOSTNAME=$(hostname)

log_info "Generating WireGuard keys for $HOSTNAME"
log_info "Output directory: $OUTPUT_DIR"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check if wireguard-tools is installed
if ! command -v wg >/dev/null 2>&1; then
    log_error "WireGuard tools not found. Installing..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq wireguard-tools
fi

# Generate private key
PRIVATE_KEY=$(wg genkey)
PUBLIC_KEY=$(echo "$PRIVATE_KEY" | wg pubkey)

# Save keys
echo "$PRIVATE_KEY" > "$OUTPUT_DIR/privatekey"
echo "$PUBLIC_KEY" > "$OUTPUT_DIR/publickey"

# Set secure permissions
chmod 600 "$OUTPUT_DIR/privatekey"
chmod 644 "$OUTPUT_DIR/publickey"

log_success "Keys generated successfully:"
echo ""
echo "Private Key:"
cat "$OUTPUT_DIR/privatekey"
echo ""
echo "Public Key:"
cat "$OUTPUT_DIR/publickey"
echo ""
echo "Files saved to:"
echo "  Private: $OUTPUT_DIR/privatekey"
echo "  Public:  $OUTPUT_DIR/publickey"
echo ""
log_info "Copy these keys to your inventory file (hosts.env)"


