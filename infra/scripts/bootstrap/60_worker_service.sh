#!/bin/bash
# Worker service bootstrap script for VPS3 (WORKER server)
# Creates systemd unit for RQ worker
# Usage: ./60_worker_service.sh --host HOST [OPTIONS]

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

Creates systemd unit for RQ worker on VPS3 (WORKER server).

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required, should be VPS3)
    --workers N         Number of worker instances (default: 4)
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
        mkdir -p /var/log/orcazap-worker
        chown -R $app_user:$app_user $app_dir
        chown -R $app_user:$app_user /var/log/orcazap-worker
    "
}

create_systemd_unit() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local app_user="${APP_USER:-orcazap}"
    local app_dir="${APP_DIR:-/opt/orcazap}"
    local app_env_file="${APP_ENV_FILE:-/opt/orcazap/.env}"
    local redis_url="${REDIS_URL:-redis://10.10.0.2:6379/0}"
    local num_workers="${NUM_WORKERS:-4}"
    
    log_info "Creating systemd unit template for $num_workers workers"
    
    # Render template
    local template_file="$TEMPLATE_DIR/systemd/orcazap-worker.service.tmpl"
    
    if [ ! -f "$template_file" ]; then
        log_error "Template file not found: $template_file"
        exit 1
    fi
    
    local unit_content=$(cat "$template_file")
    
    unit_content=$(echo "$unit_content" | sed "s|\${APP_USER}|$app_user|g")
    unit_content=$(echo "$unit_content" | sed "s|\${APP_DIR}|$app_dir|g")
    unit_content=$(echo "$unit_content" | sed "s|\${APP_ENV_FILE}|$app_env_file|g")
    unit_content=$(echo "$unit_content" | sed "s|\${REDIS_URL}|$redis_url|g")
    
    # Write to temp file
    local temp_unit="/tmp/orcazap-worker@.service.$$"
    echo "$unit_content" > "$temp_unit"
    
    # Copy to remote host
    ssh_copy_file "$host" "$user" "$port" "$temp_unit" "/tmp/orcazap-worker@.service"
    
    # Move to final location with backup
    ssh_exec_sudo "$host" "$user" "$port" "
        if [ -f /etc/systemd/system/orcazap-worker@.service ]; then
            cp /etc/systemd/system/orcazap-worker@.service /etc/systemd/system/orcazap-worker@.service.backup.\$(date +%Y%m%d_%H%M%S)
        fi
        mv /tmp/orcazap-worker@.service /etc/systemd/system/orcazap-worker@.service
        systemctl daemon-reload
    "
    
    # Enable worker instances
    ssh_exec_sudo "$host" "$user" "$port" "
        for i in \$(seq 1 $num_workers); do
            systemctl enable orcazap-worker@\$i || true
        done
    "
    
    # Clean up
    rm -f "$temp_unit"
}

main() {
    init_script "$@"
    load_inventory
    
    # Parse NUM_WORKERS if provided
    NUM_WORKERS="${NUM_WORKERS:-4}"
    for arg in "$@"; do
        if [[ $arg == --workers=* ]]; then
            NUM_WORKERS="${arg#*=}"
        elif [[ $arg == --workers ]]; then
            # Will be handled by parse_args if needed
            :
        fi
    done
    
    if [ -z "${TARGET_HOST:-}" ]; then
        TARGET_HOST="${VPS3_HOST:-}"
    fi
    
    if [ -z "$TARGET_HOST" ]; then
        log_error "Target host not specified. Use --host HOST or set VPS3_HOST"
        show_help
        exit 1
    fi
    
    # Should be VPS3
    if [ "$TARGET_HOST" != "${VPS3_HOST:-}" ]; then
        log_warning "This script is intended for VPS3 (WORKER server). Continuing anyway..."
    fi
    
    local ssh_user="${VPS3_SSH_USER:-root}"
    local ssh_port="${VPS3_SSH_PORT:-22}"
    
    log_info "Setting up worker service on $TARGET_HOST"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    # Build Redis URL
    local redis_host="${VPS2_WIREGUARD_IP:-10.10.0.2}"
    local redis_password="${REDIS_PASSWORD:-}"
    local redis_url="redis://"
    if [ -n "$redis_password" ]; then
        redis_url="redis://:$redis_password@$redis_host:6379/0"
    else
        redis_url="redis://$redis_host:6379/0"
    fi
    export REDIS_URL="$redis_url"
    
    create_user "$TARGET_HOST" "$ssh_user" "$ssh_port"
    create_directories "$TARGET_HOST" "$ssh_user" "$ssh_port"
    create_systemd_unit "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    log_success "Worker service setup completed"
    log_info "Note: Services will be enabled and started after code deployment"
}

main "$@"

