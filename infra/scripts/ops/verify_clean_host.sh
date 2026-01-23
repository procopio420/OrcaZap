#!/bin/bash
# Verify that the host is clean of BaseCommerce and optionally Docker
# This script is idempotent and supports dry-run mode

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$(dirname "$SCRIPT_DIR")/lib"

# Source common functions
source "$LIB_DIR/common.sh"
source "$LIB_DIR/ssh.sh"

show_help() {
    cat <<EOF
Verify that the host is clean of BaseCommerce artifacts.

This script will:
  - Check if Docker exists (if not removed)
  - Show port listeners for 80/443/8000
  - Search for any remaining BaseCommerce files/directories
  - Exit with non-zero if BaseCommerce artifacts are found

Options:
    --dry-run           Show what would be checked without making changes
    --host HOST         Target host (required)
    --help, -h          Show this help message

Examples:
    ./verify_clean_host.sh --host 191.252.120.36

EOF
}

# Check if Docker is installed and show its status
check_docker_status() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Checking Docker status"
    
    if ssh_exec "$host" "$user" "$port" "command -v docker >/dev/null 2>&1 || systemctl is-active docker >/dev/null 2>&1"; then
        log_info "Docker is installed"
        ssh_exec "$host" "$user" "$port" "docker --version 2>/dev/null || echo 'Docker service exists but command not in PATH'"
    else
        log_info "Docker is not installed (or was removed)"
    fi
}

# Check which processes are listening on ports 80, 443, and 8000
check_port_listeners() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Checking port listeners (80/443/8000)"
    
    ssh_exec "$host" "$user" "$port" "ss -lntp | grep -E ':(80|443|8000)' || echo 'Ports 80/443/8000 are free or not listening'"
}

# Search for any remaining BaseCommerce files or directories
check_basecommerce_artifacts() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Searching for BaseCommerce artifacts"
    
    local search_paths="/opt /srv /root /home /var/www"
    local found_artifacts=false
    
    for search_path in $search_paths; do
        local artifacts=$(ssh_exec "$host" "$user" "$port" "find \"$search_path\" -maxdepth 4 -iname '*basecommerce*' 2>/dev/null || true" || echo "")
        
        if [ -n "$artifacts" ]; then
            log_error "Found BaseCommerce artifacts in $search_path:"
            echo "$artifacts"
            found_artifacts=true
        fi
    done
    
    if [ "$found_artifacts" = true ]; then
        log_error "BaseCommerce artifacts found on the host"
        return 1
    else
        log_success "No BaseCommerce artifacts found"
        return 0
    fi
}

# Check for any remaining BaseCommerce Docker containers
check_docker_containers() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Checking for BaseCommerce Docker containers"
    
    if ssh_exec "$host" "$user" "$port" "command -v docker >/dev/null 2>&1 || systemctl is-active docker >/dev/null 2>&1"; then
        local containers=$(ssh_exec "$host" "$user" "$port" "docker ps -a --format '{{.Names}}' 2>/dev/null | grep -i basecommerce || true" || echo "")
        
        if [ -n "$containers" ]; then
            log_error "Found BaseCommerce containers:"
            echo "$containers"
            return 1
        else
            log_success "No BaseCommerce containers found"
        fi
    else
        log_info "Docker not installed, skipping container check"
    fi
    
    return 0
}

main() {
    init_script "$@"
    load_inventory
    
    if [ -z "${TARGET_HOST:-}" ]; then
        log_error "Target host not specified. Use --host HOST"
        show_help
        exit 1
    fi
    
    # Use inventory variables if available, otherwise defaults
    local ssh_user="${VPS1_SSH_USER:-${VPS2_SSH_USER:-${VPS3_SSH_USER:-root}}}"
    local ssh_port="${VPS1_SSH_PORT:-${VPS2_SSH_PORT:-${VPS3_SSH_PORT:-22}}}"
    
    log_info "Verifying clean host: $TARGET_HOST"
    
    local exit_code=0
    
    check_docker_status "$TARGET_HOST" "$ssh_user" "$ssh_port"
    check_port_listeners "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    if ! check_basecommerce_artifacts "$TARGET_HOST" "$ssh_user" "$ssh_port"; then
        exit_code=1
    fi
    
    if ! check_docker_containers "$TARGET_HOST" "$ssh_user" "$ssh_port"; then
        exit_code=1
    fi
    
    if [ $exit_code -eq 0 ]; then
        log_success "Host is clean - no BaseCommerce artifacts found"
    else
        log_error "Host is NOT clean - BaseCommerce artifacts remain"
    fi
    
    exit $exit_code
}

main "$@"

