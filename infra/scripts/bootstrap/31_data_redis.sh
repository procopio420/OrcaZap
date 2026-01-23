#!/bin/bash
# Redis bootstrap script for VPS2 (DATA server)
# Installs and configures Redis 7
# Usage: ./31_data_redis.sh --host HOST [OPTIONS]

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

Installs and configures Redis 7 on VPS2 (DATA server).

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required, should be VPS2)
    --help, -h          Show this help message

EOF
}

install_redis() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Installing Redis 7"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        export DEBIAN_FRONTEND=noninteractive
        
        # Install Redis
        if ! command -v redis-server >/dev/null 2>&1; then
            apt-get install -y -qq redis-server
        else
            echo 'Redis already installed'
        fi
    "
}

configure_redis() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local wg_ip="${4:-10.10.0.2}"
    local redis_password="${REDIS_PASSWORD:-}"
    
    if [ -z "$redis_password" ]; then
        log_error "REDIS_PASSWORD not set in inventory"
        exit 1
    fi
    
    log_info "Configuring Redis"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        # Backup existing config
        if [ -f /etc/redis/redis.conf ]; then
            cp /etc/redis/redis.conf /etc/redis/redis.conf.backup.\$(date +%Y%m%d_%H%M%S)
        fi
        
        # Configure to bind to WireGuard interface
        sed -i 's|^bind 127.0.0.1|bind $wg_ip 127.0.0.1|g' /etc/redis/redis.conf
        sed -i 's|^# bind 127.0.0.1|bind $wg_ip 127.0.0.1|g' /etc/redis/redis.conf
        
        # Set password
        sed -i 's|^# requirepass|requirepass|g' /etc/redis/redis.conf
        sed -i 's|^requirepass.*|requirepass $redis_password|g' /etc/redis/redis.conf
        
        # Enable protected mode
        sed -i 's|^protected-mode yes|protected-mode yes|g' /etc/redis/redis.conf
        sed -i 's|^protected-mode no|protected-mode yes|g' /etc/redis/redis.conf
        
        # Persistence (RDB snapshots)
        sed -i 's|^save 900 1|save 900 1|g' /etc/redis/redis.conf
        sed -i 's|^save 300 10|save 300 10|g' /etc/redis/redis.conf
        sed -i 's|^save 60 10000|save 60 10000|g' /etc/redis/redis.conf
    "
}

restart_redis() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Restarting Redis"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        systemctl restart redis-server
        systemctl enable redis-server
    "
}

main() {
    init_script "$@"
    load_inventory
    
    if [ -z "${TARGET_HOST:-}" ]; then
        TARGET_HOST="${VPS2_HOST:-}"
    fi
    
    if [ -z "$TARGET_HOST" ]; then
        log_error "Target host not specified. Use --host HOST or set VPS2_HOST"
        show_help
        exit 1
    fi
    
    # Should be VPS2
    if [ "$TARGET_HOST" != "${VPS2_HOST:-}" ]; then
        log_warning "This script is intended for VPS2 (DATA server). Continuing anyway..."
    fi
    
    local ssh_user="${VPS2_SSH_USER:-root}"
    local ssh_port="${VPS2_SSH_PORT:-22}"
    local wg_ip="${VPS2_WIREGUARD_IP:-10.10.0.2}"
    
    log_info "Setting up Redis on $TARGET_HOST"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    # Validate required variables
    validate_required_vars REDIS_PASSWORD
    
    install_redis "$TARGET_HOST" "$ssh_user" "$ssh_port"
    configure_redis "$TARGET_HOST" "$ssh_user" "$ssh_port" "$wg_ip"
    restart_redis "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    log_success "Redis setup completed"
}

main "$@"


