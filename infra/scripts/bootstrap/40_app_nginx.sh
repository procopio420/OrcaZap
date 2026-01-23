#!/bin/bash
# Nginx bootstrap script for VPS1 (APP server)
# Installs and configures Nginx reverse proxy
# Usage: ./40_app_nginx.sh --host HOST [OPTIONS]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"
TEMPLATE_DIR="$SCRIPT_DIR/../../templates"

# Source library functions
source "$LIB_DIR/common.sh"
source "$LIB_DIR/ssh.sh"
source "$LIB_DIR/assert.sh"

show_help() {
    cat <<EOF
Usage: $(basename "$0") --host HOST [OPTIONS]

Installs and configures Nginx on VPS1 (APP server).

Options:
    --dry-run           Show what would be done without making changes
    --host HOST         Target host (required, should be VPS1)
    --clean             Clean existing configs before setup
    --help, -h          Show this help message

EOF
}

install_nginx() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Installing Nginx"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        export DEBIAN_FRONTEND=noninteractive
        
        # Install Nginx
        if ! command -v nginx >/dev/null 2>&1; then
            apt-get install -y -qq nginx
        else
            echo 'Nginx already installed'
        fi
    "
}

configure_nginx() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    local domain="${DOMAIN:-orcazap.example.com}"
    
    log_info "Configuring Nginx"
    
    # Check for Cloudflare origin certificates locally
    local cert_dir="$(cd "$SCRIPT_DIR/../../" && pwd)"
    local local_cert="$cert_dir/origin.pem"
    local local_key="$cert_dir/origin.key"
    local use_cloudflare_certs=false
    local cert_path="/etc/ssl/orcazap"
    
    if [ -f "$local_cert" ] && [ -f "$local_key" ]; then
        log_info "Found Cloudflare origin certificates"
        use_cloudflare_certs=true
        
        # Copy certificates to remote host
        log_info "Copying certificates to remote host"
        ssh_exec_sudo "$host" "$user" "$port" "
            mkdir -p $cert_path
            chmod 755 $cert_path
        "
        
        ssh_copy_file "$host" "$user" "$port" "$local_cert" "/tmp/origin.pem"
        ssh_copy_file "$host" "$user" "$port" "$local_key" "/tmp/origin.key"
        
        ssh_exec_sudo "$host" "$user" "$port" "
            mv /tmp/origin.pem $cert_path/origin.pem
            mv /tmp/origin.key $cert_path/origin.key
            chmod 644 $cert_path/origin.pem
            chmod 600 $cert_path/origin.key
            chown root:root $cert_path/origin.pem $cert_path/origin.key
        "
        
        log_success "Certificates copied to $cert_path"
    fi
    
    # Check if SSL certificates exist on remote host (Let's Encrypt or Cloudflare)
    local cert_exists=false
    if [ "$use_cloudflare_certs" = true ]; then
        cert_exists=true
    elif ssh_exec "$host" "$user" "$port" "test -f /etc/letsencrypt/live/$domain/fullchain.pem" >/dev/null 2>&1; then
        cert_exists=true
    fi
    
    # Render template
    local template_file="$TEMPLATE_DIR/nginx/orcazap.nginx.conf.tmpl"
    
    if [ ! -f "$template_file" ]; then
        log_error "Template file not found: $template_file"
        exit 1
    fi
    
    local config_content=$(cat "$template_file")
    config_content=$(echo "$config_content" | sed "s|\${DOMAIN}|$domain|g")
    
    # Update certificate paths if using Cloudflare certificates
    if [ "$use_cloudflare_certs" = true ]; then
        config_content=$(echo "$config_content" | sed "s|/etc/letsencrypt/live/\${DOMAIN}/fullchain.pem|$cert_path/origin.pem|g")
        config_content=$(echo "$config_content" | sed "s|/etc/letsencrypt/live/\${DOMAIN}/privkey.pem|$cert_path/origin.key|g")
        config_content=$(echo "$config_content" | sed "s|/etc/letsencrypt/live/\${DOMAIN}/chain.pem|$cert_path/origin.pem|g")
        # Also replace already substituted domain paths
        config_content=$(echo "$config_content" | sed "s|/etc/letsencrypt/live/$domain/fullchain.pem|$cert_path/origin.pem|g")
        config_content=$(echo "$config_content" | sed "s|/etc/letsencrypt/live/$domain/privkey.pem|$cert_path/origin.key|g")
        config_content=$(echo "$config_content" | sed "s|/etc/letsencrypt/live/$domain/chain.pem|$cert_path/origin.pem|g")
    fi
    
    # If certificates don't exist, create HTTP-only config
    if [ "$cert_exists" = false ]; then
        log_warning "SSL certificates not found - creating HTTP-only configuration"
        log_info "After obtaining certificates, re-run this script to enable HTTPS"
        
        # Generate HTTP-only config
        config_content="# OrcaZap Nginx Configuration (HTTP-only, SSL certificates not found)
