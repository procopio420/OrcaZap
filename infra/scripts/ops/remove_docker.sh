#!/bin/bash
# Remove Docker completely from the host
# This script is idempotent and supports dry-run mode

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$(dirname "$SCRIPT_DIR")/lib"

# Source common functions
source "$LIB_DIR/common.sh"
source "$LIB_DIR/ssh.sh"

show_help() {
    cat <<EOF
Remove Docker completely from the host.

This script will:
  - Stop and disable Docker services
  - Purge Docker packages (docker.io, docker-ce, containerd, etc.)
  - Remove Docker directories and configuration
  - Clean up leftover files

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required)
    --help, -h          Show this help message

Environment Variables:
    CONFIRM_REMOVE_DOCKER=1    Required to actually perform removal

Examples:
    # Dry run
    CONFIRM_REMOVE_DOCKER=1 ./remove_docker.sh --host <VPS1_HOST> --dry-run

    # Actual removal
    CONFIRM_REMOVE_DOCKER=1 ./remove_docker.sh --host <VPS1_HOST>

EOF
}

# Stop and disable Docker and containerd services
stop_docker_services() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Stopping Docker services"
    
    if [ "$DRY_RUN" = true ]; then
        log_dry_run "systemctl stop docker containerd"
        log_dry_run "systemctl disable docker containerd"
        return 0
    fi
    
    ssh_exec_sudo "$host" "$user" "$port" 'systemctl stop docker containerd 2>/dev/null || true; systemctl disable docker containerd 2>/dev/null || true; echo "Docker services stopped and disabled"'
}

# Purge all Docker-related packages
purge_docker_packages() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Purging Docker packages"
    
    local packages="docker.io docker-ce docker-ce-cli docker-compose docker-compose-plugin containerd containerd.io runc docker-buildx-plugin docker-ce-rootless-extras"
    
    if [ "$DRY_RUN" = true ]; then
        log_dry_run "apt-get purge -y $packages"
        log_dry_run "apt-get autoremove -y"
        return 0
    fi
    
    ssh_exec_sudo "$host" "$user" "$port" "export DEBIAN_FRONTEND=noninteractive; apt-get purge -y $packages 2>/dev/null || true; apt-get autoremove -y -qq; echo 'Docker packages purged'"
}

# Remove Docker data and configuration directories
remove_docker_directories() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Removing Docker directories"
    
    local dirs="/var/lib/docker /var/lib/containerd /etc/docker /root/.docker"
    
    if [ "$DRY_RUN" = true ]; then
        log_dry_run "rm -rf $dirs"
        return 0
    fi
    
    ssh_exec_sudo "$host" "$user" "$port" "for dir in $dirs; do if [ -d \"\$dir\" ]; then rm -rf \"\$dir\"; echo \"Removed \$dir\"; fi; done"
}

# Verify that Docker has been completely removed
verify_docker_removal() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Verifying Docker removal"
    
    if [ "$DRY_RUN" = true ]; then
        log_dry_run "command -v docker"
        log_dry_run "systemctl status docker containerd"
        return 0
    fi
    
    log_info "Checking if docker command exists:"
    if ssh_exec "$host" "$user" "$port" "command -v docker >/dev/null 2>&1"; then
        log_error "Docker command still exists"
        return 1
    else
        log_success "Docker command not found (removed)"
    fi
    
    log_info "Checking Docker service status:"
    ssh_exec "$host" "$user" "$port" "systemctl status docker containerd 2>&1 | head -3 || echo 'Services not found (removed)'"
}

main() {
    init_script "$@"
    load_inventory
    
    # Check confirmation
    if [ "${CONFIRM_REMOVE_DOCKER:-}" != "1" ]; then
        log_error "CONFIRM_REMOVE_DOCKER=1 is required to perform removal"
        log_info "Set CONFIRM_REMOVE_DOCKER=1 and run again"
        exit 1
    fi
    
    if [ -z "${TARGET_HOST:-}" ]; then
        log_error "Target host not specified. Use --host HOST"
        show_help
        exit 1
    fi
    
    # Use inventory variables if available, otherwise defaults
    local ssh_user="${VPS1_SSH_USER:-${VPS2_SSH_USER:-${VPS3_SSH_USER:-root}}}"
    local ssh_port="${VPS1_SSH_PORT:-${VPS2_SSH_PORT:-${VPS3_SSH_PORT:-22}}}"
    
    log_info "Starting Docker removal on $TARGET_HOST"
    
    stop_docker_services "$TARGET_HOST" "$ssh_user" "$ssh_port"
    purge_docker_packages "$TARGET_HOST" "$ssh_user" "$ssh_port"
    remove_docker_directories "$TARGET_HOST" "$ssh_user" "$ssh_port"
    verify_docker_removal "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    log_success "Docker removal completed"
}

main "$@"

