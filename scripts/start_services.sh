#!/bin/bash
# Start required services for OrcaZap development
# This script attempts to start PostgreSQL and Redis

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

start_postgresql() {
    log_info "Attempting to start PostgreSQL..."
    
    # Try different service names
    if systemctl list-units --type=service | grep -q "postgresql.service"; then
        if sudo systemctl start postgresql 2>/dev/null; then
            log_info "PostgreSQL started successfully"
            return 0
        fi
    fi
    
    if systemctl list-units --type=service | grep -q "postgresql@"; then
        if sudo systemctl start postgresql@*.service 2>/dev/null; then
            log_info "PostgreSQL started successfully"
            return 0
        fi
    fi
    
    # Try pg_ctl if available
    if command -v pg_ctl >/dev/null 2>&1; then
        PG_DATA=$(pg_config --sharedir 2>/dev/null | sed 's|/share||')/../data
        if [ -d "$PG_DATA" ] && [ -w "$PG_DATA" ]; then
            pg_ctl start -D "$PG_DATA" 2>/dev/null && log_info "PostgreSQL started" && return 0
        fi
    fi
    
    log_warn "Could not start PostgreSQL automatically"
    log_warn "Please start manually: sudo systemctl start postgresql"
    return 1
}

start_redis() {
    log_info "Attempting to start Redis..."
    
    if systemctl list-units --type=service | grep -q "redis"; then
        if sudo systemctl start redis 2>/dev/null || sudo systemctl start redis-server 2>/dev/null; then
            log_info "Redis started successfully"
            return 0
        fi
    fi
    
    # Try to start redis-server directly if in PATH
    if command -v redis-server >/dev/null 2>&1; then
        if ! pgrep -x redis-server >/dev/null; then
            redis-server --daemonize yes 2>/dev/null && log_info "Redis started" && return 0
        fi
    fi
    
    log_warn "Could not start Redis automatically"
    log_warn "Please start manually: sudo systemctl start redis"
    return 1
}

main() {
    log_info "Starting OrcaZap services..."
    
    start_postgresql
    start_redis
    
    log_info ""
    log_info "Checking service status..."
    
    # Check PostgreSQL
    if pg_isready -h localhost >/dev/null 2>&1; then
        log_info "✅ PostgreSQL is running"
    else
        log_warn "❌ PostgreSQL is not running"
    fi
    
    # Check Redis
    if redis-cli ping >/dev/null 2>&1; then
        log_info "✅ Redis is running"
    else
        log_warn "❌ Redis is not running"
    fi
}

main "$@"








