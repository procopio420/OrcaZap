#!/bin/bash
# Health check script
# Checks application health endpoint and systemd service status
# Usage: ./healthcheck.sh --host HOST [OPTIONS]

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

Checks application health and service status.

Options:
    --dry-run           Show what would be checked without making requests
    --host HOST         Target host (required)
    --timeout SECONDS   Health check timeout (default: 10)
    --help, -h          Show this help message

EOF
}

check_service_status() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local service="$4"
    
    log_info "Checking service status: $service"
    
    local status=$(ssh_exec "$host" "$user" "$port" "systemctl is-active $service" || echo "inactive")
    
    if [ "$status" = "active" ]; then
        log_success "Service $service is active"
        return 0
    else
        log_error "Service $service is not active (status: $status)"
        return 1
    fi
}

check_health_endpoint() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local timeout="${HEALTH_TIMEOUT:-10}"
    
    log_info "Checking health endpoint"
    
    local http_code=$(ssh_exec "$host" "$user" "$port" "
        timeout $timeout curl -sf -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health 2>/dev/null || echo '000'
    " || echo "000")
    
    local response=$(ssh_exec "$host" "$user" "$port" "
        timeout $timeout curl -sf http://127.0.0.1:8000/health 2>/dev/null || echo 'FAILED'
    " || echo "FAILED")
    
    # Check HTTP status code is 200 and response contains valid JSON with status
    if [ "$http_code" = "200" ] && [ "$response" != "FAILED" ] && echo "$response" | grep -qE '"status"|"ok"|"healthy"'; then
        log_success "Health endpoint responded: $response"
        return 0
    else
        log_error "Health endpoint check failed (HTTP: $http_code, response: $response)"
        return 1
    fi
}

print_service_logs() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local service="$4"
    local lines="${5:-50}"
    
    log_info "Last $lines lines of $service logs:"
    
    ssh_exec "$host" "$user" "$port" "
        journalctl -u $service -n $lines --no-pager
    "
}

main() {
    init_script "$@"
    load_inventory
    
    # Parse timeout
    HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-10}"
    for arg in "$@"; do
        if [[ $arg == --timeout=* ]]; then
            HEALTH_TIMEOUT="${arg#*=}"
        fi
    done
    
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
    
    log_info "Running health check on $TARGET_HOST"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    local health_ok=true
    
    # Check service status
    if ! check_service_status "$TARGET_HOST" "$ssh_user" "$ssh_port" "orcazap-app"; then
        health_ok=false
        print_service_logs "$TARGET_HOST" "$ssh_user" "$ssh_port" "orcazap-app"
    fi
    
    # Check health endpoint
    if ! check_health_endpoint "$TARGET_HOST" "$ssh_user" "$ssh_port"; then
        health_ok=false
        print_service_logs "$TARGET_HOST" "$ssh_user" "$ssh_port" "orcazap-app"
    fi
    
    if [ "$health_ok" = true ]; then
        log_success "Health check passed"
        exit 0
    else
        log_error "Health check failed"
        exit 1
    fi
}

main "$@"

