# Deployment Guide

OrcaZap supports two deployment modes: single-node (simplest, cheapest) and multi-node (scalable, production-ready).

## Mode A: Single-Node Deployment

**Best for:** MVP, development, small-scale production

**Topology:**
- Single VPS instance (2GB RAM, 2 vCPU minimum)
- PostgreSQL + Redis on same server
- FastAPI + RQ workers on same server
- Nginx reverse proxy (optional but recommended)

### Prerequisites

- Ubuntu 22.04 LTS (or similar)
- Root or sudo access
- Domain name with DNS configured (optional for local dev)

### Setup Steps

1. **Create application user:**
```bash
sudo adduser --system --group --home /opt/orcazap orcazap
```

2. **Install dependencies:**
```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv postgresql-15 redis-server nginx
```

3. **Set up PostgreSQL:**
```bash
sudo -u postgres createdb orcazap
sudo -u postgres createuser orcazap
sudo -u postgres psql -c "ALTER USER orcazap WITH PASSWORD 'your-secure-password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE orcazap TO orcazap;"
```

4. **Set up Redis:**
```bash
# Edit /etc/redis/redis.conf
sudo nano /etc/redis/redis.conf
# Set: requirepass your-redis-password
# Set: bind 127.0.0.1

sudo systemctl restart redis
```

5. **Deploy application:**
```bash
sudo -u orcazap git clone <repo-url> /opt/orcazap
cd /opt/orcazap
sudo -u orcazap python3.12 -m venv venv
sudo -u orcazap venv/bin/pip install -r requirements.txt
```

6. **Configure environment:**
```bash
sudo -u orcazap cp env.example .env
sudo -u orcazap nano .env
# Set: DATABASE_URL, REDIS_URL, SECRET_KEY, etc.
```

7. **Run migrations:**
```bash
sudo -u orcazap venv/bin/alembic upgrade head
```

8. **Create systemd services:**

**`/etc/systemd/system/orcazap.service`:**
```ini
[Unit]
Description=OrcaZap FastAPI Application
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=orcazap
Group=orcazap
WorkingDirectory=/opt/orcazap
Environment="PATH=/opt/orcazap/venv/bin"
ExecStart=/opt/orcazap/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/orcazap-worker.service`:**
```ini
[Unit]
Description=OrcaZap RQ Worker
After=network.target redis.service

[Service]
Type=simple
User=orcazap
Group=orcazap
WorkingDirectory=/opt/orcazap
Environment="PATH=/opt/orcazap/venv/bin"
ExecStart=/opt/orcazap/venv/bin/rq worker --url redis://localhost:6379/0 default
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

9. **Start services:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable orcazap orcazap-worker
sudo systemctl start orcazap orcazap-worker
```

10. **Configure Nginx (optional):**
```nginx
# /etc/nginx/sites-available/orcazap
server {
    listen 80;
    server_name orcazap.com www.orcazap.com api.orcazap.com *.orcazap.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/orcazap /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

11. **Set up SSL (Let's Encrypt):**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d orcazap.com -d www.orcazap.com -d api.orcazap.com -d "*.orcazap.com"
```

12. **Health check:**
```bash
curl http://localhost:8000/health -H "Host: api.orcazap.com"
```

### Optional: PgBouncer

For better connection management, install PgBouncer:

```bash
sudo apt install pgbouncer
# Configure /etc/pgbouncer/pgbouncer.ini
# Update DATABASE_URL to use pgbouncer port (6432)
```

## Mode B: Multi-Node Deployment

**Best for:** Production, high availability, scaling

**Topology:**
- **APP node**: Nginx, FastAPI, PgBouncer
- **DATA node**: PostgreSQL, Redis
- **WORKER node**: RQ workers
- **Network**: WireGuard VPN (10.10.0.0/24) or private VPC

### Network Setup

**WireGuard VPN (recommended for VPS without private networking):**

1. **Install WireGuard on all nodes:**
```bash
sudo apt install wireguard
```

2. **Generate keys:**
```bash
wg genkey | tee privatekey | wg pubkey > publickey
```

3. **Configure WireGuard on each node:**
```ini
# /etc/wireguard/wg0.conf
[Interface]
PrivateKey = <node_private_key>
Address = 10.10.0.X/24
ListenPort = 51820

[Peer]
PublicKey = <peer_public_key>
Endpoint = <peer_public_ip>:51820
AllowedIPs = 10.10.0.Y/32
```

4. **Start WireGuard:**
```bash
sudo wg-quick up wg0
sudo systemctl enable wg-quick@wg0
```

