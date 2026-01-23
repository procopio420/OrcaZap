# OrcaZap Infrastructure

Complete infrastructure automation for OrcaZap deployment on 3 VPS instances (Locaweb, Debian 12) with WireGuard private network, systemd services, and automated CI/CD.

## Quickstart

### 1. Copy Inventory Template

```bash
cp infra/inventory/hosts.example.env infra/inventory/hosts.env
```

### 2. Configure Inventory

Edit `infra/inventory/hosts.env` with your actual values:
- VPS hostnames/IPs
- SSH user and port
- WireGuard keys (private/public keys for each VPS)
- Database passwords
- Other secrets

**Important**: Never commit `hosts.env` to git. It contains sensitive information.

### 3. Set Environment Variables

```bash
export SSH_PRIVATE_KEY="$(cat ~/.ssh/id_rsa)"
export INVENTORY_FILE="infra/inventory/hosts.env"
```

### 4. Choose Deployment Mode

#### Option A: Terraform-Orchestrated (Recommended)

```bash
cd infra/terraform
terraform init
terraform plan
terraform apply
```

Terraform will orchestrate all bootstrap scripts via SSH.

#### Option B: Direct Bash (For Debugging)

```bash
# Bootstrap VPS1 (APP)
./infra/scripts/bootstrap/00_prereqs.sh --host vps1.example.com
./infra/scripts/bootstrap/10_wireguard.sh --host vps1.example.com
./infra/scripts/bootstrap/20_firewall.sh --host vps1.example.com
# ... continue with other scripts

# Bootstrap VPS2 (DATA)
./infra/scripts/bootstrap/00_prereqs.sh --host vps2.example.com
./infra/scripts/bootstrap/10_wireguard.sh --host vps2.example.com
# ... continue

# Bootstrap VPS3 (WORKERS)
./infra/scripts/bootstrap/00_prereqs.sh --host vps3.example.com
./infra/scripts/bootstrap/10_wireguard.sh --host vps3.example.com
# ... continue
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   3 VPS (WireGuard 10.10.0.0/24)            │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐         │
│  │ VPS1 APP │      │VPS2 DATA │      │VPS3 WORK │         │
│  │10.10.0.1 │◄─────►│10.10.0.2 │◄─────►│10.10.0.3 │         │
│  │nginx     │      │postgres  │      │rq worker │         │
│  │fastapi   │      │redis     │      │systemd    │         │
│  │pgbouncer │      │backups   │      │           │         │
│  └──────────┘      └──────────┘      └──────────┘         │
└─────────────────────────────────────────────────────────────┘
```

- **VPS1 (APP)**: Nginx reverse proxy, FastAPI application, PgBouncer
- **VPS2 (DATA)**: PostgreSQL, Redis, backups
- **VPS3 (WORKERS)**: RQ workers for background job processing

## Validation Checklist

After bootstrap, verify everything is working:

### WireGuard Connectivity

```bash
# From VPS1, ping VPS2 and VPS3
ping -c 3 10.10.0.2
ping -c 3 10.10.0.3

# From VPS2, ping VPS1 and VPS3
ping -c 3 10.10.0.1
ping -c 3 10.10.0.3

# From VPS3, ping VPS1 and VPS2
ping -c 3 10.10.0.1
ping -c 3 10.10.0.2
```

### PostgreSQL Connectivity

```bash
# From VPS1 (via PgBouncer)
psql -h 127.0.0.1 -p 6432 -U orcazap -d orcazap -c "SELECT version();"

# From VPS3 (direct to VPS2)
psql -h 10.10.0.2 -p 5432 -U orcazap -d orcazap -c "SELECT version();"
```

### Redis Connectivity

```bash
# From VPS1
redis-cli -h 10.10.0.2 -p 6379 -a "$REDIS_PASSWORD" ping

# From VPS3
redis-cli -h 10.10.0.2 -p 6379 -a "$REDIS_PASSWORD" ping
```

### Systemd Services

```bash
# On VPS1
systemctl status orcazap-app
systemctl status nginx
systemctl status pgbouncer

# On VPS3
systemctl status orcazap-worker@1
systemctl status orcazap-worker@2
systemctl status orcazap-worker@3
systemctl status orcazap-worker@4
```

