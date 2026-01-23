#!/bin/bash
# Prerequisites bootstrap script
# Installs base packages, sets up swap, updates system
# Usage: ./00_prereqs.sh --host HOST [OPTIONS]

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

Installs base packages, sets up swap, updates system.

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required)
    --help, -h          Show this help message

EOF
}

setup_swap() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Setting up swap (2GB)"
    
    ssh_exec_sudo "$host" "$user" "$port" 'if [ ! -f /swapfile ]; then fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048; chmod 600 /swapfile; mkswap /swapfile; swapon /swapfile; echo "/swapfile none swap sw 0 0" >> /etc/fstab; echo "Swap file created and enabled"; else echo "Swap file already exists"; fi'
}

update_system() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Updating system packages"
    
    ssh_exec_sudo "$host" "$user" "$port" 'export DEBIAN_FRONTEND=noninteractive; apt-get update -qq; apt-get upgrade -y -qq'
}

install_base_packages() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Installing base packages"
    
    ssh_exec_sudo "$host" "$user" "$port" 'export DEBIAN_FRONTEND=noninteractive; apt-get install -y -qq wireguard-tools ufw curl wget git python3 python3-pip python3-venv postgresql-client redis-tools htop vim net-tools iputils-ping'
}

main() {
    init_script "$@"
    load_inventory
    
    if [ -z "${TARGET_HOST:-}" ]; then
        log_error "Target host not specified. Use --host HOST"
        show_help
        exit 1
    fi
    
    # Determine which VPS this is based on host
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
    
    log_info "Setting up prerequisites on $TARGET_HOST"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    setup_swap "$TARGET_HOST" "$ssh_user" "$ssh_port"
    update_system "$TARGET_HOST" "$ssh_user" "$ssh_port"
    install_base_packages "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    log_success "Prerequisites setup completed"
}

main "$@"