### APP Node Setup

1. **Install dependencies:**
```bash
sudo apt install -y python3.12 python3.12-venv nginx pgbouncer
```

2. **Deploy application:**
```bash
sudo -u orcazap git clone <repo-url> /opt/orcazap
cd /opt/orcazap
sudo -u orcazap python3.12 -m venv venv
sudo -u orcazap venv/bin/pip install -r requirements.txt
```

3. **Configure environment:**
```bash
# .env
DATABASE_URL=postgresql://orcazap:password@10.10.0.2:5432/orcazap
REDIS_URL=redis://:password@10.10.0.2:6379/0
# ... other vars
```

4. **Configure PgBouncer:**
```ini
# /etc/pgbouncer/pgbouncer.ini
[databases]
orcazap = host=10.10.0.2 port=5432 dbname=orcazap

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
pool_mode = transaction
max_client_conn = 100
default_pool_size = 20
```

5. **Create systemd service** (same as single-node, but use PgBouncer URL)

6. **Configure Nginx** (same as single-node)

### DATA Node Setup

1. **Install PostgreSQL and Redis:**
```bash
sudo apt install -y postgresql-15 redis-server
```

2. **Configure PostgreSQL:**
```conf
# /etc/postgresql/15/main/postgresql.conf
listen_addresses = '10.10.0.2'  # WireGuard IP
port = 5432
max_connections = 100
```

```conf
# /etc/postgresql/15/main/pg_hba.conf
host    all    all    10.10.0.1/32    md5  # APP node
host    all    all    10.10.0.3/32    md5  # WORKER node
```

3. **Configure Redis:**
```conf
# /etc/redis/redis.conf
bind 10.10.0.2  # WireGuard IP
port 6379
requirepass your-redis-password
protected-mode yes
```

4. **Set up database:**
```bash
sudo -u postgres createdb orcazap
sudo -u postgres createuser orcazap
sudo -u postgres psql -c "ALTER USER orcazap WITH PASSWORD 'password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE orcazap TO orcazap;"
```

### WORKER Node Setup

1. **Install dependencies:**
```bash
sudo apt install -y python3.12 python3.12-venv
```

2. **Deploy application:**
```bash
sudo -u orcazap git clone <repo-url> /opt/orcazap
cd /opt/orcazap
sudo -u orcazap python3.12 -m venv venv
sudo -u orcazap venv/bin/pip install -r requirements.txt
```

3. **Configure environment:**
```bash
# .env (same as APP node)
DATABASE_URL=postgresql://orcazap:password@10.10.0.2:5432/orcazap
REDIS_URL=redis://:password@10.10.0.2:6379/0
```

4. **Create systemd service** (same as single-node worker)

5. **Run multiple workers (optional):**
```bash
# Enable 4 workers
sudo systemctl enable orcazap-worker@1
sudo systemctl enable orcazap-worker@2
sudo systemctl enable orcazap-worker@3
sudo systemctl enable orcazap-worker@4
```

### Firewall Rules

