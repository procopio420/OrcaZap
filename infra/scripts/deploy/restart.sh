#!/bin/bash
# Service restart helper script
# Restarts app or worker services
# Usage: ./restart.sh --host HOST --service SERVICE [OPTIONS]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"

# Source library functions
source "$LIB_DIR/common.sh"
source "$LIB_DIR/ssh.sh"
source "$LIB_DIR/assert.sh"

show_help() {
    cat <<EOF
Usage: $(basename "$0") --host HOST --service SERVICE [OPTIONS]

Restarts application or worker services.

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required)
    --service SERVICE   Service to restart: app, worker, or all (required)
    --help, -h          Show this help message

EOF
}

restart_app() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Restarting application service"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        systemctl daemon-reload
        systemctl restart orcazap-app
        
        # Wait for service to be active
        sleep 2
        if ! systemctl is-active --quiet orcazap-app; then
            echo 'Service failed to start' >&2
            exit 1
        fi
    "
}

restart_worker() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local num_workers="${NUM_WORKERS:-4}"
    
    log_info "Restarting worker services"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        systemctl daemon-reload
        for i in \$(seq 1 $num_workers); do
            systemctl restart orcazap-worker@\$i
        done
        
        # Wait for services to be active
        sleep 2
        for i in \$(seq 1 $num_workers); do
            if ! systemctl is-active --quiet orcazap-worker@\$i; then
                echo \"Worker \$i failed to start\" >&2
                exit 1
            fi
        done
    "
}

main() {
    init_script "$@"
    load_inventory
    
    # Parse service argument
    local service=""
    for arg in "$@"; do
        if [[ $arg == --service=* ]]; then
            service="${arg#*=}"
        elif [[ $arg == --service ]]; then
            # Will be handled by next iteration
            :
        fi
    done
    
    if [ -z "${TARGET_HOST:-}" ]; then
        log_error "Target host not specified. Use --host HOST"
        show_help
        exit 1
    fi
    
    if [ -z "$service" ]; then
        log_error "Service not specified. Use --service app|worker|all"
        show_help
        exit 1
    fi
    
    # Determine which VPS
    local ssh_user="root"
    local ssh_port="22"
    
    if [ "$TARGET_HOST" = "${VPS1_HOST:-}" ]; then
        ssh_user="${VPS1_SSH_USER:-root}"
        ssh_port="${VPS1_SSH_PORT:-22}"
    elif [ "$TARGET_HOST" = "${VPS3_HOST:-}" ]; then
        ssh_user="${VPS3_SSH_USER:-root}"
        ssh_port="${VPS3_SSH_PORT:-22}"
    fi
    
    log_info "Restarting services on $TARGET_HOST"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    case "$service" in
        app)
            if [ "$TARGET_HOST" != "${VPS1_HOST:-}" ]; then
                log_error "App service should be restarted on VPS1"
                exit 1
            fi
            restart_app "$TARGET_HOST" "$ssh_user" "$ssh_port"
            ;;
        worker)
            if [ "$TARGET_HOST" != "${VPS3_HOST:-}" ]; then
                log_error "Worker service should be restarted on VPS3"
                exit 1
            fi
            restart_worker "$TARGET_HOST" "$ssh_user" "$ssh_port"
            ;;
        all)
            if [ "$TARGET_HOST" = "${VPS1_HOST:-}" ]; then
                restart_app "$TARGET_HOST" "$ssh_user" "$ssh_port"
            elif [ "$TARGET_HOST" = "${VPS3_HOST:-}" ]; then
                restart_worker "$TARGET_HOST" "$ssh_user" "$ssh_port"
            else
                log_error "Unknown host for service restart"
                exit 1
            fi
            ;;
        *)
            log_error "Unknown service: $service. Use app, worker, or all"
            exit 1
            ;;
    esac
    
    log_success "Service restart completed"
}

main "$@"

