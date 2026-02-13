# OrcaZap Deployment Scripts

## Available Scripts

### 1. `setup_and_test.sh` - Quick Setup & Test (No Sudo)
Tests application without requiring infrastructure services.

**Usage:**
```bash
./scripts/setup_and_test.sh
```

**What it does:**
- Checks Python dependencies
- Verifies services (PostgreSQL, Redis) status
- Updates .env file
- Runs unit tests
- Tests application loading
- Tests HTTP server

**Requirements:** None (works without sudo)

### 2. `deploy_infrastructure.sh` - Full Infrastructure Setup (Requires Sudo)
Installs and configures PostgreSQL and Redis, runs migrations.

**Usage:**
```bash
sudo ./scripts/deploy_infrastructure.sh
```

**What it does:**
- Installs PostgreSQL (if not installed)
- Starts PostgreSQL service
- Creates database and user
- Installs Redis (if not installed)
- Starts Redis service
- Updates .env configuration
- Runs database migrations
- Tests infrastructure connections

**Requirements:** Sudo access

### 3. `setup_local_infra_no_sudo.sh` - Setup Without Sudo
Attempts to set up infrastructure using existing services.

**Usage:**
```bash
./scripts/setup_local_infra_no_sudo.sh
```

**What it does:**
- Checks for existing PostgreSQL/Redis
- Creates database (if accessible)
- Updates .env
- Runs migrations (if database accessible)

**Requirements:** PostgreSQL and Redis must be running and accessible

### 4. `start_services.sh` - Start Services
Attempts to start PostgreSQL and Redis services.

**Usage:**
```bash
./scripts/start_services.sh
```

**Requirements:** Sudo access (for systemctl)

## Recommended Workflow

### For Development (Local Testing)
```bash
# 1. Quick test without infrastructure
./scripts/setup_and_test.sh

# 2. If you have PostgreSQL/Redis running, setup database
./scripts/setup_local_infra_no_sudo.sh
```

### For Full Deployment
```bash
# 1. Deploy infrastructure (requires sudo)
sudo ./scripts/deploy_infrastructure.sh

# 2. Verify setup
./scripts/setup_and_test.sh

# 3. Start application
source venv/bin/activate
uvicorn app.main:app --reload
```

## Manual Service Start

If scripts can't start services automatically:

```bash
# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Start Redis
sudo systemctl start redis
sudo systemctl enable redis

# Verify
pg_isready -h localhost
redis-cli ping
```

## Troubleshooting

### PostgreSQL Not Starting
```bash
# Check status
sudo systemctl status postgresql

# Check logs
sudo journalctl -u postgresql -n 50

# Try manual start
sudo -u postgres /usr/lib/postgresql/*/bin/pg_ctl start -D /var/lib/postgresql/*/main
```

### Redis Not Starting
```bash
# Check status
sudo systemctl status redis

# Check logs
sudo journalctl -u redis -n 50
```

### Database Connection Issues
```bash
# Test connection
psql -h localhost -U postgres -d postgres

# Check .env file
cat .env | grep DATABASE_URL
```

## Environment Variables

After running setup scripts, check `.env` file:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string (default: `redis://localhost:6379/0`)
- `SECRET_KEY`: Auto-generated secure key

## Next Steps After Infrastructure Setup

1. **Run Integration Tests:**
   ```bash
   source venv/bin/activate
   pytest tests/integration/ -v
   ```

2. **Start Application:**
   ```bash
   source venv/bin/activate
   uvicorn app.main:app --reload
   ```

3. **Test Endpoints:**
   ```bash
   # Health check
   curl http://127.0.0.1:8000/health -H "Host: api.orcazap.com"
   
   # Landing page
   curl http://127.0.0.1:8000/ -H "Host: orcazap.com"
   ```








