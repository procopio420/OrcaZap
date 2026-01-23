#!/bin/bash
# PgBouncer bootstrap script for VPS1 (APP server)
# Installs and configures PgBouncer
# Usage: ./41_app_pgbouncer.sh --host HOST [OPTIONS]

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

Installs and configures PgBouncer on VPS1 (APP server).

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required, should be VPS1)
    --help, -h          Show this help message

EOF
}

install_pgbouncer() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Installing PgBouncer"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        export DEBIAN_FRONTEND=noninteractive
        
        # Install PgBouncer
        if ! command -v pgbouncer >/dev/null 2>&1; then
            apt-get install -y -qq pgbouncer
        else
            log_info 'PgBouncer already installed'
        fi
    "
}

generate_md5_hash() {
    local username="$1"
    local password="$2"
    echo -n "${username}${password}" | md5sum | cut -d' ' -f1
}

configure_pgbouncer() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local db_host="${4:-10.10.0.2}"
    local db_port="${5:-5432}"
    local db_name="${POSTGRES_DB:-orcazap}"
    local db_user="${POSTGRES_USER:-orcazap}"
    local db_password="${POSTGRES_PASSWORD:-}"
    
    if [ -z "$db_password" ]; then
        log_error "POSTGRES_PASSWORD not set in inventory"
        exit 1
    fi
    
    log_info "Configuring PgBouncer"
    
    # Generate MD5 hash for userlist
    local md5_hash=$(generate_md5_hash "$db_user" "$db_password")
    
    # Render pgbouncer.ini template
    local template_file="$TEMPLATE_DIR/pgbouncer/pgbouncer.ini.tmpl"
    
    if [ ! -f "$template_file" ]; then
        log_error "Template file not found: $template_file"
        exit 1
    fi
    
    local config_content=$(cat "$template_file")
    
    config_content=$(echo "$config_content" | sed "s|\${DB_NAME}|$db_name|g")
    config_content=$(echo "$config_content" | sed "s|\${DB_HOST}|$db_host|g")
    config_content=$(echo "$config_content" | sed "s|\${DB_PORT}|$db_port|g")
    config_content=$(echo "$config_content" | sed "s|\${LISTEN_ADDR}|127.0.0.1|g")
    config_content=$(echo "$config_content" | sed "s|\${LISTEN_PORT}|6432|g")
    config_content=$(echo "$config_content" | sed "s|\${MAX_CLIENT_CONN}|100|g")
    config_content=$(echo "$config_content" | sed "s|\${DEFAULT_POOL_SIZE}|20|g")
    config_content=$(echo "$config_content" | sed "s|\${MIN_POOL_SIZE}|5|g")
    config_content=$(echo "$config_content" | sed "s|\${RESERVE_POOL_SIZE}|5|g")
    config_content=$(echo "$config_content" | sed "s|\${RESERVE_POOL_TIMEOUT}|3|g")
    
    # Render userlist.txt template
    local userlist_template="$TEMPLATE_DIR/pgbouncer/userlist.txt.tmpl"
    
    if [ ! -f "$userlist_template" ]; then
        log_error "Template file not found: $userlist_template"
        exit 1
    fi
    
    local userlist_content=$(cat "$userlist_template")
    
    userlist_content=$(echo "$userlist_content" | sed "s|\${DB_USER}|$db_user|g")
    userlist_content=$(echo "$userlist_content" | sed "s|\${MD5_HASH}|md5$md5_hash|g")
    
    # Write configs to temp files
    local temp_config="/tmp/pgbouncer.ini.$$"
    local temp_userlist="/tmp/userlist.txt.$$"
    
    echo "$config_content" > "$temp_config"
    echo "$userlist_content" > "$temp_userlist"
    
    # Copy to remote host
    ssh_copy_file "$host" "$user" "$port" "$temp_config" "/tmp/pgbouncer.ini"
    ssh_copy_file "$host" "$user" "$port" "$temp_userlist" "/tmp/userlist.txt"
    
    # Move to final location with backup
    ssh_exec_sudo "$host" "$user" "$port" "
        if [ -f /etc/pgbouncer/pgbouncer.ini ]; then
            cp /etc/pgbouncer/pgbouncer.ini /etc/pgbouncer/pgbouncer.ini.backup.\$(date +%Y%m%d_%H%M%S)
        fi
        if [ -f /etc/pgbouncer/userlist.txt ]; then
            cp /etc/pgbouncer/userlist.txt /etc/pgbouncer/userlist.txt.backup.\$(date +%Y%m%d_%H%M%S)
        fi
        
        mkdir -p /etc/pgbouncer
        mv /tmp/pgbouncer.ini /etc/pgbouncer/pgbouncer.ini
        mv /tmp/userlist.txt /etc/pgbouncer/userlist.txt
        chmod 600 /etc/pgbouncer/pgbouncer.ini
        chmod 600 /etc/pgbouncer/userlist.txt
        chown pgbouncer:pgbouncer /etc/pgbouncer/pgbouncer.ini
        chown pgbouncer:pgbouncer /etc/pgbouncer/userlist.txt
    "
    
    # Clean up temp files
    rm -f "$temp_config" "$temp_userlist"
}

restart_pgbouncer() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Restarting PgBouncer"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        systemctl restart pgbouncer
        systemctl enable pgbouncer
    "
}

main() {
    init_script "$@"
    load_inventory
    
    if [ -z "${TARGET_HOST:-}" ]; then
        TARGET_HOST="${VPS1_HOST:-}"
    fi
    
    if [ -z "$TARGET_HOST" ]; then
        log_error "Target host not specified. Use --host HOST or set VPS1_HOST"
        show_help
        exit 1
    fi
    
    # Should be VPS1
    if [ "$TARGET_HOST" != "${VPS1_HOST:-}" ]; then
        log_warning "This script is intended for VPS1 (APP server). Continuing anyway..."
    fi
    
    local ssh_user="${VPS1_SSH_USER:-root}"
    local ssh_port="${VPS1_SSH_PORT:-22}"
    local db_host="${VPS2_WIREGUARD_IP:-10.10.0.2}"
    
    log_info "Setting up PgBouncer on $TARGET_HOST"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    # Validate required variables
    validate_required_vars POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD
    
    install_pgbouncer "$TARGET_HOST" "$ssh_user" "$ssh_port"
    configure_pgbouncer "$TARGET_HOST" "$ssh_user" "$ssh_port" "$db_host"
    restart_pgbouncer "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    log_success "PgBouncer setup completed"
}

main "$@"

