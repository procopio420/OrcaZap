#!/bin/bash
# Test all services on all 3 VPS and provide host:port summary

set -uo pipefail
# Note: removed -e to allow script to continue even if some checks fail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
export SSH_PRIVATE_KEY="$PROJECT_ROOT/infra/deploy_key"
export INVENTORY_FILE="$PROJECT_ROOT/infra/inventory/hosts.env"

VPS1=191.252.120.36
VPS2=191.252.120.182
VPS3=191.252.120.176

POSTGRES_PASSWORD="_uetYjvZLNd6uAlJQZO1km_Lzl8EmpBeOCuTzpvEgEI"
REDIS_PASSWORD="W3oXTVOmlK3X7UXJ6aslgcwSO2Bh6VPnSfYCH3rmmcI"

echo "🔍 Testing all services on all VPS..."
echo ""

# Function to check port
check_port() {
    local host=$1
    local port=$2
    local service=$3
    local via=${4:-"public"}
    
    if ssh -i "$SSH_PRIVATE_KEY" -o IdentitiesOnly=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@"$host" "timeout 2 bash -c '</dev/tcp/127.0.0.1/$port' 2>/dev/null" 2>/dev/null; then
        echo "  ✅ $service: $host:$port (via $via)"
        return 0
    else
        echo "  ❌ $service: $host:$port (NOT LISTENING)"
        return 1
    fi
}

# Function to check HTTP endpoint
check_http() {
    local host=$1
    local port=$2
    local path=$3
    local service=$4
    
    local response=$(ssh -i "$SSH_PRIVATE_KEY" -o IdentitiesOnly=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@"$host" \
        "curl -sf -m 5 http://127.0.0.1:$port$path 2>/dev/null" 2>/dev/null || echo "")
    
    if [ -n "$response" ]; then
        echo "  ✅ $service: $host:$port$path (HTTP OK)"
        echo "     Response: $response"
        return 0
    else
        echo "  ❌ $service: $host:$port$path (NOT RESPONDING)"
        return 1
    fi
}

# Function to check service status
check_service() {
    local host=$1
    local service=$2
    
    local status=$(ssh -i "$SSH_PRIVATE_KEY" -o IdentitiesOnly=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@"$host" \
        "systemctl is-active $service 2>/dev/null" 2>/dev/null || echo "inactive")
    
    if [ "$status" = "active" ]; then
        echo "  ✅ $service: ACTIVE"
        return 0
    else
        echo "  ❌ $service: $status"
        return 1
    fi
}

# Function to check database connection
check_postgres() {
    local host=$1
    local via=$2
    
    local result=$(ssh -i "$SSH_PRIVATE_KEY" -o IdentitiesOnly=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@"$host" \
        "PGPASSWORD='$POSTGRES_PASSWORD' timeout 5 psql -h $via -p 5432 -U orcazap -d orcazap -c 'SELECT 1;' 2>&1" 2>/dev/null || echo "FAILED")
    
    if echo "$result" | grep -q "1 row"; then
        echo "  ✅ PostgreSQL: $host:5432 (via $via) - CONNECTED"
        return 0
    else
        echo "  ❌ PostgreSQL: $host:5432 (via $via) - FAILED"
        return 1
    fi
}

# Function to check Redis connection
check_redis() {
    local host=$1
    local via=$2
    
    local result=$(ssh -i "$SSH_PRIVATE_KEY" -o IdentitiesOnly=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@"$host" \
        "timeout 5 redis-cli -h $via -p 6379 -a '$REDIS_PASSWORD' ping 2>&1 | grep -v 'Warning:' | tr -d '\n'" 2>/dev/null || echo "FAILED")
    
    if [ "$result" = "PONG" ]; then
        echo "  ✅ Redis: $host:6379 (via $via) - CONNECTED"
        return 0
    else
        echo "  ❌ Redis: $host:6379 (via $via) - FAILED"
        return 1
    fi
}

# ============================================
# VPS1 (APP) - 191.252.120.36
# ============================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 VPS1 (APP): $VPS1"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Systemd services
check_service "$VPS1" "orcazap-app"
check_service "$VPS1" "nginx"
check_service "$VPS1" "pgbouncer"

# Port checks
check_port "$VPS1" "8000" "FastAPI App" "localhost"
check_port "$VPS1" "80" "Nginx HTTP" "public"
check_port "$VPS1" "443" "Nginx HTTPS" "public"
check_port "$VPS1" "6432" "PgBouncer" "localhost"

# HTTP endpoints
check_http "$VPS1" "8000" "/health" "Health Endpoint"

echo ""

# ============================================
# VPS2 (DATA) - 191.252.120.182
# ============================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "💾 VPS2 (DATA): $VPS2"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Systemd services
check_service "$VPS2" "postgresql"
check_service "$VPS2" "redis-server"