# Supports: $domain, www.$domain, api.$domain, *.$domain
# Note: SSL will be enabled after certificates are obtained via Let's Encrypt

# Public site (apex + www)
server {
    listen 80;
    listen [::]:80;
    server_name $domain www.$domain;

    # Logging
    access_log /var/log/nginx/orcazap-public-access.log;
    error_log /var/log/nginx/orcazap-public-error.log;

    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Proxy to FastAPI
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Static files (if needed)
    location /static {
        alias /var/www/orcazap/static;
        expires 30d;
        add_header Cache-Control \"public, immutable\";
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
}

# API host
server {
    listen 80;
    listen [::]:80;
    server_name api.$domain;

    # Logging
    access_log /var/log/nginx/orcazap-api-access.log;
    error_log /var/log/nginx/orcazap-api-error.log;

    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Proxy to FastAPI
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
}

# Tenant subdomains (wildcard)
server {
    listen 80;
    listen [::]:80;
    server_name *.$domain;

    # Logging
    access_log /var/log/nginx/orcazap-tenant-access.log;
    error_log /var/log/nginx/orcazap-tenant-error.log;

    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Proxy to FastAPI
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Static files (if needed)
    location /static {
        alias /var/www/orcazap/static;
        expires 30d;
        add_header Cache-Control \"public, immutable\";
    }
}
"
    else
        if [ "$use_cloudflare_certs" = true ]; then
            log_info "Using Cloudflare origin certificates - full HTTPS configuration"
        else
            log_info "SSL certificates found - using full HTTPS configuration"
        fi
    fi
    
    # Write config to temp file
    local temp_config="/tmp/orcazap.nginx.conf.$$"
    echo "$config_content" > "$temp_config"
    
    # Copy to remote host
    ssh_copy_file "$host" "$user" "$port" "$temp_config" "/tmp/orcazap.nginx.conf"
    
    # Move to final location with backup
    ssh_exec_sudo "$host" "$user" "$port" "
        if [ -f /etc/nginx/sites-available/orcazap ]; then
            cp /etc/nginx/sites-available/orcazap /etc/nginx/sites-available/orcazap.backup.\$(date +%Y%m%d_%H%M%S)
        fi
        mv /tmp/orcazap.nginx.conf /etc/nginx/sites-available/orcazap
        
        # Enable site
        ln -sf /etc/nginx/sites-available/orcazap /etc/nginx/sites-enabled/orcazap
        
        # Remove default site
        rm -f /etc/nginx/sites-enabled/default
        
        # Test configuration
        nginx -t || {
            echo 'Nginx configuration test failed'
            echo 'Check /etc/nginx/sites-available/orcazap for errors'
            exit 1
        }
    "
    
    # Clean up
    rm -f "$temp_config"
}

restart_nginx() {
    local host="$1"
    local user="${2:-root}"
    local port="${3:-22}"
    
    log_info "Restarting Nginx"
    
    ssh_exec_sudo "$host" "$user" "$port" "
        systemctl restart nginx
        systemctl enable nginx
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
    
    # Should be VPS1
    if [ "$TARGET_HOST" != "${VPS1_HOST:-}" ]; then
        log_warning "This script is intended for VPS1 (APP server). Continuing anyway..."
    fi
    
    local ssh_user="${VPS1_SSH_USER:-root}"
    local ssh_port="${VPS1_SSH_PORT:-22}"
    
    log_info "Setting up Nginx on $TARGET_HOST"
    
    # Assert SSH connection
    assert_ssh_connection "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    # Clean if requested
    if [ "${CLEAN:-false}" = true ]; then
        log_info "Cleaning existing Nginx configs"
        ssh_exec_sudo "$TARGET_HOST" "$ssh_user" "$ssh_port" "
            rm -f /etc/nginx/sites-available/orcazap
            rm -f /etc/nginx/sites-enabled/orcazap
        "
    fi
    
    install_nginx "$TARGET_HOST" "$ssh_user" "$ssh_port"
    configure_nginx "$TARGET_HOST" "$ssh_user" "$ssh_port"
    restart_nginx "$TARGET_HOST" "$ssh_user" "$ssh_port"
    
    log_success "Nginx setup completed"
}

main "$@"

