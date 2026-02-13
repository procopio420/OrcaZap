#!/bin/bash
# Remove BaseCommerce containers, images, volumes, networks, and directories
# This script is idempotent and supports dry-run mode

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$(dirname "$SCRIPT_DIR")/lib"

# Source common functions
source "$LIB_DIR/common.sh"
source "$LIB_DIR/ssh.sh"

show_help() {
    cat <<EOF
Remove BaseCommerce from the host.

This script will:
  - Stop and remove all BaseCommerce Docker containers
  - Remove BaseCommerce Docker images
  - Remove BaseCommerce Docker volumes and networks
  - Remove BaseCommerce directories and compose files
  - Free ports 80/443 for OrcaZap nginx

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required)
    --help, -h          Show this help message

Environment Variables:
    CONFIRM_REMOVE_BASECOMMERCE=1    Required to actually perform removal

Examples:
    # Dry run
    CONFIRM_REMOVE_BASECOMMERCE=1 ./remove_basecommerce.sh --host <VPS1_HOST> --dry-run

    # Actual removal
    CONFIRM_REMOVE_BASECOMMERCE=1 ./remove_basecommerce.sh --host <VPS1_HOST>

EOF
}

# Check if Docker is installed and running
check_docker_installed() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    # Check if docker command exists or docker service is active
    if ssh_exec "$host" "$user" "$port" "command -v docker >/dev/null 2>&1 || systemctl is-active docker >/dev/null 2>&1"; then
        return 0
    else
        return 1
    fi
}

# Stop and remove all BaseCommerce containers
remove_basecommerce_containers() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Removing BaseCommerce containers"
    
    if [ "$DRY_RUN" = true ]; then
        log_dry_run "docker ps -a --format '{{.Names}}' | grep -i basecommerce | xargs -r docker rm -f"
        log_dry_run "docker ps -a --format '{{.Names}}' | grep -i basecommerce | xargs -r docker stop"
        return 0
    fi
    
    ssh_exec_sudo "$host" "$user" "$port" 'containers=$(docker ps -a --format "{{.Names}}" | grep -i basecommerce || true); if [ -n "$containers" ]; then count=$(echo "$containers" | wc -l); echo "Found $count BaseCommerce container(s)"; echo "$containers" | xargs -r docker stop; echo "$containers" | xargs -r docker rm -f; echo "Removed BaseCommerce containers"; else echo "No BaseCommerce containers found"; fi'
}

# Remove all BaseCommerce Docker images
remove_basecommerce_images() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Removing BaseCommerce images"
    
    if [ "$DRY_RUN" = true ]; then
        log_dry_run "docker images --format '{{.Repository}}:{{.Tag}}' | grep -i basecommerce | xargs -r docker rmi -f"
        return 0
    fi
    
    ssh_exec_sudo "$host" "$user" "$port" 'images=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep -i basecommerce || true); if [ -n "$images" ]; then count=$(echo "$images" | wc -l); echo "Found $count BaseCommerce image(s)"; echo "$images" | xargs -r docker rmi -f; echo "Removed BaseCommerce images"; else echo "No BaseCommerce images found"; fi'
}

# Remove all BaseCommerce Docker volumes
remove_basecommerce_volumes() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Removing BaseCommerce volumes"
    
    if [ "$DRY_RUN" = true ]; then
        log_dry_run "docker volume ls --format '{{.Name}}' | grep -i basecommerce | xargs -r docker volume rm"
        return 0
    fi
    
    ssh_exec_sudo "$host" "$user" "$port" 'volumes=$(docker volume ls --format "{{.Name}}" | grep -i basecommerce || true); if [ -n "$volumes" ]; then count=$(echo "$volumes" | wc -l); echo "Found $count BaseCommerce volume(s)"; echo "$volumes" | xargs -r docker volume rm 2>/dev/null || echo "Warning: Some volumes may be in use"; echo "Removed BaseCommerce volumes"; else echo "No BaseCommerce volumes found"; fi'
}

# Remove all BaseCommerce Docker networks
remove_basecommerce_networks() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Removing BaseCommerce networks"
    
    if [ "$DRY_RUN" = true ]; then
        log_dry_run "docker network ls --format '{{.Name}}' | grep -i basecommerce | xargs -r docker network rm"
        return 0
    fi
    
    ssh_exec_sudo "$host" "$user" "$port" 'networks=$(docker network ls --format "{{.Name}}" | grep -i basecommerce || true); if [ -n "$networks" ]; then count=$(echo "$networks" | wc -l); echo "Found $count BaseCommerce network(s)"; echo "$networks" | xargs -r docker network rm; echo "Removed BaseCommerce networks"; else echo "No BaseCommerce networks found"; fi'
}

