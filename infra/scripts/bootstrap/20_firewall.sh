#!/bin/bash
# Firewall bootstrap script
# Configures UFW firewall rules
# Usage: ./20_firewall.sh --host HOST [OPTIONS]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"

# Source library functions
source "$LIB_DIR/common.sh"
source "$LIB_DIR/ssh.sh"
source "$LIB_DIR/assert.sh"

show_help() {
    cat <<EOF
Usage: $(basename "$0") --host HOST [OPTIONS]

Configures UFW firewall rules.

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required)
    --help, -h          Show this help message

EOF
}

configure_firewall_vps1() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Configuring firewall for VPS1 (APP)"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        # Reset UFW to defaults (if not already configured)
        ufw --force reset || true
        
        # Default policies
        ufw default deny incoming
        ufw default allow outgoing
        
        # SSH
        ufw allow ${port}/tcp comment 'SSH'
        
        # HTTP/HTTPS
        ufw allow 80/tcp comment 'HTTP'
        ufw allow 443/tcp comment 'HTTPS'
        
        # WireGuard
        ufw allow ${WIREGUARD_PORT:-51820}/udp comment 'WireGuard'
        
        # PostgreSQL via PgBouncer (from WireGuard network)
        ufw allow from 10.10.0.0/24 to any port 6432 comment 'PgBouncer'
        
        # Enable firewall
        ufw --force enable
    "
}

configure_firewall_vps2() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Configuring firewall for VPS2 (DATA)"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        # Reset UFW to defaults (if not already configured)
        ufw --force reset || true
        
        # Default policies
        ufw default deny incoming
        ufw default allow outgoing
        
        # SSH
        ufw allow ${port}/tcp comment 'SSH'
        
        # WireGuard
        ufw allow ${WIREGUARD_PORT:-51820}/udp comment 'WireGuard'
        
        # PostgreSQL (from VPS1 and VPS3 via WireGuard)
        ufw allow from ${VPS1_WIREGUARD_IP:-10.10.0.1} to any port 5432 comment 'PostgreSQL from VPS1'
        ufw allow from ${VPS3_WIREGUARD_IP:-10.10.0.3} to any port 5432 comment 'PostgreSQL from VPS3'
        
        # Redis (from VPS1 and VPS3 via WireGuard)
        ufw allow from ${VPS1_WIREGUARD_IP:-10.10.0.1} to any port 6379 comment 'Redis from VPS1'
        ufw allow from ${VPS3_WIREGUARD_IP:-10.10.0.3} to any port 6379 comment 'Redis from VPS3'
        
        # Enable firewall
        ufw --force enable
    "
}

configure_firewall_vps3() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Configuring firewall for VPS3 (WORKER)"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        # Reset UFW to defaults (if not already configured)
        ufw --force reset || true
        
        # Default policies
        ufw default deny incoming
        ufw default allow outgoing
        
        # SSH
        ufw allow ${port}/tcp comment 'SSH'
        
        # WireGuard
        ufw allow ${WIREGUARD_PORT:-51820}/udp comment 'WireGuard'
        
        # PostgreSQL and Redis (from WireGuard network)
        ufw allow from 10.10.0.0/24 to any port 5432 comment 'PostgreSQL'
        ufw allow from 10.10.0.0/24 to any port 6379 comment 'Redis'
        
        # Enable firewall
        ufw --force enable
    "
}

main() {
    init_script "$@"
    load_inventory
    
    if [ -z "${TARGET_HOST:-}" ]; then
        log_error "Target host not specified. Use --host HOST"
        show_help
        exit 1
    fi
    
    # Determine which VPS this is
    local ssh_user="root"
    local ssh_port="22"
    
    if [ "$TARGET_HOST" = "${VPS1_HOST:-}" ]; then
        ssh_user="${VPS1_SSH_USER:-root}"
        ssh_port="${VPS1_SSH_PORT:-22}"
    elif [ "$TARGET_HOST" = "${VPS2_HOST:-}" ]; then
        ssh_user="${VPS2_SSH_USER:-root}"
        ssh_port="${VPS2_SSH_PORT:-22}"
    elif [ "$TARGET_HOST" = "${VPS3_HOST:-}" ]; then
        ssh_user="${VPS3_SSH_USER:-root}"
        ssh_port="${VPS3_SSH_PORT:-22}"
    fi
    
    log_info "Configuring firewall on $TARGET_HOST"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    # Configure based on which VPS
    if [ "$TARGET_HOST" = "${VPS1_HOST:-}" ]; then
        configure_firewall_vps1 "$TARGET_HOST" "$ssh_user" "$ssh_port"
    elif [ "$TARGET_HOST" = "${VPS2_HOST:-}" ]; then
        configure_firewall_vps2 "$TARGET_HOST" "$ssh_user" "$ssh_port"
    elif [ "$TARGET_HOST" = "${VPS3_HOST:-}" ]; then
        configure_firewall_vps3 "$TARGET_HOST" "$ssh_user" "$ssh_port"
    else
        log_error "Unknown host: $TARGET_HOST"
        exit 1
    fi
    
    log_success "Firewall configuration completed"
}

main "$@"
