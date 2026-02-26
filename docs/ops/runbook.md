# OrcaZap Runbook

**⚠️ PRIVATE TEMPLATE - DO NOT COMMIT REAL VALUES**

This is a template runbook for operational procedures. Fill in real values for your environment and keep this file private (add to `.gitignore` or use a private repository).

## Service Health Checks

### Application Health

```bash
# Check API health
curl https://api.orcazap.com/health

# Check readiness (database, Redis)
curl https://api.orcazap.com/monitoring/ready

# Check metrics
curl https://api.orcazap.com/monitoring/metrics
```

### Service Status

```bash
# Check systemd services
sudo systemctl status orcazap
sudo systemctl status orcazap-worker

# Check service logs
sudo journalctl -u orcazap -n 50
sudo journalctl -u orcazap-worker -n 50
```

### Database Health

```bash
# Connect to database
psql $DATABASE_URL -c "SELECT version();"

# Check connection pool (if using PgBouncer)
psql -h 127.0.0.1 -p 6432 -U orcazap -d orcazap -c "SHOW POOLS;"

# Check active connections
psql $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"
```

### Redis Health

```bash
# Ping Redis
redis-cli -h <REDIS_HOST> -a <REDIS_PASSWORD> ping

# Check queue depth
redis-cli -h <REDIS_HOST> -a <REDIS_PASSWORD> LLEN rq:queue:default

# Check failed jobs
redis-cli -h <REDIS_HOST> -a <REDIS_PASSWORD> LLEN rq:queue:failed
```

## Queue Diagnostics

### Check Queue Depth

```bash
# Default queue
redis-cli -h <REDIS_HOST> -a <REDIS_PASSWORD> LLEN rq:queue:default

# Failed queue
redis-cli -h <REDIS_HOST> -a <REDIS_PASSWORD> LLEN rq:queue:failed
```

### View Stuck Jobs

```bash
# List jobs in queue
redis-cli -h <REDIS_HOST> -a <REDIS_PASSWORD> LRANGE rq:queue:default 0 10

# Check worker status
sudo systemctl status orcazap-worker
```

### Retry Failed Jobs

```bash
# Connect to RQ dashboard or use RQ CLI
rq info --url redis://:<REDIS_PASSWORD>@<REDIS_HOST>:6379/0

# Retry specific job (requires RQ CLI)
rq retry <job_id> --url redis://:<REDIS_PASSWORD>@<REDIS_HOST>:6379/0
```

## WhatsApp Webhook Issues

### Verify Webhook Configuration

```bash
# Test webhook verification
curl "https://api.orcazap.com/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=<VERIFY_TOKEN>&hub.challenge=test"

# Check webhook logs
sudo journalctl -u orcazap -g "webhook" -n 50
```

### Test Webhook Endpoint

```bash
# Send test webhook (replace with real payload)
curl -X POST https://api.orcazap.com/webhooks/whatsapp \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/whatsapp/webhook_text_message.json
```

### Check Message Processing

```bash
# Query recent messages
psql $DATABASE_URL -c "SELECT id, provider_message_id, direction, created_at FROM messages ORDER BY created_at DESC LIMIT 10;"

# Check for unprocessed messages
psql $DATABASE_URL -c "SELECT COUNT(*) FROM messages WHERE conversation_id IS NULL;"
```

## Database Slow Queries

### Identify Slow Queries

```sql
-- Enable slow query logging (if not enabled)
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries > 1s
SELECT pg_reload_conf();

-- View slow queries
SELECT query, calls, total_time, mean_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

### Check Indexes

```sql
-- Find missing indexes
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats
WHERE schemaname = 'public'
AND n_distinct > 100
AND correlation < 0.1;
```

### Analyze Tables

```bash
# Run ANALYZE on all tables
psql $DATABASE_URL -c "ANALYZE;"

# Vacuum if needed
psql $DATABASE_URL -c "VACUUM ANALYZE;"
```

## Backup and Restore

### Database Backup

```bash
# Full backup
pg_dump -h <DB_HOST> -U orcazap orcazap | gzip > backup-$(date +%Y%m%d).sql.gz

# Backup specific tables
pg_dump -h <DB_HOST> -U orcazap -t tenants -t users orcazap > tenants-backup.sql
```

### Database Restore

```bash
# Restore from backup
gunzip < backup-20240101.sql.gz | psql -h <DB_HOST> -U orcazap orcazap

