# OrcaZap Documentation

Welcome to the OrcaZap documentation. This is the central navigation hub for all technical documentation.

## Start Here

1. **[README.md](../README.md)** - Quick start guide and high-level overview
2. **[Architecture](architecture.md)** - System architecture and design decisions
3. **[Flows](flows.md)** - End-to-end application flows
4. **[Security](security.md)** - Security model and tenant isolation

## Architecture

- **[Architecture Overview](architecture.md)** - Component boundaries, multi-tenancy, tech stack
- **[Application Flows](flows.md)** - Webhook → worker → quote → approval flows
- **[Security Model](security.md)** - Tenant isolation, authentication, CSRF, webhooks

## Deployment & Operations

- **[Deployment Guide](deployment.md)** - Single-node and multi-node deployment modes
- **[Runbook](ops/runbook.md)** - Operational procedures and troubleshooting (private template)

## Architecture Decision Records (ADRs)

- **[0001: Why RQ](adr/0001-why-rq.md)** - Background job processing choice
- **[0002: Why HTMX](adr/0002-why-htmx.md)** - Admin panel technology choice
- **[0003: Host-Based Multitenancy](adr/0003-host-based-multitenancy.md)** - Multi-tenant routing design
- **[0004: Systemd Deployment](adr/0004-systemd-deploy.md)** - Production service management

## Archived Documentation

Historical implementation notes and step-by-step completion docs are archived in [docs/archive/](archive/README.md).

These documents capture the development process but are not the canonical source of truth. Refer to the docs above for current architecture and deployment information.




