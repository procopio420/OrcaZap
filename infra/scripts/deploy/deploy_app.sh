#!/bin/bash
# Application deployment script for VPS1 (APP server)
# Deploys code, sets up venv, installs dependencies, restarts service
# Usage: ./deploy_app.sh --host HOST [OPTIONS]

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

Deploys application to VPS1 (APP server).

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
        # Ensure directory exists and is owned by app_user
        mkdir -p $app_dir
        chown -R $app_user:$app_user $app_dir
        
        if [ -d $app_dir/.git ]; then
            cd $app_dir
            sudo -u $app_user git fetch origin || exit 1
            sudo -u $app_user git checkout $branch || sudo -u $app_user git checkout -b $branch origin/$branch || exit 1
            sudo -u $app_user git pull origin $branch || exit 1
        elif [ -n '$repo_url' ]; then
            # Clone if repo URL provided
            if [ -d $app_dir ] && [ -n \"\$(ls -A $app_dir 2>/dev/null)\" ]; then
                # Directory exists with content, remove it
                rm -rf $app_dir/*
            fi
            sudo -u $app_user git clone $repo_url $app_dir || exit 1
            cd $app_dir
            sudo -u $app_user git checkout $branch || exit 1
        else
            echo 'REPO_URL not set' >&2
            exit 1
        fi
        
        # Ensure ownership after git operations
        chown -R $app_user:$app_user $app_dir
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

create_env_file() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local app_dir="${APP_DIR:-/opt/orcazap}"
    local app_user="${APP_USER:-orcazap}"
    local app_env_file="${APP_ENV_FILE:-/opt/orcazap/.env}"
    local vps2_wg_ip="${VPS2_WIREGUARD_IP:-10.10.0.2}"
    
    log_info "Creating .env file"
    
    # Generate SECRET_KEY if not set
    local secret_key="${SECRET_KEY:-}"
    if [ -z "$secret_key" ]; then
        secret_key=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || openssl rand -hex 32)
    fi
    
    # Build DATABASE_URL
    local db_url="postgresql://${POSTGRES_USER:-orcazap}:${POSTGRES_PASSWORD:-}@${vps2_wg_ip}:5432/${POSTGRES_DB:-orcazap}"
    
    # Build REDIS_URL (with password if set)
    local redis_url="redis://"
    if [ -n "${REDIS_PASSWORD:-}" ]; then
        redis_url="redis://:${REDIS_PASSWORD}@${vps2_wg_ip}:6379/0"
    else
        redis_url="redis://${vps2_wg_ip}:6379/0"
    fi
    
    # Create .env content
    local env_content="# Database
DATABASE_URL=$db_url

# Redis
REDIS_URL=$redis_url

# Application
SECRET_KEY=$secret_key
DEBUG=false
ENVIRONMENT=production

# WhatsApp Cloud API
WHATSAPP_VERIFY_TOKEN=${WHATSAPP_VERIFY_TOKEN:-change-me-random-string}
WHATSAPP_ACCESS_TOKEN=${WHATSAPP_ACCESS_TOKEN:-your-access-token-here}
WHATSAPP_PHONE_NUMBER_ID=${WHATSAPP_PHONE_NUMBER_ID:-your-phone-number-id}
WHATSAPP_BUSINESS_ACCOUNT_ID=${WHATSAPP_BUSINESS_ACCOUNT_ID:-your-waba-id}

# Security
BCRYPT_ROUNDS=12

# Admin
ADMIN_SESSION_SECRET=${ADMIN_SESSION_SECRET:-$secret_key}

# Operator Admin
OPERATOR_USERNAME=${OPERATOR_USERNAME:-admin}
OPERATOR_PASSWORD=${OPERATOR_PASSWORD:-change-me-in-production}

# Stripe
STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY:-}
STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET:-}
STRIPE_PRICE_ID=${STRIPE_PRICE_ID:-}
"
    
    # Write to temp file
    local temp_env="/tmp/orcazap.env.$$"
    echo "$env_content" > "$temp_env"
    
    # Copy to remote host
    ssh_copy_file "$host" "$user" "$port" "$temp_env" "/tmp/orcazap.env"
    
    # Move to final location
    ssh_exec_sudo "$host" "$user" "$port" "
        mv /tmp/orcazap.env $app_env_file
        chown $app_user:$app_user $app_env_file
        chmod 600 $app_env_file
    "
    
    # Clean up
    rm -f "$temp_env"
    
    log_info ".env file created at $app_env_file"
}

restart_service() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Restarting application service"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        systemctl daemon-reload
        systemctl enable orcazap-app || true
        
        # Check if service file exists
        if [ ! -f /etc/systemd/system/orcazap-app.service ]; then
            echo 'Service file not found: /etc/systemd/system/orcazap-app.service' >&2
            exit 1
        fi
        
        # Restart service and check status
        if ! systemctl restart orcazap-app; then
            echo 'Service restart failed. Checking status...' >&2
            systemctl status orcazap-app || true
            journalctl -u orcazap-app -n 50 --no-pager || true
            exit 1
        fi
        
        # Wait a moment and verify it's running
        sleep 2
        if ! systemctl is-active --quiet orcazap-app; then
            echo 'Service is not running after restart. Checking logs...' >&2
            systemctl status orcazap-app || true
            journalctl -u orcazap-app -n 50 --no-pager || true
            exit 1
        fi
    " || {
        log_error "Service restart failed. Check logs on $host"
        exit 1
    }
    
    log_success "Service restarted successfully"
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
        TARGET_HOST="${VPS1_HOST:-}"
    fi
    
    if [ -z "$TARGET_HOST" ]; then
        log_error "Target host not specified. Use --host HOST or set VPS1_HOST"
        show_help
        exit 1
    fi
    
    local ssh_user="${VPS1_SSH_USER:-root}"
    local ssh_port="${VPS1_SSH_PORT:-22}"
    
    log_info "Deploying application to $TARGET_HOST"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    # Clean if requested
    if [ "$do_clean" = true ]; then
        log_info "Cleaning before deployment"
        "$CLEANUP_DIR/cleanup_app.sh" --host "$TARGET_HOST" --code-only ${DRY_RUN:+--dry-run} || true
    fi
    
    deploy_code "$TARGET_HOST" "$ssh_user" "$ssh_port"
    setup_venv "$TARGET_HOST" "$ssh_user" "$ssh_port"
    install_dependencies "$TARGET_HOST" "$ssh_user" "$ssh_port"
    create_env_file "$TARGET_HOST" "$ssh_user" "$ssh_port"
    restart_service "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    log_success "Application deployment completed"
}

main "$@"

