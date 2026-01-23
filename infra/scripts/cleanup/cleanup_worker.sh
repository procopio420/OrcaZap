#!/bin/bash
# Cleanup script for VPS3 (WORKER server)
# Usage: ./cleanup_worker.sh --host HOST [OPTIONS]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"

# Source library functions
source "$LIB_DIR/common.sh"
source "$LIB_DIR/ssh.sh"
source "$LIB_DIR/assert.sh"

# Parse arguments
TARGET_HOST=""
CODE_ONLY=false
SERVICES_ONLY=false
LOGS_ONLY=false
REMOVE_USER=false

show_help() {
    cat <<EOF
Usage: $(basename "$0") --host HOST [OPTIONS]

Cleanup VPS3 (WORKER server): removes code, venv, services, logs.

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required)
    --code-only         Clean only code and venv
    --services-only     Clean only systemd services
    --logs-only         Clean only logs
    --remove-user       Also remove application user (requires confirmation)
    --help, -h          Show this help message

EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --host)
                TARGET_HOST="$2"
                shift 2
                ;;
            --code-only)
                CODE_ONLY=true
                shift
                ;;
            --services-only)
                SERVICES_ONLY=true
                shift
                ;;
            --logs-only)
                LOGS_ONLY=true
                shift
                ;;
            --remove-user)
                REMOVE_USER=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

cleanup_services() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Stopping and removing systemd services"
    
    # Stop all worker instances gracefully
    ssh_exec_sudo "$host" "$user" "$port" "
        for i in {1..4}; do
            systemctl stop orcazap-worker@\$i --no-block || true
            timeout 30 bash -c 'while systemctl is-active --quiet orcazap-worker@\$i; do sleep 1; done' || true
            systemctl disable orcazap-worker@\$i || true
        done
        systemctl stop orcazap-worker --no-block || true
        timeout 30 bash -c 'while systemctl is-active --quiet orcazap-worker; do sleep 1; done' || true
        systemctl disable orcazap-worker || true
    "
    
    # Remove systemd unit files
    ssh_exec_sudo "$host" "$user" "$port" "
        rm -f /etc/systemd/system/orcazap-worker@.service
        rm -f /etc/systemd/system/orcazap-worker.service
        systemctl daemon-reload
    "
    
    log_success "Services stopped and removed"
}

cleanup_code() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Removing application code and virtual environment"
    
    local app_dir="${APP_DIR:-/opt/orcazap}"
    ssh_exec_sudo "$host" "$user" "$port" "
        rm -rf $app_dir
    "
    
    log_success "Code and venv removed"
}

cleanup_logs() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Removing worker logs"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        rm -rf /var/log/orcazap-worker
    "
    
    log_success "Logs removed"
}

cleanup_user() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    if [ "$DRY_RUN" = true ]; then
        log_dry_run "Remove user ${APP_USER:-orcazap}"
        return 0
    fi
    
    local app_user="${APP_USER:-orcazap}"
    read -p "Are you sure you want to remove user $app_user? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "User removal cancelled"
        return 0
    fi
    
    log_info "Removing application user"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        userdel -r $app_user || true
    "
    
    log_success "User removed"
}

main() {
    init_script "$@"
    load_inventory
    
    if [ -z "$TARGET_HOST" ]; then
        TARGET_HOST="${VPS3_HOST:-}"
    fi
    
    if [ -z "$TARGET_HOST" ]; then
        log_error "Target host not specified. Use --host HOST"
        show_help
        exit 1
    fi
    
    local ssh_user="${VPS3_SSH_USER:-root}"
    local ssh_port="${VPS3_SSH_PORT:-22}"
    
    log_info "Starting cleanup for VPS3 (WORKER): $TARGET_HOST"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    # Determine what to clean
    if [ "$CODE_ONLY" = true ]; then
        cleanup_code "$TARGET_HOST" "$ssh_user" "$ssh_port"
    elif [ "$SERVICES_ONLY" = true ]; then
        cleanup_services "$TARGET_HOST" "$ssh_user" "$ssh_port"
    elif [ "$LOGS_ONLY" = true ]; then
        cleanup_logs "$TARGET_HOST" "$ssh_user" "$ssh_port"
    else
        # Full cleanup
        cleanup_services "$TARGET_HOST" "$ssh_user" "$ssh_port"
        cleanup_code "$TARGET_HOST" "$ssh_user" "$ssh_port"
        cleanup_logs "$TARGET_HOST" "$ssh_user" "$ssh_port"
    fi
    
    if [ "$REMOVE_USER" = true ]; then
        cleanup_user "$TARGET_HOST" "$ssh_user" "$ssh_port"
    fi
    
    log_success "Cleanup completed for $TARGET_HOST"
}

main "$@"