# Remove BaseCommerce directories from common paths
remove_basecommerce_directories() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Removing BaseCommerce directories"
    
    local search_paths="/opt /srv /root /home /var/www"
    
    if [ "$DRY_RUN" = true ]; then
        log_dry_run "find $search_paths -maxdepth 4 -iname '*basecommerce*' -type d -exec rm -rf {} +"
        log_dry_run "find $search_paths -maxdepth 4 -iname '*basecommerce*' -type f -delete"
        return 0
    fi
    
    ssh_exec_sudo "$host" "$user" "$port" "found=0; for path in $search_paths; do if [ -d \"\$path\" ]; then matches=\$(find \"\$path\" -maxdepth 4 -iname '*basecommerce*' 2>/dev/null | wc -l); if [ \"\$matches\" -gt 0 ]; then found=1; find \"\$path\" -maxdepth 4 -iname '*basecommerce*' -type d -exec rm -rf {} + 2>/dev/null || true; find \"\$path\" -maxdepth 4 -iname '*basecommerce*' -type f -delete 2>/dev/null || true; fi; fi; done; if [ \"\$found\" -eq 1 ]; then echo 'BaseCommerce directories removed'; else echo 'No BaseCommerce directories found'; fi"
}

# Remove docker-compose files that reference BaseCommerce
remove_basecommerce_compose_files() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Removing BaseCommerce compose files"
    
    local search_paths="/opt /srv /root /home /var/www"
    
    if [ "$DRY_RUN" = true ]; then
        log_dry_run "find $search_paths -maxdepth 4 -name 'docker-compose.yml' -o -name 'docker-compose.yaml' -o -name 'compose.yml' -o -name 'compose.yaml' | xargs -r grep -l basecommerce | xargs -r rm -f"
        return 0
    fi
    
    ssh_exec_sudo "$host" "$user" "$port" "found=0; for path in $search_paths; do if [ -d \"\$path\" ]; then files=\$(find \"\$path\" -maxdepth 4 \\( -name 'docker-compose.yml' -o -name 'docker-compose.yaml' -o -name 'compose.yml' -o -name 'compose.yaml' \\) -exec grep -l -i basecommerce {} \\; 2>/dev/null || true); if [ -n \"\$files\" ]; then found=1; echo \"\$files\" | xargs -r rm -f; fi; fi; done; if [ \"\$found\" -eq 1 ]; then echo 'BaseCommerce compose files removed'; else echo 'No BaseCommerce compose files found'; fi"
}

# Verify that BaseCommerce has been removed
verify_removal() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Verifying BaseCommerce removal"
    
    if [ "$DRY_RUN" = true ]; then
        log_dry_run "docker ps -a | grep -i basecommerce"
        log_dry_run "ss -lntp | grep -E ':(80|443)'"
        return 0
    fi
    
    log_info "Remaining Docker containers:"
    ssh_exec "$host" "$user" "$port" "docker ps -a --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null || echo 'Docker not installed'"
    
    log_info "Port listeners (80/443):"
    ssh_exec "$host" "$user" "$port" "ss -lntp | grep -E ':(80|443)' || echo 'Ports 80/443 are free'"
}

main() {
    init_script "$@"
    
    # Check confirmation
    if [ "${CONFIRM_REMOVE_BASECOMMERCE:-}" != "1" ]; then
        log_error "CONFIRM_REMOVE_BASECOMMERCE=1 is required to perform removal"
        log_info "Set CONFIRM_REMOVE_BASECOMMERCE=1 and run again"
        exit 1
    fi
    
    if [ -z "${TARGET_HOST:-}" ]; then
        log_error "Target host not specified. Use --host HOST"
        show_help
        exit 1
    fi
    
    local ssh_user="${VPS1_SSH_USER:-root}"
    local ssh_port="${VPS1_SSH_PORT:-22}"
    
    log_info "Starting BaseCommerce removal on $TARGET_HOST"
    
    # Check if Docker is installed
    if check_docker_installed "$TARGET_HOST" "$ssh_user" "$ssh_port"; then
        log_info "Docker is installed, removing BaseCommerce Docker resources"
        
        remove_basecommerce_containers "$TARGET_HOST" "$ssh_user" "$ssh_port"
        remove_basecommerce_images "$TARGET_HOST" "$ssh_user" "$ssh_port"
        remove_basecommerce_volumes "$TARGET_HOST" "$ssh_user" "$ssh_port"
        remove_basecommerce_networks "$TARGET_HOST" "$ssh_user" "$ssh_port"
    else
        log_info "Docker is not installed, skipping Docker resource removal"
    fi
    
    # Always search for directories and compose files
    remove_basecommerce_directories "$TARGET_HOST" "$ssh_user" "$ssh_port"
    remove_basecommerce_compose_files "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    # Verify removal
    verify_removal "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    log_success "BaseCommerce removal completed"
}

main "$@"

