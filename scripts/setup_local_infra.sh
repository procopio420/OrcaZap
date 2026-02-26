#!/bin/bash
# Local infrastructure setup script for OrcaZap
# Sets up PostgreSQL, Redis, and runs migrations locally

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

check_command() {
    if command -v "$1" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Check if running as root for system operations
check_sudo() {
    if [ "$EUID" -eq 0 ]; then
        SUDO=""
    else
        SUDO="sudo"
        if ! sudo -n true 2>/dev/null; then
            log_warn "This script requires sudo privileges for some operations"
        fi
    fi
}

setup_postgresql() {
    log_info "Setting up PostgreSQL..."
    
    # Check if PostgreSQL is installed
    if ! check_command psql; then
        log_info "Installing PostgreSQL..."
        $SUDO apt-get update -qq
        $SUDO apt-get install -y -qq postgresql postgresql-contrib
    else
        log_info "PostgreSQL is already installed"
    fi
    
    # Start PostgreSQL service
    if ! $SUDO systemctl is-active --quiet postgresql; then
        log_info "Starting PostgreSQL service..."
        $SUDO systemctl start postgresql
        $SUDO systemctl enable postgresql
    else
        log_info "PostgreSQL service is already running"
    fi
    
    # Create database and user
    log_info "Creating database and user..."
    $SUDO -u postgres psql <<EOF || true
-- Create database if it doesn't exist
SELECT 'CREATE DATABASE orcazap'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'orcazap')\gexec

-- Create user if it doesn't exist
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
    
    log_info "PostgreSQL setup complete"
}

setup_redis() {
    log_info "Setting up Redis..."
    
    # Check if Redis is installed
    if ! check_command redis-cli; then
        log_info "Installing Redis..."
        $SUDO apt-get update -qq
        $SUDO apt-get install -y -qq redis-server
    else
        log_info "Redis is already installed"
    fi
    
    # Start Redis service
    if ! $SUDO systemctl is-active --quiet redis || ! $SUDO systemctl is-active --quiet redis-server; then
        log_info "Starting Redis service..."
        if $SUDO systemctl list-units --type=service | grep -q redis-server; then
            $SUDO systemctl start redis-server
            $SUDO systemctl enable redis-server
        else
            $SUDO systemctl start redis
            $SUDO systemctl enable redis
        fi
    else
        log_info "Redis service is already running"
    fi
    
    # Test Redis connection
    if redis-cli ping >/dev/null 2>&1 || $SUDO redis-cli ping >/dev/null 2>&1; then
        log_info "Redis is responding"
    else
        log_error "Redis is not responding"
        return 1
    fi
    
    log_info "Redis setup complete"
}

update_env_file() {
    log_info "Updating .env file..."
    
    cd "$PROJECT_DIR"
    
    if [ ! -f .env ]; then
        log_warn ".env file not found, creating from env.example"
        cp env.example .env
    fi
    
    # Update DATABASE_URL if it's still the default
    if grep -q "postgresql://orcazap:password@localhost" .env; then
        log_info "Updating DATABASE_URL in .env"
        sed -i 's|DATABASE_URL=postgresql://orcazap:password@localhost:5432/orcazap|DATABASE_URL=postgresql://orcazap:orcazap_dev_password@localhost:5432/orcazap|' .env
    fi
    
    # Generate SECRET_KEY if not set
    if grep -q "SECRET_KEY=change-me" .env; then
        log_info "Generating SECRET_KEY"
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        sed -i "s|SECRET_KEY=change-me.*|SECRET_KEY=$SECRET_KEY|" .env
    fi
    
    log_info ".env file updated"
}

run_migrations() {
    log_info "Running database migrations..."
    
    cd "$PROJECT_DIR"
    
    # Activate virtual environment if it exists
    if [ -d venv ]; then
        source venv/bin/activate
    fi
    
    # Check if alembic is available
    if ! command -v alembic >/dev/null 2>&1; then
        log_error "Alembic not found. Please install dependencies: pip install -r requirements.txt"
        return 1
    fi
    
    # Run migrations
    alembic upgrade head
    
    log_info "Migrations complete"
}

test_setup() {
    log_info "Testing setup..."
    
    cd "$PROJECT_DIR"
    
    # Activate virtual environment if it exists
    if [ -d venv ]; then
        source venv/bin/activate
    fi
    
    # Test database connection
    log_info "Testing database connection..."
    python3 -c "
from app.settings import settings
from sqlalchemy import create_engine, text
engine = create_engine(settings.database_url)
with engine.connect() as conn:
    result = conn.execute(text('SELECT 1'))
    print('✅ Database connection successful')
" || {
        log_error "Database connection failed"
        return 1
    }
    
    # Test Redis connection
    log_info "Testing Redis connection..."
    python3 -c "
import redis
from app.settings import settings
r = redis.from_url(settings.redis_url)
r.ping()
print('✅ Redis connection successful')
" || {
        log_error "Redis connection failed"
        return 1
    }
    
    log_info "All tests passed!"
}

main() {
    log_info "Starting local infrastructure setup..."
    
    check_sudo
    
    setup_postgresql
    setup_redis
    update_env_file
    run_migrations
    test_setup
    
    log_info ""
    log_info "════════════════════════════════════════════════════════"
    log_info "✅ Infrastructure setup complete!"
    log_info "════════════════════════════════════════════════════════"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Review .env file and update production values"
    log_info "  2. Start the application: uvicorn app.main:app --reload"
    log_info "  3. Test endpoints: curl http://127.0.0.1:8000/health -H 'Host: api.orcazap.com'"
    log_info ""
}

main "$@"











