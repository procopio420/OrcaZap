# OrcaZap Production Deployment Guide

## Pre-Deployment Checklist

### ✅ Code Status
- [x] All code implemented
- [x] Unit tests passing (9/9)
- [x] Application loads successfully
- [x] HTTP server responds correctly
- [x] Host routing working
- [x] All dependencies installed

### ⏳ Infrastructure Setup Required

## Step 1: Database Setup

```bash
# Install PostgreSQL (if not installed)
sudo apt update
sudo apt install postgresql postgresql-contrib

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql <<EOF
CREATE DATABASE orcazap;
CREATE USER orcazap WITH PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE orcazap TO orcazap;
\q
EOF

# Update .env with database URL
# DATABASE_URL=postgresql://orcazap:your-secure-password@localhost:5432/orcazap
```

## Step 2: Redis Setup

```bash
# Install Redis (if not installed)
sudo apt install redis-server

# Start Redis
sudo systemctl start redis
sudo systemctl enable redis

# Verify Redis is running
redis-cli ping
# Should return: PONG
```

## Step 3: Run Database Migrations

```bash
cd /home/lucas/hobby/orcazap
source venv/bin/activate

# Check current migration status
alembic current

# Run all migrations
alembic upgrade head

# Verify tables created
psql -U orcazap -d orcazap -c "\dt"
```

## Step 4: Configure Environment Variables

Edit `.env` file with production values:

```bash
# Database (from Step 1)
DATABASE_URL=postgresql://orcazap:your-password@localhost:5432/orcazap

# Redis (default should work)
REDIS_URL=redis://localhost:6379/0

# Application (generate secure key)
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
# Add to .env: SECRET_KEY=<generated-value>

# Environment
DEBUG=false
ENVIRONMENT=production

# WhatsApp (get from Meta for Developers)
WHATSAPP_VERIFY_TOKEN=your-verify-token
WHATSAPP_ACCESS_TOKEN=your-access-token
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id
WHATSAPP_BUSINESS_ACCOUNT_ID=your-waba-id

# Operator Admin
OPERATOR_USERNAME=admin
OPERATOR_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
# Add to .env: OPERATOR_PASSWORD=<generated-value>

# Stripe (get from Stripe Dashboard)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...
```

## Step 5: Test Application Locally

```bash
cd /home/lucas/hobby/orcazap
source venv/bin/activate

# Start server
uvicorn app.main:app --host 127.0.0.1 --port 8000

# In another terminal, test endpoints:
curl http://127.0.0.1:8000/health -H "Host: api.orcazap.com"
curl http://127.0.0.1:8000/ -H "Host: orcazap.com"
```

## Step 6: Deploy Systemd Service

```bash
# Copy systemd service template
sudo cp infra/templates/systemd/orcazap-app.service.tmpl /etc/systemd/system/orcazap-app.service

# Edit service file with correct paths
sudo nano /etc/systemd/system/orcazap-app.service
# Update: APP_DIR, APP_USER, APP_ENV_FILE

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable orcazap-app
sudo systemctl start orcazap-app

# Check status
sudo systemctl status orcazap-app
```

## Step 7: Configure Nginx

```bash
# Copy Nginx config template
sudo cp infra/templates/nginx/orcazap.nginx.conf.tmpl /etc/nginx/sites-available/orcazap

# Edit if needed (update paths, etc.)
sudo nano /etc/nginx/sites-available/orcazap

# Enable site
sudo ln -s /etc/nginx/sites-available/orcazap /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

## Step 8: Setup TLS Certificate

Follow the guide in `docs/infra_domains_tls.md`:

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Request wildcard certificate (DNS-01 challenge)
certbot certonly \
  --manual \
  --preferred-challenges dns \
  -d "*.orcazap.com" \
  -d "orcazap.com" \
  -d "www.orcazap.com" \
  -d "api.orcazap.com" \
  --email your-email@example.com \
  --agree-tos

# Follow prompts to add DNS TXT record
# Certificates will be at: /etc/letsencrypt/live/orcazap.com/

# Update Nginx config to use certificates
# (Already configured in template)

# Test auto-renewal
sudo certbot renew --dry-run
```

## Step 9: Configure DNS

Set up DNS records pointing to your server IP:

1. **A Record**: `orcazap.com` → `<YOUR_SERVER_IP>`
2. **CNAME**: `www.orcazap.com` → `orcazap.com`
3. **A Record**: `api.orcazap.com` → `<YOUR_SERVER_IP>`
4. **A Record**: `*.orcazap.com` → `<YOUR_SERVER_IP>`

Wait for DNS propagation (can take up to 48 hours, usually much faster).

## Step 10: Verify Deployment

```bash
# Test all endpoints
curl https://orcazap.com/ -k  # Should show landing page
curl https://api.orcazap.com/health -k  # Should return {"status":"ok","service":"orcazap"}
curl https://test.orcazap.com/ -k  # Should show 404 (no tenant yet)

# Check logs
sudo journalctl -u orcazap-app -f
sudo tail -f /var/log/nginx/orcazap-*-error.log
```

## Step 11: Run Integration Tests

```bash
cd /home/lucas/hobby/orcazap
source venv/bin/activate

# Run all tests
pytest tests/ -v

# Should see:
# - Unit tests: 9 passed
# - Integration tests: (require database)
```

## Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection
psql -U orcazap -d orcazap -c "SELECT 1;"
```

### Redis Connection Issues
```bash
# Check Redis is running
sudo systemctl status redis
redis-cli ping
```

### Application Not Starting
```bash
# Check systemd logs
sudo journalctl -u orcazap-app -n 50

# Check for Python errors
cd /home/lucas/hobby/orcazap
source venv/bin/activate
python -c "from app.main import app"
```

### Nginx Issues
```bash
# Test configuration
sudo nginx -t

# Check error logs
sudo tail -f /var/log/nginx/error.log
```

## Security Checklist

- [ ] `SECRET_KEY` is strong and unique
- [ ] `OPERATOR_PASSWORD` is strong
- [ ] Database password is strong
- [ ] `.env` file has correct permissions (600)
- [ ] TLS certificates are valid
- [ ] Nginx is configured with security headers
- [ ] Firewall rules are configured
- [ ] Regular backups are set up

## Monitoring

Set up monitoring for:
- Application health: `https://api.orcazap.com/health`
- Systemd service status
- Nginx access/error logs
- Database connection pool
- Redis connection
- Disk space
- Certificate expiration (auto-renewal should handle this)

## Backup Strategy

1. **Database Backups**:
   ```bash
   # Daily backup script
   pg_dump -U orcazap orcazap > backup_$(date +%Y%m%d).sql
   ```

2. **Configuration Backups**:
   - Backup `.env` file (securely)
   - Backup Nginx configs
   - Backup systemd service files

3. **Certificate Backups**:
   - `/etc/letsencrypt/` is automatically backed up by Certbot

## Post-Deployment

1. Create first tenant via registration
2. Test onboarding flow
3. Test tenant dashboard
4. Test operator admin
5. Configure WhatsApp webhook
6. Test Stripe checkout (use test mode first)

## Support

For issues, check:
- Application logs: `sudo journalctl -u orcazap-app`
- Nginx logs: `/var/log/nginx/`
- Database logs: `/var/log/postgresql/`
- System logs: `sudo journalctl -xe`








