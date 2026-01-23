#!/bin/bash
# WireGuard bootstrap script
# Sets up WireGuard VPN on target host
# Usage: ./10_wireguard.sh --host HOST [OPTIONS]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"
TEMPLATE_DIR="$SCRIPT_DIR/../../templates"

# Source library functions
source "$LIB_DIR/common.sh"
source "$LIB_DIR/ssh.sh"
source "$LIB_DIR/assert.sh"

show_help() {
    cat <<EOF
Usage: $(basename "$0") --host HOST [OPTIONS]

Sets up WireGuard VPN.

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required)
    --help, -h          Show this help message

EOF
}

install_wireguard() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Installing WireGuard"
    
    ssh_exec_sudo "$host" "$user" "$port" 'export DEBIAN_FRONTEND=noninteractive; if ! command -v wg >/dev/null 2>&1; then apt-get install -y -qq wireguard wireguard-tools; else echo "WireGuard already installed"; fi'
}

generate_wireguard_config() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local wg_ip="$4"
    local private_key="$5"
    local wg_port="${6:-51820}"
    
    log_info "Generating WireGuard configuration"
    
    # Determine which VPS this is
    local peers=""
    if [ "$host" = "${VPS1_HOST:-}" ]; then
        # VPS1 peers: VPS2 and VPS3
        peers="[Peer]
PublicKey = ${VPS2_WIREGUARD_PUBLIC_KEY}
Endpoint = ${VPS2_PUBLIC_IP}:${wg_port}
AllowedIPs = ${VPS2_WIREGUARD_IP}/32

[Peer]
PublicKey = ${VPS3_WIREGUARD_PUBLIC_KEY}
Endpoint = ${VPS3_PUBLIC_IP}:${wg_port}
AllowedIPs = ${VPS3_WIREGUARD_IP}/32"
    elif [ "$host" = "${VPS2_HOST:-}" ]; then
        # VPS2 peers: VPS1 and VPS3
        peers="[Peer]
PublicKey = ${VPS1_WIREGUARD_PUBLIC_KEY}
Endpoint = ${VPS1_PUBLIC_IP}:${wg_port}
AllowedIPs = ${VPS1_WIREGUARD_IP}/32

[Peer]
PublicKey = ${VPS3_WIREGUARD_PUBLIC_KEY}
Endpoint = ${VPS3_PUBLIC_IP}:${wg_port}
AllowedIPs = ${VPS3_WIREGUARD_IP}/32"
    elif [ "$host" = "${VPS3_HOST:-}" ]; then
        # VPS3 peers: VPS1 and VPS2
        peers="[Peer]
PublicKey = ${VPS1_WIREGUARD_PUBLIC_KEY}
Endpoint = ${VPS1_PUBLIC_IP}:${wg_port}
AllowedIPs = ${VPS1_WIREGUARD_IP}/32

[Peer]
PublicKey = ${VPS2_WIREGUARD_PUBLIC_KEY}
Endpoint = ${VPS2_PUBLIC_IP}:${wg_port}
AllowedIPs = ${VPS2_WIREGUARD_IP}/32"
    fi
    
    # Render template
    local template_file="$TEMPLATE_DIR/wireguard/wg0.conf.tmpl"
    
    if [ ! -f "$template_file" ]; then
        log_error "Template file not found: $template_file"
        exit 1
    fi
    
    local config_content=$(cat "$template_file")
    
    # Substitute variables using a safer method (avoid sed special chars)
    config_content=$(echo "$config_content" | python3 -c "
import sys
content = sys.stdin.read()
content = content.replace('\${PRIVATE_KEY}', '$private_key')
content = content.replace('\${WG_IP}', '$wg_ip')
content = content.replace('\${WG_PORT}', '$wg_port')
content = content.replace('\${PEERS}', '''$peers''')
print(content)
" 2>/dev/null || echo "$config_content" | sed "s|\\\${PRIVATE_KEY}|$private_key|g" | sed "s|\\\${WG_IP}|$wg_ip|g" | sed "s|\\\${WG_PORT}|$wg_port|g" | sed "s|\\\${PEERS}|$peers|g")
    
    # Write config to temp file
    local temp_config="/tmp/wg0.conf.$$"
    echo "$config_content" > "$temp_config"
    
    # Copy to remote host
    ssh_copy_file "$host" "$user" "$port" "$temp_config" "/tmp/wg0.conf"
    
    # Move to final location with backup
    ssh_exec_sudo "$host" "$user" "$port" 'if [ -f /etc/wireguard/wg0.conf ]; then cp /etc/wireguard/wg0.conf /etc/wireguard/wg0.conf.backup.$(date +%Y%m%d_%H%M%S); fi; mkdir -p /etc/wireguard; mv /tmp/wg0.conf /etc/wireguard/wg0.conf; chmod 600 /etc/wireguard/wg0.conf'
    
    # Clean up temp file
    rm -f "$temp_config"
}

