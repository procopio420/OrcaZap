#!/bin/bash
# Generate WireGuard keys on all servers via SSH
# Usage: ./setup_all_wireguard_keys.sh
# Requires: SSH_PRIVATE_KEY and INVENTORY_FILE environment variables

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"
KEYGEN_SCRIPT="$SCRIPT_DIR/generate_wireguard_keys.sh"

# Source library functions
source "$LIB_DIR/common.sh"
source "$LIB_DIR/ssh.sh"
source "$LIB_DIR/assert.sh"

show_help() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Generates WireGuard keys on all three VPS servers and collects them.

Options:
    --dry-run           Show what would be done without making changes
    --output FILE       Output file for collected keys (default: wireguard-keys.env)
    --help, -h          Show this help message

EOF
}

generate_keys_on_server() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local vps_name="$4"
    
    log_info "Generating WireGuard keys on $vps_name ($host)"
    
    # Copy key generation script to remote server
    ssh_copy_file "$host" "$user" "$port" "$KEYGEN_SCRIPT" "/tmp/generate_wireguard_keys.sh"
    
    # Make it executable and run it
    ssh_exec_sudo "$host" "$user" "$port" "
        chmod +x /tmp/generate_wireguard_keys.sh
        /tmp/generate_wireguard_keys.sh /tmp/wireguard-keys-$vps_name
    "
    
    # Retrieve the keys
    local temp_dir="/tmp/wireguard-keys-$vps_name-$$"
    mkdir -p "$temp_dir"
    
    ssh_copy_file "$host" "$user" "$port" "/tmp/wireguard-keys-$vps_name/privatekey" "$temp_dir/privatekey"
    ssh_copy_file "$host" "$user" "$port" "/tmp/wireguard-keys-$vps_name/publickey" "$temp_dir/publickey"
    
    # Read keys
    local private_key=$(cat "$temp_dir/privatekey")
    local public_key=$(cat "$temp_dir/publickey")
    
    # Clean up
    rm -rf "$temp_dir"
    ssh_exec_sudo "$host" "$user" "$port" "
        rm -rf /tmp/wireguard-keys-$vps_name
        rm -f /tmp/generate_wireguard_keys.sh
    " || true
    
    echo "$private_key|$public_key"
}

collect_keys() {
    local output_file="${1:-wireguard-keys.env}"
    
    log_info "Collecting WireGuard keys from all servers"
    
    # Generate keys on each server
    local vps1_keys=$(generate_keys_on_server "$VPS1_HOST" "${VPS1_SSH_USER:-root}" "${VPS1_SSH_PORT:-22}" "VPS1")
    local vps2_keys=$(generate_keys_on_server "$VPS2_HOST" "${VPS2_SSH_USER:-root}" "${VPS2_SSH_PORT:-22}" "VPS2")
    local vps3_keys=$(generate_keys_on_server "$VPS3_HOST" "${VPS3_SSH_USER:-root}" "${VPS3_SSH_PORT:-22}" "VPS3")
    
    # Parse keys
    local vps1_private=$(echo "$vps1_keys" | cut -d'|' -f1)
    local vps1_public=$(echo "$vps1_keys" | cut -d'|' -f2)
    local vps2_private=$(echo "$vps2_keys" | cut -d'|' -f1)
    local vps2_public=$(echo "$vps2_keys" | cut -d'|' -f2)
    local vps3_private=$(echo "$vps3_keys" | cut -d'|' -f1)
    local vps3_public=$(echo "$vps3_keys" | cut -d'|' -f2)
    
    # Write to output file
    cat > "$output_file" <<EOF
# WireGuard Keys - Generated $(date)
# DO NOT COMMIT THIS FILE TO GIT

# VPS1 (APP) WireGuard Keys
VPS1_WIREGUARD_PRIVATE_KEY=$vps1_private
VPS1_WIREGUARD_PUBLIC_KEY=$vps1_public

# VPS2 (DATA) WireGuard Keys
VPS2_WIREGUARD_PRIVATE_KEY=$vps2_private
VPS2_WIREGUARD_PUBLIC_KEY=$vps2_public

# VPS3 (WORKER) WireGuard Keys
VPS3_WIREGUARD_PRIVATE_KEY=$vps3_private
VPS3_WIREGUARD_PUBLIC_KEY=$vps3_public
EOF
    
    log_success "Keys collected and saved to $output_file"
    log_info "You can now merge these keys into your hosts.env file"
}

main() {
    init_script "$@"
    load_inventory
    
    # Parse output file argument
    local output_file="wireguard-keys.env"
    for arg in "$@"; do
        if [[ $arg == --output=* ]]; then
            output_file="${arg#*=}"
        fi
    done
    
    # Validate required variables
    validate_required_vars VPS1_HOST VPS2_HOST VPS3_HOST
    
    # Assert SSH connections
    assert_ssh_connection "$VPS1_HOST" "${VPS1_SSH_USER:-root}" "${VPS1_SSH_PORT:-22}"
    assert_ssh_connection "$VPS2_HOST" "${VPS2_SSH_USER:-root}" "${VPS2_SSH_PORT:-22}"
    assert_ssh_connection "$VPS3_HOST" "${VPS3_SSH_USER:-root}" "${VPS3_SSH_PORT:-22}"
    
    collect_keys "$output_file"
    
    log_success "WireGuard key generation completed"
    log_info "Next step: Merge keys from $output_file into infra/inventory/hosts.env"
}

main "$@"