### Application Health

```bash
# Health check endpoint (direct)
curl http://localhost:8000/health

# Via Nginx (if configured)
curl http://vps1.example.com/health

# Multi-domain health checks
curl -H "Host: api.orcazap.com" http://vps1.example.com/health
curl -H "Host: orcazap.com" http://vps1.example.com/
curl -H "Host: test-tenant.orcazap.com" http://vps1.example.com/
```

## Cleanup Procedures

### BaseCommerce Removal

The `ops/` directory contains scripts to remove BaseCommerce (an old project) and optionally Docker from hosts.

#### `remove_basecommerce.sh`

Removes all BaseCommerce containers, images, volumes, networks, directories, and compose files.

**Requirements:**
- `CONFIRM_REMOVE_BASECOMMERCE=1` environment variable must be set

**Usage:**
```bash
export SSH_PRIVATE_KEY="$(pwd)/docs/infra/deploy_key"
export INVENTORY_FILE="$(pwd)/infra/inventory/hosts.env"

# Dry run
CONFIRM_REMOVE_BASECOMMERCE=1 ./infra/scripts/ops/remove_basecommerce.sh --host 191.252.120.36 --dry-run

# Actual removal
CONFIRM_REMOVE_BASECOMMERCE=1 ./infra/scripts/ops/remove_basecommerce.sh --host 191.252.120.36
```

**What it does:**
- Stops and removes all Docker containers with "basecommerce" in the name (case-insensitive)
- Removes all Docker images with "basecommerce" in the repository/tag
- Removes all Docker volumes and networks matching "basecommerce"
- Searches and removes BaseCommerce directories in `/opt`, `/srv`, `/root`, `/home`, `/var/www`
- Removes docker-compose files that reference BaseCommerce
- Frees ports 80/443 for OrcaZap nginx

#### `remove_docker.sh`

Completely removes Docker from the host (packages, services, directories).

**Requirements:**
- `CONFIRM_REMOVE_DOCKER=1` environment variable must be set

**Usage:**
```bash
export SSH_PRIVATE_KEY="$(pwd)/docs/infra/deploy_key"
export INVENTORY_FILE="$(pwd)/infra/inventory/hosts.env"

# Dry run
CONFIRM_REMOVE_DOCKER=1 ./infra/scripts/ops/remove_docker.sh --host 191.252.120.36 --dry-run

# Actual removal
CONFIRM_REMOVE_DOCKER=1 ./infra/scripts/ops/remove_docker.sh --host 191.252.120.36
```

**What it does:**
- Stops and disables Docker and containerd services
- Purges Docker packages (docker.io, docker-ce, containerd, runc, etc.)
- Removes Docker directories (`/var/lib/docker`, `/var/lib/containerd`, `/etc/docker`)
- Runs `apt autoremove` to clean up dependencies

**Rollback:** If you need to reinstall Docker later:
```bash
# On the server
apt-get update
apt-get install -y docker.io docker-compose
systemctl enable docker
systemctl start docker
```

#### `verify_clean_host.sh`

Verifies that the host is clean of BaseCommerce artifacts.

**Usage:**
```bash
export SSH_PRIVATE_KEY="$(pwd)/docs/infra/deploy_key"
export INVENTORY_FILE="$(pwd)/infra/inventory/hosts.env"

./infra/scripts/ops/verify_clean_host.sh --host 191.252.120.36
```

**What it checks:**
- Docker installation status
- Port listeners for 80/443/8000
- BaseCommerce files/directories in common paths
- BaseCommerce Docker containers (if Docker is installed)

**Exit code:**
- `0` if host is clean (no BaseCommerce artifacts)
- `1` if BaseCommerce artifacts are found

#### Complete Cleanup Workflow

To completely remove BaseCommerce and Docker from a host:

```bash
export SSH_PRIVATE_KEY="$(pwd)/docs/infra/deploy_key"
export INVENTORY_FILE="$(pwd)/infra/inventory/hosts.env"
export TARGET_HOST=191.252.120.36

# Step 1: Remove BaseCommerce
CONFIRM_REMOVE_BASECOMMERCE=1 ./infra/scripts/ops/remove_basecommerce.sh --host "$TARGET_HOST"

# Step 2: (Optional) Remove Docker completely
CONFIRM_REMOVE_DOCKER=1 ./infra/scripts/ops/remove_docker.sh --host "$TARGET_HOST"

# Step 3: Verify cleanup
./infra/scripts/ops/verify_clean_host.sh --host "$TARGET_HOST"
```

