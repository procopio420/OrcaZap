#!/bin/bash
# Infrastructure deployment script for OrcaZap
# Uses existing bootstrap scripts adapted for local deployment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BOOTSTRAP_DIR="$PROJECT_DIR/infra/scripts/bootstrap"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $*"; }

# Check if running with sudo
check_sudo_access() {
    if [ "$EUID" -eq 0 ]; then
        return 0
    elif sudo -n true 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

install_postgresql_local() {
    log_step "Installing PostgreSQL..."
    
    if command -v psql >/dev/null 2>&1; then
        log_info "PostgreSQL client already installed"
    else
        log_info "Installing PostgreSQL..."
        sudo apt-get update -qq
        sudo apt-get install -y -qq postgresql postgresql-contrib
    fi
    
    # Start and enable PostgreSQL
    if ! sudo systemctl is-active --quiet postgresql; then
        log_info "Starting PostgreSQL service..."
        sudo systemctl start postgresql
        sudo systemctl enable postgresql
    fi
    
    # Wait for PostgreSQL to be ready
    log_info "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if pg_isready -h localhost >/dev/null 2>&1; then
            log_info "PostgreSQL is ready"
            return 0
        fi
        sleep 1
    done
    
    log_error "PostgreSQL failed to start"
    return 1
}

setup_postgresql_database() {
    log_step "Setting up PostgreSQL database..."
    
    sudo -u postgres psql <<EOF
-- Create database
SELECT 'CREATE DATABASE orcazap'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'orcazap')\gexec

-- Create user
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'orcazap') THEN
        CREATE USER orcazap WITH PASSWORD 'orcazap_dev_password';
    END IF;
END
\$\$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE orcazap TO orcazap;
ALTER DATABASE orcazap OWNER TO orcazap;
EOF
    
    log_info "Database 'orcazap' and user 'orcazap' created"
}

install_redis_local() {
    log_step "Installing Redis..."
    
    if command -v redis-cli >/dev/null 2>&1; then
        log_info "Redis already installed"
    else
        log_info "Installing Redis..."
        sudo apt-get update -qq
        sudo apt-get install -y -qq redis-server
    fi
    
    # Start and enable Redis
    if ! sudo systemctl is-active --quiet redis && ! sudo systemctl is-active --quiet redis-server; then
        log_info "Starting Redis service..."
        if sudo systemctl list-units --type=service | grep -q redis-server.service; then
            sudo systemctl start redis-server
            sudo systemctl enable redis-server
        else
            sudo systemctl start redis
            sudo systemctl enable redis
        fi
    fi
    
    # Test Redis
    sleep 2
    if redis-cli ping >/dev/null 2>&1; then
        log_info "Redis is ready"
        return 0
    else
        log_error "Redis failed to start"
        return 1
    fi
}

update_env_config() {
    log_step "Updating .env configuration..."
    
    cd "$PROJECT_DIR"
    
    if [ ! -f .env ]; then
        cp env.example .env
    fi
    
    # Update DATABASE_URL
    sed -i 's|^DATABASE_URL=.*|DATABASE_URL=postgresql://orcazap:orcazap_dev_password@localhost:5432/orcazap|' .env
    
    # Generate SECRET_KEY
    if grep -q "SECRET_KEY=change-me" .env || ! grep -q "^SECRET_KEY=" .env; then
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        if grep -q "^SECRET_KEY=" .env; then
            sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" .env
        else
            echo "SECRET_KEY=$SECRET_KEY" >> .env
        fi
        log_info "Generated SECRET_KEY"
    fi
    
    log_info ".env file configured"
}

run_migrations() {
    log_step "Running database migrations..."
    
    cd "$PROJECT_DIR"
    
    if [ -d venv ]; then
        source venv/bin/activate
    fi
    
    if ! command -v alembic >/dev/null 2>&1; then
        log_error "Alembic not found. Install dependencies first: pip install -r requirements.txt"
        return 1
    fi
    
    alembic upgrade head
    log_info "Migrations complete"
}

test_infrastructure() {
    log_step "Testing infrastructure..."
    
    cd "$PROJECT_DIR"
    
    if [ -d venv ]; then
        source venv/bin/activate
    fi
    
    # Test database
    log_info "Testing database connection..."
    python3 <<EOF
from app.settings import settings
from sqlalchemy import create_engine, text
try:
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT version()'))
        print('✅ Database connection successful')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    exit(1)
EOF
    
    # Test Redis
    log_info "Testing Redis connection..."
    python3 <<EOF
import redis
from app.settings import settings
try:
    r = redis.from_url(settings.redis_url)
    r.ping()
    print('✅ Redis connection successful')
except Exception as e:
    print(f'❌ Redis connection failed: {e}')
    exit(1)
EOF
    
    log_info "All infrastructure tests passed"
}

main() {
    log_info "════════════════════════════════════════════════════════"
    log_info "OrcaZap Infrastructure Deployment"
    log_info "════════════════════════════════════════════════════════"
    log_info ""
    
    if ! check_sudo_access; then
        log_error "This script requires sudo access"
        log_info "Please run with sudo or ensure passwordless sudo is configured"
        log_info "Or run: sudo $0"
        exit 1
    fi
    
    install_postgresql_local
    setup_postgresql_database
    install_redis_local
    update_env_config
    run_migrations
    test_infrastructure
    
    log_info ""
    log_info "════════════════════════════════════════════════════════"
    log_info "✅ Infrastructure deployment complete!"
    log_info "════════════════════════════════════════════════════════"
    log_info ""
    log_info "Services status:"
    log_info "  PostgreSQL: $(sudo systemctl is-active postgresql)"
    log_info "  Redis: $(sudo systemctl is-active redis 2>/dev/null || sudo systemctl is-active redis-server 2>/dev/null || echo 'unknown')"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Start application: source venv/bin/activate && uvicorn app.main:app --reload"
    log_info "  2. Test endpoints: curl http://127.0.0.1:8000/health -H 'Host: api.orcazap.com'"
    log_info "  3. Run integration tests: pytest tests/integration/ -v"
    log_info ""
}

main "$@"











