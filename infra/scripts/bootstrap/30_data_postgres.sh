#!/bin/bash
# PostgreSQL bootstrap script for VPS2 (DATA server)
# Installs and configures PostgreSQL 15
# Usage: ./30_data_postgres.sh --host HOST [OPTIONS]

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

Installs and configures PostgreSQL 15 on VPS2 (DATA server).

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required, should be VPS2)
    --help, -h          Show this help message

EOF
}

install_postgresql() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Installing PostgreSQL 15"
    
    ssh_exec_sudo "$host" "$user" "$port" 'export DEBIAN_FRONTEND=noninteractive; if ! command -v psql >/dev/null 2>&1; then apt-get install -y -qq postgresql-15 postgresql-contrib-15; else echo "PostgreSQL already installed"; fi'
}

configure_postgresql() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local wg_ip="${4:-10.10.0.2}"
    
    log_info "Configuring PostgreSQL"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        # Backup existing config
        if [ -f /etc/postgresql/15/main/postgresql.conf ]; then
            cp /etc/postgresql/15/main/postgresql.conf /etc/postgresql/15/main/postgresql.conf.backup.\$(date +%Y%m%d_%H%M%S)
        fi
        
        # Configure to listen on WireGuard interface
        sed -i \"s|#listen_addresses = 'localhost'|listen_addresses = '127.0.0.1,$wg_ip'|g\" /etc/postgresql/15/main/postgresql.conf
        sed -i \"s|#port = 5432|port = 5432|g\" /etc/postgresql/15/main/postgresql.conf
        
        # Memory settings for 1GB RAM VPS
        sed -i \"s|#shared_buffers = 128MB|shared_buffers = 256MB|g\" /etc/postgresql/15/main/postgresql.conf
        sed -i \"s|#max_connections = 100|max_connections = 100|g\" /etc/postgresql/15/main/postgresql.conf
    "
}

configure_pg_hba() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local vps1_ip="${4:-10.10.0.1}"
    local vps3_ip="${5:-10.10.0.3}"
    
    log_info "Configuring PostgreSQL host-based authentication"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        # Backup existing pg_hba.conf
        if [ -f /etc/postgresql/15/main/pg_hba.conf ]; then
            cp /etc/postgresql/15/main/pg_hba.conf /etc/postgresql/15/main/pg_hba.conf.backup.\$(date +%Y%m%d_%H%M%S)
        fi
        
        # Add rules for VPS1 and VPS3
        if ! grep -q \"$vps1_ip/32\" /etc/postgresql/15/main/pg_hba.conf; then
            echo \"host    all    all    $vps1_ip/32    md5\" >> /etc/postgresql/15/main/pg_hba.conf
        fi
        if ! grep -q \"$vps3_ip/32\" /etc/postgresql/15/main/pg_hba.conf; then
            echo \"host    all    all    $vps3_ip/32    md5\" >> /etc/postgresql/15/main/pg_hba.conf
        fi
    "
}

create_database() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local db_name="${POSTGRES_DB:-orcazap}"
    local db_user="${POSTGRES_USER:-orcazap}"
    local db_password="${POSTGRES_PASSWORD:-}"
    
    if [ -z "$db_password" ]; then
        log_error "POSTGRES_PASSWORD not set in inventory"
        exit 1
    fi
    
    log_info "Creating database and user"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        sudo -u postgres psql <<EOF
-- Create user if not exists
DO \\\$\\\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '$db_user') THEN
        CREATE USER $db_user WITH PASSWORD '$db_password';
    ELSE
        ALTER USER $db_user WITH PASSWORD '$db_password';
    END IF;
END
\\\$\\\$;

-- Create database if not exists
SELECT 'CREATE DATABASE $db_name OWNER $db_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$db_name')\\gexec

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE $db_name TO $db_user;
EOF
    "
}

restart_postgresql() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Restarting PostgreSQL"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        systemctl restart postgresql
        systemctl enable postgresql
    "
}

main() {
    init_script "$@"
    load_inventory
    
    if [ -z "${TARGET_HOST:-}" ]; then
        TARGET_HOST="${VPS2_HOST:-}"
    fi
    
    if [ -z "$TARGET_HOST" ]; then
        log_error "Target host not specified. Use --host HOST or set VPS2_HOST"
        show_help
        exit 1
    fi
    
    # Should be VPS2
    if [ "$TARGET_HOST" != "${VPS2_HOST:-}" ]; then
        log_warning "This script is intended for VPS2 (DATA server). Continuing anyway..."
    fi
    
    local ssh_user="${VPS2_SSH_USER:-root}"
    local ssh_port="${VPS2_SSH_PORT:-22}"
    local wg_ip="${VPS2_WIREGUARD_IP:-10.10.0.2}"
    local vps1_ip="${VPS1_WIREGUARD_IP:-10.10.0.1}"
    local vps3_ip="${VPS3_WIREGUARD_IP:-10.10.0.3}"
    
    log_info "Setting up PostgreSQL on $TARGET_HOST"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    # Validate required variables
    validate_required_vars POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD
    
    install_postgresql "$TARGET_HOST" "$ssh_user" "$ssh_port"
    configure_postgresql "$TARGET_HOST" "$ssh_user" "$ssh_port" "$wg_ip"
    configure_pg_hba "$TARGET_HOST" "$ssh_user" "$ssh_port" "$vps1_ip" "$vps3_ip"
    create_database "$TARGET_HOST" "$ssh_user" "$ssh_port"
    restart_postgresql "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    log_success "PostgreSQL setup completed"
}

main "$@"