**Note:** After removing BaseCommerce, ports 80/443 will be free for OrcaZap nginx configuration.

### Full Cleanup (Before Fresh Deployment)

```bash
# Clean VPS1 (APP)
./infra/scripts/cleanup/cleanup_app.sh --host vps1.example.com

# Clean VPS3 (WORKER)
./infra/scripts/cleanup/cleanup_worker.sh --host vps3.example.com

# Clean VPS2 (DATA) - optional, preserves DB/Redis
./infra/scripts/cleanup/cleanup_data.sh --host vps2.example.com
```

### Dry-Run Cleanup

```bash
# See what would be deleted without actually deleting
./infra/scripts/cleanup/cleanup_app.sh --host vps1.example.com --dry-run
```

### Selective Cleanup

```bash
# Clean only code and venv
./infra/scripts/cleanup/cleanup_app.sh --host vps1.example.com --code-only

# Clean only services
./infra/scripts/cleanup/cleanup_app.sh --host vps1.example.com --services-only

# Clean only logs
./infra/scripts/cleanup/cleanup_app.sh --host vps1.example.com --logs-only
```

## Rollback Procedures

### Restore Template Backups

All config files are backed up before modification to:
- `/tmp/orcazap-backups/` (temporary backups)
- Original location with `.backup.YYYYMMDD_HHMMSS` suffix

```bash
# Find backups
ls -la /etc/wireguard/wg0.conf.backup.*
ls -la /etc/nginx/sites-available/orcazap.backup.*

# Restore from backup
cp /etc/wireguard/wg0.conf.backup.20240121_120000 /etc/wireguard/wg0.conf
systemctl restart wg-quick@wg0
```

### Restore from Cleanup Backups

```bash
# Cleanup scripts backup critical files to /tmp/orcazap-backups/
ls -la /tmp/orcazap-backups/

# Restore systemd service
cp /tmp/orcazap-backups/orcazap-app.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable orcazap-app
systemctl start orcazap-app
```

## Password Rotation

### PostgreSQL Password

```bash
# On VPS2
sudo -u postgres psql -c "ALTER USER orcazap WITH PASSWORD 'new_password';"

# Update PgBouncer userlist.txt on VPS1
# Generate MD5 hash: echo -n "username:password" | md5sum
# Update /etc/pgbouncer/userlist.txt

# Update application .env file on VPS1 and VPS3
# Update DATABASE_URL in /opt/orcazap/.env

# Restart services
systemctl restart pgbouncer
systemctl restart orcazap-app
```

### Redis Password

```bash
# On VPS2
redis-cli -a old_password CONFIG SET requirepass new_password

# Update application .env file on VPS1 and VPS3
# Update REDIS_URL in /opt/orcazap/.env

# Restart services
systemctl restart orcazap-app
systemctl restart orcazap-worker@*
```

## Deployment

### Multi-Domain SaaS Deployment

The application supports multi-domain architecture:
- `orcazap.com` / `www.orcazap.com` - Public site
- `api.orcazap.com` - API host (webhooks, operator admin)
- `*.orcazap.com` - Tenant subdomains

**Full Deployment Workflow:**

```bash
# 1. Bootstrap infrastructure (if not done)
# VPS2 (DATA server) - PostgreSQL and Redis
./infra/scripts/bootstrap/30_data_postgres.sh --host vps2.example.com
./infra/scripts/bootstrap/31_data_redis.sh --host vps2.example.com

# VPS1 (APP server) - Nginx and application service
./infra/scripts/bootstrap/40_app_nginx.sh --host vps1.example.com
./infra/scripts/bootstrap/50_app_service.sh --host vps1.example.com

# 2. Deploy application code
./infra/scripts/deploy/deploy_app.sh --host vps1.example.com

# 3. Run database migrations
./infra/scripts/deploy/migrate.sh --host vps1.example.com

# 4. Deploy workers (VPS3)
./infra/scripts/deploy/deploy_worker.sh --host vps3.example.com

# 5. Health check
./infra/scripts/deploy/healthcheck.sh --host vps1.example.com
```

