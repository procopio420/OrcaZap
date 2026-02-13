# ADR 0004: Systemd Deployment (No Docker in Production)

**Status:** Accepted  
**Date:** 2024-12  
**Deciders:** Platform Engineering Team

## Context

OrcaZap needs to run in production on VPS instances. We need to decide:
- How to run the application (Docker containers vs systemd services)
- How to manage service lifecycle (restarts, logging, dependencies)
- How to deploy updates

We need a deployment strategy that:
- Works well on small VPS instances (1GB RAM, 2 vCPU)
- Is simple to operate and debug
- Has minimal overhead
- Is easy to maintain

## Decision

We will use **systemd services** directly on VPS instances (no Docker in production).

## Decision Drivers

- **Simplicity**: No container orchestration, no Docker daemon overhead
- **Resource efficiency**: Direct process execution, no container layer overhead
- **Easier debugging**: Direct access to logs, processes, filesystem
- **VPS-friendly**: Works well on small VPS instances (1GB RAM)
- **Service management**: systemd handles restarts, logging, dependencies

## Considered Options

### Option 1: Systemd Services ✅

**Pros:**
- Simple setup (just systemd unit files)
- Low overhead (no container layer)
- Direct access to logs (`journalctl`)
- Easy debugging (direct process access)
- Built-in service management (restarts, dependencies)
- Works well on small VPS

**Cons:**
- Less portable (VPS-specific, not containerized)
- Manual dependency management (acceptable for controlled environment)
- No container isolation (acceptable for single-tenant VPS)

**Implementation:**
- systemd unit files: `orcazap.service`, `orcazap-worker.service`
- Services run as non-root user (`orcazap`)
- Logs via `journalctl`
- Dependencies: `After=network.target postgresql.service redis.service`

### Option 2: Docker Compose

**Pros:**
- Containerized (isolated, portable)
- Easy local dev (same as production)
- Dependency management (docker-compose)

**Cons:**
- Docker daemon overhead (~100MB RAM)
- More complex setup (Docker + docker-compose)
- Harder debugging (need to exec into containers)
- Overkill for single-tenant VPS

**Why not chosen:** Unnecessary overhead for single-tenant VPS deployment.

### Option 3: Kubernetes

**Pros:**
- Scalable, production-grade orchestration
- Self-healing, auto-scaling

**Cons:**
- Massive overkill for early-stage SaaS
- Complex setup and operation
- High resource requirements
- Not needed for single-tenant VPS

**Why not chosen:** Massive overkill for current needs.

## Consequences

### Positive

- **Simple deployment**: Just systemd unit files, no container orchestration
- **Low overhead**: Direct process execution, no container layer
- **Easy debugging**: Direct access to logs, processes, filesystem
- **Fast startup**: No container pull/start overhead
- **Resource efficient**: Minimal memory overhead

### Negative

- **Less portable**: VPS-specific, not containerized (acceptable for dedicated VPS)
- **Manual dependencies**: Need to manage Python dependencies manually (acceptable)
- **No isolation**: Processes run directly on host (acceptable for single-tenant VPS)

### Neutral

- **Deployment**: Use git + systemd restart (acceptable, can add deployment scripts)
- **Scaling**: Can still scale horizontally (multiple VPS instances)

## Implementation Notes

### Systemd Unit Files

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

### Deployment Process

1. **Deploy code:**
```bash
cd /opt/orcazap
sudo -u orcazap git pull
sudo -u orcazap venv/bin/pip install -r requirements.txt
```

2. **Run migrations:**
```bash
sudo -u orcazap venv/bin/alembic upgrade head
```

3. **Restart services:**
```bash
sudo systemctl restart orcazap orcazap-worker
```

### Logging

- Logs via `journalctl`: `sudo journalctl -u orcazap -f`
- Structured logging (JSON in production)
- Request IDs for tracing

## Future Considerations

- **Docker for local dev**: Can use Docker for local development (optional)
- **Containerization later**: Can migrate to Docker/Kubernetes if needed for scaling
- **Deployment automation**: Can add deployment scripts (Ansible, etc.)

## References

- [systemd Service Files](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [systemd Best Practices](https://www.freedesktop.org/software/systemd/man/systemd.exec.html)

