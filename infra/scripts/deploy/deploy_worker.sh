#!/bin/bash
# Worker deployment script for VPS3 (WORKER server)
# Deploys code, sets up venv, installs dependencies, restarts services
# Usage: ./deploy_worker.sh --host HOST [OPTIONS]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"
CLEANUP_DIR="$SCRIPT_DIR/../cleanup"

# Source library functions
source "$LIB_DIR/common.sh"
source "$LIB_DIR/ssh.sh"
source "$LIB_DIR/assert.sh"

show_help() {
    cat <<EOF
Usage: $(basename "$0") --host HOST [OPTIONS]

Deploys worker to VPS3 (WORKER server).

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required)
    --clean             Clean before deploying (default: true)
    --no-clean          Skip cleanup before deploying
    --branch BRANCH     Git branch to deploy (default: main)
    --help, -h          Show this help message

EOF
}

deploy_code() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local app_dir="${APP_DIR:-/opt/orcazap}"
    local app_user="${APP_USER:-orcazap}"
    local branch="${DEPLOY_BRANCH:-main}"
    local repo_url="${REPO_URL:-}"
    
    log_info "Deploying code from branch: $branch"
    
    local repo_url="${REPO_URL:-}"
    local git_hash_before=""
    
    # Get current commit hash for rollback
    if [ "$DRY_RUN" = false ]; then
        git_hash_before=$(ssh_exec_sudo "$host" "$user" "$port" "
            if [ -d $app_dir/.git ]; then
                cd $app_dir && sudo -u $app_user git rev-parse HEAD 2>/dev/null || echo ''
            fi
        " || echo "")
    fi
    
    ssh_exec_sudo "$host" "$user" "$port" "
        if [ -d $app_dir/.git ]; then
            cd $app_dir
            sudo -u $app_user git fetch origin || exit 1
            sudo -u $app_user git checkout $branch || sudo -u $app_user git checkout -b $branch origin/$branch || exit 1
            sudo -u $app_user git pull origin $branch || exit 1
        elif [ -n '$repo_url' ]; then
            # Clone if repo URL provided and directory doesn't exist
            sudo -u $app_user git clone $repo_url $app_dir || exit 1
            cd $app_dir
            sudo -u $app_user git checkout $branch || exit 1
        else
            echo 'Git repository not found in $app_dir and REPO_URL not set' >&2
            exit 1
        fi
    " || {
        # Rollback on failure
        if [ -n "$git_hash_before" ] && [ "$DRY_RUN" = false ]; then
            log_warning "Deployment failed, rolling back to previous commit"
            ssh_exec_sudo "$host" "$user" "$port" "
                cd $app_dir && sudo -u $app_user git reset --hard $git_hash_before 2>/dev/null || true
            "
        fi
        log_error "Code deployment failed"
        exit 1
    }
}

setup_venv() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local app_dir="${APP_DIR:-/opt/orcazap}"
    local app_user="${APP_USER:-orcazap}"
    
    log_info "Setting up virtual environment"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        if [ ! -d $app_dir/venv ]; then
            sudo -u $app_user python3 -m venv $app_dir/venv
        fi
    "
}

install_dependencies() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local app_dir="${APP_DIR:-/opt/orcazap}"
    local app_user="${APP_USER:-orcazap}"
    
    log_info "Installing dependencies"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        cd $app_dir
        sudo -u $app_user $app_dir/venv/bin/pip install --upgrade pip
        if [ -f requirements.txt ]; then
            sudo -u $app_user $app_dir/venv/bin/pip install -r requirements.txt
        else
            echo 'requirements.txt not found' >&2
            exit 1
        fi
    "
}

restart_services() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local num_workers="${NUM_WORKERS:-4}"
    
    log_info "Restarting worker services (rolling restart: worker first)"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        systemctl daemon-reload
        
        # Stop workers first (drain jobs)
        for i in \$(seq 1 $num_workers); do
            systemctl stop orcazap-worker@\$i || true
        done
        
        # Enable and start workers
        for i in \$(seq 1 $num_workers); do
            systemctl enable orcazap-worker@\$i
            systemctl start orcazap-worker@\$i
        done
    "
}

parse_deploy_args() {
    local do_clean=true
    local deploy_branch="main"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --clean)
                do_clean=true
                shift
                ;;
            --no-clean)
                do_clean=false
                shift
                ;;
            --branch=*)
                deploy_branch="${1#*=}"
                shift
                ;;
            --branch)
                deploy_branch="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done
    
    export DO_CLEAN="$do_clean"
    export DEPLOY_BRANCH="$deploy_branch"
}

main() {
    init_script "$@"
    load_inventory
    
    # Parse deploy-specific arguments
    parse_deploy_args "$@"
    
    local do_clean="${DO_CLEAN:-true}"
    local deploy_branch="${DEPLOY_BRANCH:-main}"
    
    if [ -z "${TARGET_HOST:-}" ]; then
        TARGET_HOST="${VPS3_HOST:-}"
    fi
    
    if [ -z "$TARGET_HOST" ]; then
        log_error "Target host not specified. Use --host HOST or set VPS3_HOST"
        show_help
        exit 1
    fi
    
    local ssh_user="${VPS3_SSH_USER:-root}"
    local ssh_port="${VPS3_SSH_PORT:-22}"
    
    log_info "Deploying worker to $TARGET_HOST"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    # Clean if requested (skip if DRY_RUN to avoid confusion)
    if [ "$do_clean" = true ] && [ "${DRY_RUN:-false}" != "true" ]; then
        log_info "Cleaning before deployment"
        "$CLEANUP_DIR/cleanup_worker.sh" --host "$TARGET_HOST" --code-only || true
    fi
    
    deploy_code "$TARGET_HOST" "$ssh_user" "$ssh_port"
    setup_venv "$TARGET_HOST" "$ssh_user" "$ssh_port"
    install_dependencies "$TARGET_HOST" "$ssh_user" "$ssh_port"
    restart_services "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    log_success "Worker deployment completed"
}

main "$@"

