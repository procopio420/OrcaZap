# OrcaZap Deployment Commands

## Prerequisites

1. **SSH Key Setup**: Place your SSH private key at `docs/infra/deploy_key` or set `SSH_PRIVATE_KEY` environment variable
2. **Inventory File**: Ensure `infra/inventory/hosts.env` is configured

## Deployment Steps

### Step 1: Set Environment Variables

```bash
export SSH_PRIVATE_KEY="$(pwd)/docs/infra/deploy_key"
export INVENTORY_FILE="$(pwd)/infra/inventory/hosts.env"
```

### Step 2: Deploy Application to VPS1 (APP)

```bash
./infra/scripts/deploy/deploy_app.sh --host 191.252.120.36
```

### Step 3: Deploy Workers to VPS3 (WORKER)

```bash
./infra/scripts/deploy/deploy_worker.sh --host 191.252.120.176
```

### Step 4: Run Database Migrations

```bash
./infra/scripts/deploy/migrate.sh --host 191.252.120.36
```

### Step 5: Start Services

```bash
# Start app on VPS1
./infra/scripts/deploy/restart.sh --host 191.252.120.36 --service app

# Start workers on VPS3
./infra/scripts/deploy/restart.sh --host 191.252.120.176 --service worker
```

### Step 6: Health Check

```bash
./infra/scripts/deploy/healthcheck.sh --host 191.252.120.36
```

### Step 7: Verify All Services

```bash
./infra/scripts/ops/test_services.sh
```

## All-in-One Deployment Script

```bash
#!/bin/bash
# Complete OrcaZap deployment

set -euo pipefail

export SSH_PRIVATE_KEY="$(pwd)/docs/infra/deploy_key"
export INVENTORY_FILE="$(pwd)/infra/inventory/hosts.env"

VPS1=191.252.120.36
VPS3=191.252.120.176

echo "🚀 Starting OrcaZap deployment..."

# Deploy app
echo "📦 Deploying app to VPS1..."
./infra/scripts/deploy/deploy_app.sh --host "$VPS1"

# Deploy workers
echo "📦 Deploying workers to VPS3..."
./infra/scripts/deploy/deploy_worker.sh --host "$VPS3"

# Run migrations
echo "🔄 Running migrations..."
./infra/scripts/deploy/migrate.sh --host "$VPS1"

# Start services
echo "🔄 Starting services..."
./infra/scripts/deploy/restart.sh --host "$VPS1" --service app
./infra/scripts/deploy/restart.sh --host "$VPS3" --service worker

# Health check
echo "🏥 Running health checks..."
./infra/scripts/deploy/healthcheck.sh --host "$VPS1"

# Final status
echo "📊 Final status..."
./infra/scripts/ops/test_services.sh

echo "✅ Deployment complete!"
```

## Expected Service Endpoints

After successful deployment:

- **FastAPI App**: `http://191.252.120.36:8000/health`
- **Nginx HTTP**: `http://191.252.120.36:80`
- **Nginx HTTPS**: `https://191.252.120.36:443`
- **PostgreSQL**: `191.252.120.182:5432` (via WireGuard: `10.10.0.2:5432`)
- **Redis**: `191.252.120.182:6379` (via WireGuard: `10.10.0.2:6379`)