# Port checks
check_port "$VPS2" "5432" "PostgreSQL" "localhost"
check_port "$VPS2" "6379" "Redis" "localhost"

# Database connections (from VPS2 itself)
check_postgres "$VPS2" "127.0.0.1"
check_redis "$VPS2" "127.0.0.1"

echo ""

# ============================================
# VPS3 (WORKER) - 191.252.120.176
# ============================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚙️  VPS3 (WORKER): $VPS3"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Systemd services
check_service "$VPS3" "orcazap-worker@1"
check_service "$VPS3" "orcazap-worker@2"

# Check if more workers exist
for i in 3 4; do
    if ssh -i "$SSH_PRIVATE_KEY" -o IdentitiesOnly=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@"$VPS3" \
        "systemctl list-units --type=service | grep -q orcazap-worker@$i" 2>/dev/null; then
        check_service "$VPS3" "orcazap-worker@$i"
    fi
done

echo ""

# ============================================
# Cross-VPS Connectivity Tests
# ============================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔗 Cross-VPS Connectivity (WireGuard)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# VPS1 -> VPS2 (PostgreSQL via WireGuard)
echo "Testing VPS1 -> VPS2 PostgreSQL (10.10.0.2:5432)..."
if ssh -i "$SSH_PRIVATE_KEY" -o IdentitiesOnly=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@"$VPS1" \
    "PGPASSWORD='$POSTGRES_PASSWORD' timeout 5 psql -h 10.10.0.2 -p 5432 -U orcazap -d orcazap -c 'SELECT 1;' 2>&1" 2>/dev/null | grep -q "1 row"; then
    echo "  ✅ VPS1 -> VPS2 PostgreSQL: CONNECTED"
else
    echo "  ❌ VPS1 -> VPS2 PostgreSQL: FAILED"
fi

# VPS1 -> VPS2 (Redis via WireGuard)
echo "Testing VPS1 -> VPS2 Redis (10.10.0.2:6379)..."
if ssh -i "$SSH_PRIVATE_KEY" -o IdentitiesOnly=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@"$VPS1" \
    "timeout 5 redis-cli -h 10.10.0.2 -p 6379 -a '$REDIS_PASSWORD' ping 2>&1 | grep -v 'Warning:' | grep -q 'PONG'" 2>/dev/null; then
    echo "  ✅ VPS1 -> VPS2 Redis: CONNECTED"
else
    echo "  ❌ VPS1 -> VPS2 Redis: FAILED"
fi

# VPS3 -> VPS2 (PostgreSQL via WireGuard)
echo "Testing VPS3 -> VPS2 PostgreSQL (10.10.0.2:5432)..."
if ssh -i "$SSH_PRIVATE_KEY" -o IdentitiesOnly=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@"$VPS3" \
    "PGPASSWORD='$POSTGRES_PASSWORD' timeout 5 psql -h 10.10.0.2 -p 5432 -U orcazap -d orcazap -c 'SELECT 1;' 2>&1" 2>/dev/null | grep -q "1 row"; then
    echo "  ✅ VPS3 -> VPS2 PostgreSQL: CONNECTED"
else
    echo "  ❌ VPS3 -> VPS2 PostgreSQL: FAILED"
fi

# VPS3 -> VPS2 (Redis via WireGuard)
echo "Testing VPS3 -> VPS2 Redis (10.10.0.2:6379)..."
if ssh -i "$SSH_PRIVATE_KEY" -o IdentitiesOnly=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@"$VPS3" \
    "timeout 5 redis-cli -h 10.10.0.2 -p 6379 -a '$REDIS_PASSWORD' ping 2>&1 | grep -v 'Warning:' | grep -q 'PONG'" 2>/dev/null; then
    echo "  ✅ VPS3 -> VPS2 Redis: CONNECTED"
else
    echo "  ❌ VPS3 -> VPS2 Redis: FAILED"
fi

echo ""

# ============================================
# Summary
# ============================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 SERVICE SUMMARY - Host:Port"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "VPS1 (APP) - $VPS1:"
echo "  • FastAPI App:     $VPS1:8000 (internal) / http://$VPS1:8000/health"
echo "  • Nginx HTTP:      $VPS1:80"
echo "  • Nginx HTTPS:     $VPS1:443"
echo "  • PgBouncer:       $VPS1:6432 (internal)"
echo ""
echo "VPS2 (DATA) - $VPS2:"
echo "  • PostgreSQL:      $VPS2:5432 (10.10.0.2:5432 via WireGuard)"
echo "  • Redis:           $VPS2:6379 (10.10.0.2:6379 via WireGuard)"
echo ""
echo "VPS3 (WORKER) - $VPS3:"
echo "  • RQ Workers:      systemd services (no HTTP port)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