# Restore specific tables
psql -h <DB_HOST> -U orcazap orcazap < tenants-backup.sql
```

### Redis Backup

```bash
# Redis RDB backup (if configured)
redis-cli -h <REDIS_HOST> -a <REDIS_PASSWORD> BGSAVE

# Copy RDB file
cp /var/lib/redis/dump.rdb /backup/redis-$(date +%Y%m%d).rdb
```

## Incident Response

### Service Down

1. **Check service status:**
```bash
sudo systemctl status orcazap
sudo systemctl status orcazap-worker
```

2. **Check logs:**
```bash
sudo journalctl -u orcazap -n 100
sudo journalctl -u orcazap-worker -n 100
```

3. **Restart services:**
```bash
sudo systemctl restart orcazap
sudo systemctl restart orcazap-worker
```

4. **Verify health:**
```bash
curl http://localhost:8000/health
```

### Database Connection Issues

1. **Check database status:**
```bash
sudo systemctl status postgresql
```

2. **Test connection:**
```bash
psql $DATABASE_URL -c "SELECT 1;"
```

3. **Check PgBouncer (if used):**
```bash
psql -h 127.0.0.1 -p 6432 -U orcazap -d orcazap -c "SELECT 1;"
```

4. **Check firewall:**
```bash
sudo ufw status
```

### Redis Connection Issues

1. **Check Redis status:**
```bash
sudo systemctl status redis
```

2. **Test connection:**
```bash
redis-cli -h <REDIS_HOST> -a <REDIS_PASSWORD> ping
```

3. **Check firewall:**
```bash
sudo ufw status
```

### High Queue Depth

1. **Check queue depth:**
```bash
redis-cli -h <REDIS_HOST> -a <REDIS_PASSWORD> LLEN rq:queue:default
```

2. **Scale workers:**
```bash
# Enable additional workers
sudo systemctl enable orcazap-worker@2
sudo systemctl start orcazap-worker@2
```

3. **Check for stuck jobs:**
```bash
# View job details
redis-cli -h <REDIS_HOST> -a <REDIS_PASSWORD> LRANGE rq:queue:default 0 5
```

## Common Commands

### Application

```bash
# View logs
sudo journalctl -u orcazap -f

# Restart service
sudo systemctl restart orcazap

# Check service status
sudo systemctl status orcazap
```

### Worker

```bash
# View worker logs
sudo journalctl -u orcazap-worker -f

# Restart worker
sudo systemctl restart orcazap-worker

# Check worker status
sudo systemctl status orcazap-worker
```

### Database

```bash
# Connect to database
psql $DATABASE_URL

# Run migration
cd /opt/orcazap
sudo -u orcazap venv/bin/alembic upgrade head

# Check migration status
sudo -u orcazap venv/bin/alembic current
```

### Redis

```bash
# Connect to Redis
redis-cli -h <REDIS_HOST> -a <REDIS_PASSWORD>

# Monitor commands
redis-cli -h <REDIS_HOST> -a <REDIS_PASSWORD> MONITOR

# Flush queue (⚠️ use with caution)
redis-cli -h <REDIS_HOST> -a <REDIS_PASSWORD> DEL rq:queue:default
```

## Monitoring

### Prometheus Metrics

```bash
# Scrape metrics endpoint
curl https://api.orcazap.com/monitoring/metrics
```

### Log Aggregation

```bash
# Follow application logs
sudo journalctl -u orcazap -f

# Follow worker logs
sudo journalctl -u orcazap-worker -f

# Search logs
sudo journalctl -u orcazap -g "error" -n 50
```

## Maintenance Windows

### Scheduled Maintenance

1. **Notify users** (if applicable)
2. **Put application in maintenance mode** (future: maintenance page)
3. **Run migrations:**
```bash
cd /opt/orcazap
sudo -u orcazap venv/bin/alembic upgrade head
```
4. **Restart services:**
```bash
sudo systemctl restart orcazap orcazap-worker
```
5. **Verify health:**
```bash
curl https://api.orcazap.com/health
```

## Contact Information

**On-Call Engineer:** [Fill in]
**Escalation:** [Fill in]
**Slack Channel:** [Fill in]




