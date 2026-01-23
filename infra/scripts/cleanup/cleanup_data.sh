#!/bin/bash
# Cleanup script for VPS2 (DATA server)
# Usage: ./cleanup_data.sh --host HOST [OPTIONS]
# NOTE: This script preserves PostgreSQL and Redis data

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"

# Source library functions
source "$LIB_DIR/common.sh"
source "$LIB_DIR/ssh.sh"
source "$LIB_DIR/assert.sh"

# Parse arguments
TARGET_HOST=""
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

show_help() {
    cat <<EOF
Usage: $(basename "$0") --host HOST [OPTIONS]

Cleanup VPS2 (DATA server): removes old backups and logs.
PRESERVES: PostgreSQL database, Redis data, active backups.

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required)
    --retention-days N  Number of days to keep backups (default: 7)
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
            --retention-days)
                BACKUP_RETENTION_DAYS="$2"
                shift 2
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

cleanup_old_backups() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local backup_dir="${BACKUP_DIR:-/backup}"
    
    log_info "Removing backups older than $BACKUP_RETENTION_DAYS days"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        if [ -d '$backup_dir' ]; then
            find '$backup_dir' -name 'orcazap-*.sql.gz' -type f -mtime +$BACKUP_RETENTION_DAYS -delete
        fi
    "
    
    log_success "Old backups cleaned"
}

cleanup_old_logs() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Cleaning old logs (PostgreSQL, Redis)"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        journalctl --vacuum-time=30d || true
        find /var/log/postgresql -name '*.log' -type f -mtime +30 -delete || true
        find /var/log/redis -name '*.log' -type f -mtime +30 -delete || true
    "
    
    log_success "Old logs cleaned"
}

main() {
    init_script "$@"
    load_inventory
    
    if [ -z "$TARGET_HOST" ]; then
        TARGET_HOST="${VPS2_HOST:-}"
    fi
    
    if [ -z "$TARGET_HOST" ]; then
        log_error "Target host not specified. Use --host HOST"
        show_help
        exit 1
    fi
    
    local ssh_user="${VPS2_SSH_USER:-root}"
    local ssh_port="${VPS2_SSH_PORT:-22}"
    
    log_info "Starting cleanup for VPS2 (DATA): $TARGET_HOST"
    log_warning "This script preserves PostgreSQL and Redis data"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    cleanup_old_backups "$TARGET_HOST" "$ssh_user" "$ssh_port"
    cleanup_old_logs "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    log_success "Cleanup completed for $TARGET_HOST"
}

main "$@"


