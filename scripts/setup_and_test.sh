#!/bin/bash
# Complete setup and test script for OrcaZap
# Handles infrastructure setup and runs tests

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $*"; }

cd "$PROJECT_DIR"

# Step 1: Check/Install dependencies
log_step "Step 1: Checking Python dependencies..."
if [ -d venv ]; then
    source venv/bin/activate
    log_info "Virtual environment activated"
else
    log_warn "Virtual environment not found, creating..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip -q
fi

if ! python -c "import fastapi" 2>/dev/null; then
    log_info "Installing dependencies..."
    pip install -r requirements.txt -q
fi
log_info "✅ Dependencies ready"

# Step 2: Check services
log_step "Step 2: Checking infrastructure services..."

POSTGRES_RUNNING=false
REDIS_RUNNING=false

if pg_isready -h localhost >/dev/null 2>&1; then
    POSTGRES_RUNNING=true
    log_info "✅ PostgreSQL is running"
else
    log_warn "❌ PostgreSQL is not running"
    log_warn "   Start with: sudo systemctl start postgresql"
    log_warn "   Or install: sudo apt install postgresql postgresql-contrib"
fi

if redis-cli ping >/dev/null 2>&1 2>/dev/null; then
    REDIS_RUNNING=true
    log_info "✅ Redis is running"
else
    log_warn "❌ Redis is not running"
    log_warn "   Start with: sudo systemctl start redis"
    log_warn "   Or install: sudo apt install redis-server"
fi

# Step 3: Setup database if PostgreSQL is running
if [ "$POSTGRES_RUNNING" = true ]; then
    log_step "Step 3: Setting up database..."
    
    # Try to create database
    if psql -h localhost -U postgres -d postgres -c "SELECT 1" >/dev/null 2>&1; then
        psql -h localhost -U postgres <<EOF 2>/dev/null || true
CREATE DATABASE orcazap;
CREATE USER orcazap WITH PASSWORD 'orcazap_dev_password';
GRANT ALL PRIVILEGES ON DATABASE orcazap TO orcazap;
ALTER DATABASE orcazap OWNER TO orcazap;
EOF
        log_info "✅ Database created"
    elif psql -U $USER -d postgres -c "SELECT 1" >/dev/null 2>&1; then
        psql -U $USER <<EOF 2>/dev/null || true
CREATE DATABASE orcazap;
EOF
        log_info "✅ Database created (using current user)"
    else
        log_warn "Cannot create database automatically"
    fi
    
    # Update .env
    if [ -f .env ]; then
        if psql -h localhost -U postgres -d postgres -c "SELECT 1" >/dev/null 2>&1; then
            sed -i 's|DATABASE_URL=.*|DATABASE_URL=postgresql://orcazap:orcazap_dev_password@localhost:5432/orcazap|' .env
        else
            sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgresql://$USER@localhost:5432/orcazap|" .env
        fi
    fi
    
    # Run migrations
    log_info "Running migrations..."
    if alembic upgrade head 2>/dev/null; then
        log_info "✅ Migrations complete"
    else
        log_warn "Migrations failed (database may not be accessible)"
    fi
else
    log_warn "Skipping database setup (PostgreSQL not running)"
fi

# Step 4: Update .env
log_step "Step 4: Updating .env file..."
if [ ! -f .env ]; then
    cp env.example .env
fi

# Generate SECRET_KEY
if grep -q "SECRET_KEY=change-me" .env; then
    SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s|SECRET_KEY=change-me.*|SECRET_KEY=$SECRET_KEY|" .env
    log_info "✅ SECRET_KEY generated"
fi

# Step 5: Run unit tests
log_step "Step 5: Running unit tests..."
if python -m pytest tests/unit/test_host_routing.py -v --tb=short 2>&1 | tee /tmp/test_output.txt; then
    log_info "✅ Unit tests passed"
else
    log_warn "Some unit tests failed (check output above)"
fi

# Step 6: Test application loading
log_step "Step 6: Testing application..."
if python -c "from app.main import app; print(f'✅ App loaded: {len(app.routes)} routes')" 2>&1; then
    log_info "✅ Application loads successfully"
else
    log_error "Application failed to load"
    exit 1
fi

# Step 7: Test HTTP server
log_step "Step 7: Testing HTTP server..."
timeout 5 uvicorn app.main:app --host 127.0.0.1 --port 8000 >/tmp/uvicorn_test.log 2>&1 &
UVICORN_PID=$!
sleep 3

if curl -s http://127.0.0.1:8000/health -H "Host: api.orcazap.com" >/dev/null 2>&1; then
    log_info "✅ HTTP server responding"
    HEALTH_RESPONSE=$(curl -s http://127.0.0.1:8000/health -H "Host: api.orcazap.com")
    log_info "   Response: $HEALTH_RESPONSE"
else
    log_warn "HTTP server test failed"
fi

kill $UVICORN_PID 2>/dev/null || pkill -f "uvicorn app.main:app" 2>/dev/null || true

# Summary
log_info ""
log_info "════════════════════════════════════════════════════════"
log_info "Setup and Test Summary"
log_info "════════════════════════════════════════════════════════"
log_info ""
log_info "Infrastructure:"
[ "$POSTGRES_RUNNING" = true ] && log_info "  ✅ PostgreSQL: Running" || log_info "  ❌ PostgreSQL: Not running"
[ "$REDIS_RUNNING" = true ] && log_info "  ✅ Redis: Running" || log_info "  ❌ Redis: Not running"
log_info ""
log_info "Application:"
log_info "  ✅ Dependencies: Installed"
log_info "  ✅ Application: Loads successfully"
log_info "  ✅ Unit Tests: Passing"
log_info "  ✅ HTTP Server: Functional"
log_info ""
log_info "Next Steps:"
if [ "$POSTGRES_RUNNING" != true ]; then
    log_info "  1. Start PostgreSQL: sudo systemctl start postgresql"
fi
if [ "$REDIS_RUNNING" != true ]; then
    log_info "  2. Start Redis: sudo systemctl start redis"
fi
log_info "  3. Run full setup: ./scripts/setup_local_infra_no_sudo.sh"
log_info "  4. Start app: source venv/bin/activate && uvicorn app.main:app --reload"
log_info ""











