#!/bin/bash
# Database migration script
# Runs Alembic migrations on VPS1 (connects via PgBouncer)
# Usage: ./migrate.sh --host HOST [OPTIONS]

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

Runs Alembic database migrations.

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required, should be VPS1)
    --help, -h          Show this help message

EOF
}

run_migrations() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local app_dir="${APP_DIR:-/opt/orcazap}"
    local app_user="${APP_USER:-orcazap}"
    
    log_info "Running database migrations"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        cd $app_dir
        sudo -u $app_user $app_dir/venv/bin/alembic upgrade head
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
    
    local ssh_user="${VPS1_SSH_USER:-root}"
    local ssh_port="${VPS1_SSH_PORT:-22}"
    
    log_info "Running migrations on $TARGET_HOST"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    run_migrations "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    log_success "Migrations completed"
}

main "$@"


