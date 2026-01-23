#!/bin/bash
# Cleanup script for VPS1 (APP server)
# Usage: ./cleanup_app.sh --host HOST [OPTIONS]

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

Cleanup VPS1 (APP server): removes code, venv, services, configs, logs.

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
    
    # Stop services gracefully
    ssh_exec_sudo "$host" "$user" "$port" "
        systemctl stop orcazap-app --no-block || true
        timeout 30 bash -c 'while systemctl is-active --quiet orcazap-app; do sleep 1; done' || true
        systemctl disable orcazap-app || true
        systemctl stop pgbouncer --no-block || true
        timeout 10 bash -c 'while systemctl is-active --quiet pgbouncer; do sleep 1; done' || true
        systemctl disable pgbouncer || true
    "
    
    # Remove systemd unit files
    ssh_exec_sudo "$host" "$user" "$port" "
        rm -f /etc/systemd/system/orcazap-app.service
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

cleanup_configs() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Removing Nginx and PgBouncer configs"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        rm -f /etc/nginx/sites-available/orcazap
        rm -f /etc/nginx/sites-enabled/orcazap
        rm -f /etc/pgbouncer/pgbouncer.ini
        rm -f /etc/pgbouncer/userlist.txt
        nginx -t && systemctl reload nginx || true
    "
    
    log_success "Configs removed"
}

cleanup_logs() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Removing application logs"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        rm -rf /var/log/orcazap
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
    
    read -p "Are you sure you want to remove user ${APP_USER:-orcazap}? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "User removal cancelled"
        return 0
    fi
    
    log_info "Removing application user"
    
    local app_user="${APP_USER:-orcazap}"
    ssh_exec_sudo "$host" "$user" "$port" "
        userdel -r $app_user || true
    "
    
    log_success "User removed"
}

main() {
    init_script "$@"
    load_inventory
    
    if [ -z "$TARGET_HOST" ]; then
        TARGET_HOST="${VPS1_HOST:-}"
    fi
    
    if [ -z "$TARGET_HOST" ]; then
        log_error "Target host not specified. Use --host HOST"
        show_help
        exit 1
    fi
    
    local ssh_user="${VPS1_SSH_USER:-root}"
    local ssh_port="${VPS1_SSH_PORT:-22}"
    
    log_info "Starting cleanup for VPS1 (APP): $TARGET_HOST"
    
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
        cleanup_configs "$TARGET_HOST" "$ssh_user" "$ssh_port"
        cleanup_logs "$TARGET_HOST" "$ssh_user" "$ssh_port"
    fi
    
    if [ "$REMOVE_USER" = true ]; then
        cleanup_user "$TARGET_HOST" "$ssh_user" "$ssh_port"
    fi
    
    log_success "Cleanup completed for $TARGET_HOST"
}

main "$@"

