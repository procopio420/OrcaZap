#!/bin/bash
# Merge WireGuard keys from wireguard-keys.env into hosts.env
# Usage: ./merge_keys.sh [wireguard-keys.env] [hosts.env]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEYS_FILE="${1:-wireguard-keys.env}"
HOSTS_FILE="${2:-$SCRIPT_DIR/../../inventory/hosts.env}"

if [ ! -f "$KEYS_FILE" ]; then
    echo "Error: Keys file not found: $KEYS_FILE"
    exit 1
fi

if [ ! -f "$HOSTS_FILE" ]; then
    echo "Error: Hosts file not found: $HOSTS_FILE"
    exit 1
fi

echo "Merging keys from $KEYS_FILE into $HOSTS_FILE"

# Source the keys file
set -a
source "$KEYS_FILE"
set +a

# Update hosts.env with actual keys
sed -i "s|VPS1_WIREGUARD_PRIVATE_KEY=.*|VPS1_WIREGUARD_PRIVATE_KEY=$VPS1_WIREGUARD_PRIVATE_KEY|" "$HOSTS_FILE"
sed -i "s|VPS1_WIREGUARD_PUBLIC_KEY=.*|VPS1_WIREGUARD_PUBLIC_KEY=$VPS1_WIREGUARD_PUBLIC_KEY|" "$HOSTS_FILE"
sed -i "s|VPS2_WIREGUARD_PRIVATE_KEY=.*|VPS2_WIREGUARD_PRIVATE_KEY=$VPS2_WIREGUARD_PRIVATE_KEY|" "$HOSTS_FILE"
sed -i "s|VPS2_WIREGUARD_PUBLIC_KEY=.*|VPS2_WIREGUARD_PUBLIC_KEY=$VPS2_WIREGUARD_PUBLIC_KEY|" "$HOSTS_FILE"
sed -i "s|VPS3_WIREGUARD_PRIVATE_KEY=.*|VPS3_WIREGUARD_PRIVATE_KEY=$VPS3_WIREGUARD_PRIVATE_KEY|" "$HOSTS_FILE"
sed -i "s|VPS3_WIREGUARD_PUBLIC_KEY=.*|VPS3_WIREGUARD_PUBLIC_KEY=$VPS3_WIREGUARD_PUBLIC_KEY|" "$HOSTS_FILE"

echo "✅ Keys merged successfully into $HOSTS_FILE"


