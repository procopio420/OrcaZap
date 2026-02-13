#!/bin/bash
# Local infrastructure setup script (no sudo version)
# Sets up database and runs migrations using existing services

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

check_postgresql() {
    log_info "Checking PostgreSQL..."
    
    if command -v psql >/dev/null 2>&1; then
        log_info "PostgreSQL client found"
        
        # Try to connect
        if psql -h localhost -U postgres -d postgres -c "SELECT 1" >/dev/null 2>&1 || \
           psql -h localhost -U $USER -d postgres -c "SELECT 1" >/dev/null 2>&1 || \
           psql -d postgres -c "SELECT 1" >/dev/null 2>&1; then
            log_info "PostgreSQL is accessible"
            return 0
        else
            log_warn "PostgreSQL is installed but not accessible"
            log_warn "Please start PostgreSQL manually: sudo systemctl start postgresql"
            return 1
        fi
    else
        log_warn "PostgreSQL client not found"
        log_warn "Please install PostgreSQL: sudo apt install postgresql postgresql-contrib"
        return 1
    fi
}

setup_database() {
    log_info "Setting up database..."
    
    # Try different connection methods
    PSQL_CMD=""
    if psql -h localhost -U postgres -d postgres -c "SELECT 1" >/dev/null 2>&1; then
        PSQL_CMD="psql -h localhost -U postgres"
    elif psql -U $USER -d postgres -c "SELECT 1" >/dev/null 2>&1; then
        PSQL_CMD="psql -U $USER"
    elif psql -d postgres -c "SELECT 1" >/dev/null 2>&1; then
        PSQL_CMD="psql"
    else
        log_error "Cannot connect to PostgreSQL"
        return 1
    fi
    
    log_info "Creating database and user..."
    $PSQL_CMD <<EOF || true
-- Create database if it doesn't exist
SELECT 'CREATE DATABASE orcazap'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'orcazap')\gexec

-- Create user if it doesn't exist (may fail if user exists, that's OK)
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'orcazap') THEN
        CREATE USER orcazap WITH PASSWORD 'orcazap_dev_password';
    END IF;
EXCEPTION WHEN OTHERS THEN
    -- User might already exist, ignore
    NULL;
END
\$\$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE orcazap TO orcazap;
ALTER DATABASE orcazap OWNER TO orcazap;
EOF
    
    log_info "Database setup complete"
}

check_redis() {
    log_info "Checking Redis..."
    
    if command -v redis-cli >/dev/null 2>&1; then
        if redis-cli ping >/dev/null 2>&1; then
            log_info "Redis is running and accessible"
            return 0
        else
            log_warn "Redis client found but server not responding"
            log_warn "Please start Redis manually: sudo systemctl start redis"
            return 1
        fi
    else
        log_warn "Redis not found"
        log_warn "Please install Redis: sudo apt install redis-server"
        return 1
    fi
}

update_env_file() {
    log_info "Updating .env file..."
    
    cd "$PROJECT_DIR"
    
    if [ ! -f .env ]; then
        log_warn ".env file not found, creating from env.example"
        cp env.example .env
    fi
    
    # Try to detect database connection string
    DB_URL=""
    if psql -h localhost -U postgres -d postgres -c "SELECT 1" >/dev/null 2>&1; then
        DB_URL="postgresql://orcazap:orcazap_dev_password@localhost:5432/orcazap"
    elif psql -U $USER -d postgres -c "SELECT 1" >/dev/null 2>&1; then
        DB_URL="postgresql://$USER@localhost:5432/orcazap"
    else
        DB_URL="postgresql://orcazap:orcazap_dev_password@localhost:5432/orcazap"
    fi
    
    # Update DATABASE_URL
    if grep -q "^DATABASE_URL=" .env; then
        sed -i "s|^DATABASE_URL=.*|DATABASE_URL=$DB_URL|" .env
        log_info "Updated DATABASE_URL in .env"
    else
        echo "DATABASE_URL=$DB_URL" >> .env
        log_info "Added DATABASE_URL to .env"
    fi
    
    # Generate SECRET_KEY if not set
    if grep -q "SECRET_KEY=change-me" .env || ! grep -q "^SECRET_KEY=" .env; then
        log_info "Generating SECRET_KEY"
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "change-me-in-production-$(date +%s)")
        if grep -q "^SECRET_KEY=" .env; then
            sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" .env
        else
            echo "SECRET_KEY=$SECRET_KEY" >> .env
        fi
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
try:
    engine = create_engine(settings.database_url)
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print('✅ Database connection successful')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    exit(1)
" || {
        log_error "Database connection test failed"
        return 1
    }
    
    # Test Redis connection
    log_info "Testing Redis connection..."
    python3 -c "
import redis
from app.settings import settings
try:
    r = redis.from_url(settings.redis_url)
    r.ping()
    print('✅ Redis connection successful')
except Exception as e:
    print(f'❌ Redis connection failed: {e}')
    exit(1)
" || {
        log_warn "Redis connection test failed (non-critical for basic testing)"
    }
    
    log_info "Setup tests complete!"
}

main() {
    log_info "Starting local infrastructure setup (no sudo)..."
    log_info ""
    
    if check_postgresql; then
        setup_database
    else
        log_error "PostgreSQL setup skipped - please configure manually"
    fi
    
    check_redis || log_warn "Redis check failed - sessions may not work"
    
    update_env_file
    run_migrations
    test_setup
    
    log_info ""
    log_info "════════════════════════════════════════════════════════"
    log_info "✅ Infrastructure setup complete!"
    log_info "════════════════════════════════════════════════════════"
    log_info ""
    log_info "Next steps:"
    log_info "  1. Review .env file"
    log_info "  2. Start app: source venv/bin/activate && uvicorn app.main:app --reload"
    log_info "  3. Test: curl http://127.0.0.1:8000/health -H 'Host: api.orcazap.com'"
    log_info ""
}

main "$@"








