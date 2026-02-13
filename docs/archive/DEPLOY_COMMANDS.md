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
./infra/scripts/deploy/deploy_app.sh --host <VPS1_HOST>
```

### Step 3: Deploy Workers to VPS3 (WORKER)

```bash
./infra/scripts/deploy/deploy_worker.sh --host <VPS3_HOST>
```

### Step 4: Run Database Migrations

```bash
./infra/scripts/deploy/migrate.sh --host <VPS1_HOST>
```

### Step 5: Start Services

```bash
# Start app on VPS1
./infra/scripts/deploy/restart.sh --host <VPS1_HOST> --service app

# Start workers on VPS3
./infra/scripts/deploy/restart.sh --host <VPS3_HOST> --service worker
```

### Step 6: Health Check

```bash
./infra/scripts/deploy/healthcheck.sh --host <VPS1_HOST>
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

VPS1=<VPS1_HOST>
VPS3=<VPS3_HOST>

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

- **FastAPI App**: `http://<VPS1_HOST>:8000/health`
- **Nginx HTTP**: `http://<VPS1_HOST>:80`
- **Nginx HTTPS**: `https://<VPS1_HOST>:443`
- **PostgreSQL**: `<VPS2_HOST>:5432` (via WireGuard: `10.10.0.2:5432`)
- **Redis**: `<VPS2_HOST>:6379` (via WireGuard: `10.10.0.2:6379`)