**APP node:**
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 51820/udp  # WireGuard
sudo ufw enable
```

**DATA node:**
```bash
sudo ufw allow 22/tcp
sudo ufw allow 51820/udp  # WireGuard
sudo ufw allow from 10.10.0.1 to any port 5432  # PostgreSQL
sudo ufw allow from 10.10.0.1 to any port 6379  # Redis
sudo ufw allow from 10.10.0.3 to any port 5432  # PostgreSQL
sudo ufw allow from 10.10.0.3 to any port 6379  # Redis
sudo ufw enable
```

**WORKER node:**
```bash
sudo ufw allow 22/tcp
sudo ufw allow 51820/udp  # WireGuard
sudo ufw enable
```

## Environment Variables Reference

See [.env.example](../env.example) for complete variable reference.

**Required:**
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `SECRET_KEY`: Application secret key (generate with `openssl rand -hex 32`)
- `WHATSAPP_VERIFY_TOKEN`: Webhook verification token
- `WHATSAPP_ACCESS_TOKEN`: WhatsApp Cloud API access token
- `WHATSAPP_PHONE_NUMBER_ID`: WhatsApp phone number ID
- `WHATSAPP_BUSINESS_ACCOUNT_ID`: WhatsApp Business Account ID

**Optional:**
- `DEBUG`: Enable debug mode (default: false)
- `ENVIRONMENT`: Environment name (development, staging, production)
- `BCRYPT_ROUNDS`: Password hashing rounds (default: 12)
- `ADMIN_SESSION_SECRET`: Session secret (default: same as SECRET_KEY)
- `OPENAI_API_KEY`: OpenAI API key (for LLM parsing)
- `ANTHROPIC_API_KEY`: Anthropic API key (for LLM parsing)

## Operational Checklist

### Pre-Deployment
- [ ] Database migrations tested locally
- [ ] Environment variables configured
- [ ] SSL certificates obtained (Let's Encrypt)
- [ ] DNS records configured (A records, CNAME)
- [ ] Firewall rules configured
- [ ] Backup strategy defined

### Deployment
- [ ] Application code deployed
- [ ] Dependencies installed
- [ ] Database migrations run (`alembic upgrade head`)
- [ ] Systemd services created and enabled
- [ ] Services started and healthy
- [ ] Nginx configured and reloaded
- [ ] SSL certificates installed
- [ ] Health checks passing

### Post-Deployment
- [ ] Webhook endpoint verified (WhatsApp)
- [ ] Test message sent and received
- [ ] Admin panel accessible
- [ ] Worker processing jobs
- [ ] Logs monitored for errors
- [ ] Backups running

## Rollback Strategy

1. **Stop services:**
```bash
sudo systemctl stop orcazap orcazap-worker
```

2. **Revert code:**
```bash
cd /opt/orcazap
sudo -u orcazap git checkout <previous-commit>
sudo -u orcazap venv/bin/pip install -r requirements.txt
```

3. **Rollback database (if needed):**
```bash
sudo -u orcazap venv/bin/alembic downgrade -1
```

4. **Restart services:**
```bash
sudo systemctl start orcazap orcazap-worker
```

## Data Migrations Process

1. **Test migration locally:**
```bash
alembic upgrade head
alembic downgrade -1
```

2. **Backup database:**
```bash
pg_dump -h <host> -U orcazap orcazap > backup-$(date +%Y%m%d).sql
```

3. **Run migration on production:**
```bash
sudo -u orcazap venv/bin/alembic upgrade head
```

4. **Verify migration:**
```bash
# Check migration version
sudo -u orcazap venv/bin/alembic current
# Check application health
curl http://localhost:8000/health
```

5. **Monitor logs:**
```bash
sudo journalctl -u orcazap -f
```

## Monitoring

**Health endpoints:**
- `GET /health`: Basic health check
- `GET /monitoring/ready`: Readiness check (database, Redis)
- `GET /monitoring/metrics`: Prometheus metrics

**Service status:**
```bash
sudo systemctl status orcazap
sudo systemctl status orcazap-worker
```

**Logs:**
```bash
sudo journalctl -u orcazap -f
sudo journalctl -u orcazap-worker -f
```

**Queue depth:**
```bash
redis-cli -h <redis-host> -a <password> LLEN rq:queue:default
```

## Backups

### Database Backups

**Daily backup script:**
```bash
#!/bin/bash
# /opt/orcazap/scripts/backup-db.sh
BACKUP_DIR=/backup/orcazap
DATE=$(date +%Y%m%d)
pg_dump -h <host> -U orcazap orcazap | gzip > $BACKUP_DIR/orcazap-$DATE.sql.gz
# Keep last 7 days
find $BACKUP_DIR -name "orcazap-*.sql.gz" -mtime +7 -delete
```

**Cron job:**
```bash
# /etc/cron.daily/orcazap-backup
0 2 * * * /opt/orcazap/scripts/backup-db.sh
```

### Redis Backups

Redis persistence via RDB snapshots (configured in redis.conf):
```conf
save 900 1
save 300 10
save 60 10000
```

## Troubleshooting

**Service won't start:**
- Check logs: `sudo journalctl -u orcazap -n 50`
- Check environment variables: `sudo -u orcazap cat .env`
- Check database connectivity: `psql $DATABASE_URL -c "SELECT 1"`

**Worker not processing jobs:**
- Check Redis connectivity: `redis-cli -h <host> -a <password> ping`
- Check queue depth: `redis-cli LLEN rq:queue:default`
- Check worker logs: `sudo journalctl -u orcazap-worker -f`

**Database connection errors:**
- Check PgBouncer (if used): `psql -h 127.0.0.1 -p 6432 -U orcazap -d orcazap`
- Check PostgreSQL logs: `sudo journalctl -u postgresql -f`
- Check firewall rules: `sudo ufw status`

**Nginx errors:**
- Check config: `sudo nginx -t`
- Check logs: `sudo tail -f /var/log/nginx/error.log`
- Check SSL: `sudo certbot certificates`




