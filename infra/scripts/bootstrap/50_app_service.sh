#!/bin/bash
# Application service bootstrap script for VPS1 (APP server)
# Creates systemd unit for FastAPI application
# Usage: ./50_app_service.sh --host HOST [OPTIONS]

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

Creates systemd unit for FastAPI application on VPS1 (APP server).

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required, should be VPS1)
    --help, -h          Show this help message

EOF
}

create_user() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local app_user="${APP_USER:-orcazap}"
    
    log_info "Creating application user: $app_user"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        if ! id -u $app_user >/dev/null 2>&1; then
            useradd -r -m -s /bin/bash $app_user
        fi
    "
}

create_directories() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local app_dir="${APP_DIR:-/opt/orcazap}"
    local app_user="${APP_USER:-orcazap}"
    
    log_info "Creating application directories"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        mkdir -p $app_dir
        mkdir -p /var/log/orcazap
        mkdir -p /var/www/orcazap/static
        chown -R $app_user:$app_user $app_dir
        chown -R $app_user:$app_user /var/log/orcazap
        chown -R $app_user:$app_user /var/www/orcazap
    "
}

create_systemd_unit() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local app_user="${APP_USER:-orcazap}"
    local app_dir="${APP_DIR:-/opt/orcazap}"
    local app_env_file="${APP_ENV_FILE:-/opt/orcazap/.env}"
    
    log_info "Creating systemd unit"
    
    # Render template
    local template_file="$TEMPLATE_DIR/systemd/orcazap-app.service.tmpl"
    
    if [ ! -f "$template_file" ]; then
        log_error "Template file not found: $template_file"
        exit 1
    fi
    
    local unit_content=$(cat "$template_file")
    
    unit_content=$(echo "$unit_content" | sed "s|\${APP_USER}|$app_user|g")
    unit_content=$(echo "$unit_content" | sed "s|\${APP_DIR}|$app_dir|g")
    unit_content=$(echo "$unit_content" | sed "s|\${APP_ENV_FILE}|$app_env_file|g")
    
    # Write to temp file
    local temp_unit="/tmp/orcazap-app.service.$$"
    echo "$unit_content" > "$temp_unit"
    
    # Copy to remote host
    ssh_copy_file "$host" "$user" "$port" "$temp_unit" "/tmp/orcazap-app.service"
    
    # Move to final location with backup
    ssh_exec_sudo "$host" "$user" "$port" "
        if [ -f /etc/systemd/system/orcazap-app.service ]; then
            cp /etc/systemd/system/orcazap-app.service /etc/systemd/system/orcazap-app.service.backup.\$(date +%Y%m%d_%H%M%S)
        fi
        mv /tmp/orcazap-app.service /etc/systemd/system/orcazap-app.service
        systemctl daemon-reload
    "
    
    # Clean up
    rm -f "$temp_unit"
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
    
    log_info "Setting up application service on $TARGET_HOST"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    create_user "$TARGET_HOST" "$ssh_user" "$ssh_port"
    create_directories "$TARGET_HOST" "$ssh_user" "$ssh_port"
    create_systemd_unit "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    log_success "Application service setup completed"
    log_info "Note: Service will be enabled and started after code deployment"
}

main "$@"