enable_wireguard() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Enabling WireGuard"
    
    ssh_exec_sudo "$host" "$user" "$port" 'wg-quick down wg0 2>/dev/null || true; wg-quick up wg0; systemctl enable wg-quick@wg0'
}

main() {
    init_script "$@"
    load_inventory
    
    if [ -z "${TARGET_HOST:-}" ]; then
        log_error "Target host not specified. Use --host HOST"
        show_help
        exit 1
    fi
    
    # Determine which VPS this is and get config
    local ssh_user="root"
    local ssh_port="22"
    local wg_ip=""
    local private_key=""
    local wg_port="${WIREGUARD_PORT:-51820}"
    
    if [ "$TARGET_HOST" = "${VPS1_HOST:-}" ]; then
        ssh_user="${VPS1_SSH_USER:-root}"
        ssh_port="${VPS1_SSH_PORT:-22}"
        wg_ip="${VPS1_WIREGUARD_IP:-}"
        private_key="${VPS1_WIREGUARD_PRIVATE_KEY:-}"
    elif [ "$TARGET_HOST" = "${VPS2_HOST:-}" ]; then
        ssh_user="${VPS2_SSH_USER:-root}"
        ssh_port="${VPS2_SSH_PORT:-22}"
        wg_ip="${VPS2_WIREGUARD_IP:-}"
        private_key="${VPS2_WIREGUARD_PRIVATE_KEY:-}"
    elif [ "$TARGET_HOST" = "${VPS3_HOST:-}" ]; then
        ssh_user="${VPS3_SSH_USER:-root}"
        ssh_port="${VPS3_SSH_PORT:-22}"
        wg_ip="${VPS3_WIREGUARD_IP:-}"
        private_key="${VPS3_WIREGUARD_PRIVATE_KEY:-}"
    fi
    
    if [ -z "$wg_ip" ] || [ -z "$private_key" ]; then
        log_error "WireGuard configuration missing for $TARGET_HOST"
        log_error "Check inventory file for WIREGUARD_IP and WIREGUARD_PRIVATE_KEY"
        exit 1
    fi
    
    log_info "Setting up WireGuard on $TARGET_HOST (IP: $wg_ip)"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    # Validate required variables
    validate_required_vars VPS1_WIREGUARD_PUBLIC_KEY VPS2_WIREGUARD_PUBLIC_KEY VPS3_WIREGUARD_PUBLIC_KEY
    validate_required_vars VPS1_PUBLIC_IP VPS2_PUBLIC_IP VPS3_PUBLIC_IP
    
    install_wireguard "$TARGET_HOST" "$ssh_user" "$ssh_port"
    generate_wireguard_config "$TARGET_HOST" "$ssh_user" "$ssh_port" "$wg_ip" "$private_key" "$wg_port"
    enable_wireguard "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    log_success "WireGuard setup completed"
}

main "$@"
