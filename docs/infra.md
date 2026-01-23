# Infrastructure Setup

## Overview

OrcaZap runs on 3 VPS instances (1GB RAM, 2 vCPU each) with no private VPC. We use **WireGuard** to create a private network and **systemd** for service management (no Docker).

## Network Setup

### WireGuard Configuration

**Network:** `10.10.0.0/24`

**VPS1 (APP):** `10.10.0.1`
**VPS2 (DATA):** `10.10.0.2`
**VPS3 (WORKERS):** `10.10.0.3`

### WireGuard Config Template

**VPS1 (`/etc/wireguard/wg0.conf`):**
```ini
[Interface]
PrivateKey = <vps1_private_key>
Address = 10.10.0.1/24
ListenPort = 51820

[Peer]
PublicKey = <vps2_public_key>
Endpoint = <vps2_public_ip>:51820
AllowedIPs = 10.10.0.2/32

[Peer]
PublicKey = <vps3_public_key>
Endpoint = <vps3_public_ip>:51820
AllowedIPs = 10.10.0.3/32
```

**VPS2 (`/etc/wireguard/wg0.conf`):**
```ini
[Interface]
PrivateKey = <vps2_private_key>
Address = 10.10.0.2/24
ListenPort = 51820

[Peer]
PublicKey = <vps1_public_key>
Endpoint = <vps1_public_ip>:51820
AllowedIPs = 10.10.0.1/32

[Peer]
PublicKey = <vps3_public_key>
Endpoint = <vps3_public_ip>:51820
AllowedIPs = 10.10.0.3/32
```

**VPS3 (`/etc/wireguard/wg0.conf`):**
```ini
[Interface]
PrivateKey = <vps3_private_key>
Address = 10.10.0.3/24
ListenPort = 51820

[Peer]
PublicKey = <vps1_public_key>
Endpoint = <vps1_public_ip>:51820
AllowedIPs = 10.10.0.1/32

[Peer]
PublicKey = <vps2_public_key>
Endpoint = <vps2_public_ip>:51820
AllowedIPs = 10.10.0.2/32
```

**Setup Commands:**
```bash
# Generate keys
wg genkey | tee privatekey | wg pubkey > publickey

# Enable WireGuard
wg-quick up wg0
systemctl enable wg-quick@wg0
```

## Firewall Rules (ufw)

### VPS1 (APP)
```bash
ufw allow 22/tcp          # SSH
ufw allow 80/tcp          # HTTP
ufw allow 443/tcp         # HTTPS
ufw allow 51820/udp       # WireGuard
ufw allow from 10.10.0.0/24 to any port 5432  # Postgres (via PgBouncer)
ufw enable
```

### VPS2 (DATA)
```bash
ufw allow 22/tcp          # SSH
ufw allow 51820/udp       # WireGuard
ufw allow from 10.10.0.1 to any port 5432  # Postgres (from VPS1)
ufw allow from 10.10.0.1 to any port 6379  # Redis (from VPS1)
ufw allow from 10.10.0.3 to any port 5432  # Postgres (from VPS3)
ufw allow from 10.10.0.3 to any port 6379  # Redis (from VPS3)
ufw enable
```

### VPS3 (WORKERS)
```bash
ufw allow 22/tcp          # SSH
ufw allow 51820/udp       # WireGuard
ufw allow from 10.10.0.0/24 to any port 5432  # Postgres
ufw allow from 10.10.0.0/24 to any port 6379  # Redis
ufw enable
```

## VPS1: Application Server

### Services
- **Nginx**: Reverse proxy, static files, SSL termination
- **FastAPI (Uvicorn)**: Application server
- **PgBouncer** (optional): Connection pooling to Postgres

### Nginx Config (`/etc/nginx/sites-available/orcazap`)
```nginx
server {
    listen 80;
    server_name orcazap.example.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static {
        alias /var/www/orcazap/static;
    }
}
```

### Systemd Unit: FastAPI (`/etc/systemd/system/orcazap.service`)
```ini
[Unit]
Description=OrcaZap FastAPI Application
After=network.target

[Service]
Type=simple
User=orcazap
WorkingDirectory=/opt/orcazap
Environment="PATH=/opt/orcazap/venv/bin"
ExecStart=/opt/orcazap/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### PgBouncer Config (`/etc/pgBouncer/pgbouncer.ini`)
```ini
[databases]
orcazap = host=10.10.0.2 port=5432 dbname=orcazap

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432
auth_type = md5
auth_file = /etc/pgBouncer/userlist.txt
pool_mode = transaction
max_client_conn = 100
default_pool_size = 20
```

## VPS2: Data Server

### Services
- **PostgreSQL**: Database (bind to `wg0` interface)
- **Redis**: Queue and cache (bind to `wg0` interface)

### PostgreSQL Config (`/etc/postgresql/15/main/postgresql.conf`)
```conf
listen_addresses = '10.10.0.2'
port = 5432
max_connections = 100
shared_buffers = 256MB
```

### PostgreSQL Host-Based Auth (`/etc/postgresql/15/main/pg_hba.conf`)
```
host    all    all    10.10.0.1/32    md5
host    all    all    10.10.0.3/32    md5
```

### Redis Config (`/etc/redis/redis.conf`)
```conf
bind 10.10.0.2
port 6379
protected-mode yes
requirepass <redis_password>
```

## VPS3: Worker Server

### Services
- **RQ Workers**: Background job processing

### Systemd Unit: RQ Worker (`/etc/systemd/system/orcazap-worker.service`)
```ini
[Unit]
Description=OrcaZap RQ Worker
After=network.target redis.service

[Service]
Type=simple
User=orcazap
WorkingDirectory=/opt/orcazap
Environment="PATH=/opt/orcazap/venv/bin"
ExecStart=/opt/orcazap/venv/bin/rq worker --url redis://10.10.0.2:6379/0 default
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Multiple Workers
Run multiple worker processes:
```bash
# /etc/systemd/system/orcazap-worker@.service
[Unit]
Description=OrcaZap RQ Worker %i
After=network.target redis.service

[Service]
Type=simple
User=orcazap
WorkingDirectory=/opt/orcazap
Environment="PATH=/opt/orcazap/venv/bin"
ExecStart=/opt/orcazap/venv/bin/rq worker --url redis://10.10.0.2:6379/0 default
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable 4 workers:
```bash
systemctl enable orcazap-worker@1
systemctl enable orcazap-worker@2
systemctl enable orcazap-worker@3
systemctl enable orcazap-worker@4
```

## Backups

### PostgreSQL Backups
```bash
# /etc/cron.daily/postgres-backup
#!/bin/bash
pg_dump -h 10.10.0.2 -U orcazap orcazap | gzip > /backup/orcazap-$(date +%Y%m%d).sql.gz
# Keep last 7 days
find /backup -name "orcazap-*.sql.gz" -mtime +7 -delete
```

### Redis Backups (Optional)
Redis persistence via RDB snapshots (configured in redis.conf).

## Validation Checklist

- [ ] WireGuard peers can ping each other
- [ ] PostgreSQL accessible from VPS1 and VPS3
- [ ] Redis accessible from VPS1 and VPS3
- [ ] Nginx serves application
- [ ] FastAPI service starts and responds
- [ ] RQ workers connect to Redis and process jobs
- [ ] Firewall rules allow only necessary traffic
- [ ] Backups run daily
- [ ] SSL certificates configured (Let's Encrypt)
- [ ] Logs rotate (logrotate)

## Monitoring (Future)

- Health check endpoint: `GET /health`
- Database connection pool monitoring
- Redis queue depth monitoring
- Worker process monitoring (systemd status)