**Important:** Make sure `DOMAIN` is set correctly in `infra/inventory/hosts.env`:
```bash
DOMAIN=orcazap.com  # Not orcazap.example.com
```

The Nginx template automatically configures all domains using `${DOMAIN}` variable.

### Manual Deployment

```bash
# Deploy app to VPS1
./infra/scripts/deploy/deploy_app.sh --host vps1.example.com

# Deploy worker to VPS3
./infra/scripts/deploy/deploy_worker.sh --host vps3.example.com

# Run migrations
./infra/scripts/deploy/migrate.sh --host vps1.example.com

# Health check
./infra/scripts/deploy/healthcheck.sh --host vps1.example.com
```

### Deployment with Cleanup

```bash
# Deploy with cleanup (default)
./infra/scripts/deploy/deploy_app.sh --host vps1.example.com --clean

# Deploy without cleanup
./infra/scripts/deploy/deploy_app.sh --host vps1.example.com --no-clean
```

### Rolling Restart Order

Deployments use **worker-first** restart order:
1. Stop workers (drain jobs)
2. Deploy and restart workers
3. Deploy and restart app

This ensures jobs are processed before app changes.

## Troubleshooting

### WireGuard Not Connecting

```bash
# Check WireGuard status
wg show
systemctl status wg-quick@wg0

# Check firewall
ufw status
ufw allow 51820/udp

# Check WireGuard config
cat /etc/wireguard/wg0.conf
```

### PostgreSQL Connection Issues

```bash
# Check PostgreSQL is listening on WireGuard interface
ss -tlnp | grep 5432

# Check pg_hba.conf
cat /etc/postgresql/15/main/pg_hba.conf

# Check PostgreSQL logs
journalctl -u postgresql -n 50
```

### Redis Connection Issues

```bash
# Check Redis is listening on WireGuard interface
ss -tlnp | grep 6379

# Test Redis connection
redis-cli -h 10.10.0.2 -p 6379 -a "$REDIS_PASSWORD" ping

# Check Redis logs
journalctl -u redis -n 50
```

### Application Not Starting

```bash
# Check systemd status
systemctl status orcazap-app
journalctl -u orcazap-app -n 50

# Check application logs
tail -f /var/log/orcazap/app.log

# Check environment file
cat /opt/orcazap/.env
```

### Worker Not Processing Jobs

```bash
# Check worker status
systemctl status orcazap-worker@1

# Check worker logs
journalctl -u orcazap-worker@1 -n 50

# Check Redis queue
redis-cli -h 10.10.0.2 -p 6379 -a "$REDIS_PASSWORD" LLEN rq:queue:default
```

## Script Safety

All scripts follow strict safety rules:

- **Idempotent**: Safe to run multiple times
- **Dry-run mode**: Test without making changes (`--dry-run`)
- **Atomic writes**: Write to temp file, then move to final location
- **Backups**: Config files backed up before modification
- **Error handling**: `set -euo pipefail` for strict error checking

## CI/CD Integration

### CI (Continuous Integration)

Runs on every PR and push to main:
- Python linting (ruff)
- Formatting checks
- Type checking (mypy)
- Tests (pytest)
- Infrastructure validation:
  - Terraform fmt/validate
  - Shellcheck on all bash scripts
  - Shfmt formatting check
  - Dry-run of bootstrap scripts

### CD (Continuous Deployment)

Manual deployment via GitHub Actions:
- Requires manual approval (GitHub Environments)
- Deploys to production VPS via SSH
- Runs cleanup before deployment
- Executes migrations
- Health check gating
- On failure: prints systemd status and logs

## File Structure

```
infra/
├── README.md (this file)
├── inventory/
│   └── hosts.example.env
├── terraform/
│   ├── versions.tf
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── scripts/
│   ├── lib/          # Shared library functions
│   ├── bootstrap/    # Initial provisioning scripts
│   ├── cleanup/      # Cleanup scripts
│   └── deploy/       # Deployment scripts
└── templates/        # Configuration templates
```

## Support

For issues or questions:
1. Check this README
2. Review script logs
3. Check systemd journal logs
4. Review GitHub Actions workflow logs

