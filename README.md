# OrcaZap

WhatsApp-first quoting assistant for Brazilian construction material stores. Automates quote generation, pricing, and approval workflows via WhatsApp Cloud API.

## Core Features

- **WhatsApp Integration**: Receive quote requests and send formatted quotes via WhatsApp Cloud API
- **Automated Quoting**: Deterministic pricing engine with volume discounts, freight calculation, and payment method discounts
- **Multi-Tenant SaaS**: Host-based routing with strict tenant isolation
- **Approval Workflow**: Human-in-the-loop approval for edge cases (unknown SKUs, low margins, high values)
- **Admin Panel**: HTMX-based server-rendered dashboard for quote approvals and configuration

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              WhatsApp Cloud API                          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI Application (Uvicorn)                           │
│  ├── Webhook endpoints                                   │
│  ├── Admin panel (HTMX)                                  │
│  └── API endpoints                                       │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
┌──────────────┐         ┌──────────────┐
│  PostgreSQL  │         │    Redis     │
│  (Database)   │         │ (Queue/Cache)│
└──────────────┘         └──────┬───────┘
                                 │
                                 ▼
                        ┌──────────────┐
                        │  RQ Workers  │
                        │ (Background)  │
                        └──────────────┘
```

**Components:**
- **API**: FastAPI application handling webhooks, admin panel, and API endpoints
- **Worker**: RQ workers processing background jobs (message processing, quote generation)
- **Database**: PostgreSQL for persistent data
- **Queue**: Redis for job queue and session storage

**Multi-Tenancy:**
- Host-based routing: `{slug}.orcazap.com` for tenant dashboards
- `api.orcazap.com` for API endpoints and webhooks
- `orcazap.com` for public pages
- All queries filtered by `tenant_id` for isolation

## Quickstart

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Redis 7+
- Poetry (recommended) or pip

### Installation

1. **Clone and install dependencies:**
```bash
git clone <repo-url>
cd orcazap
poetry install  # or: pip install -r requirements.txt
```

2. **Set up environment:**
```bash
cp env.example .env
# Edit .env with your configuration
```

3. **Set up database:**
```bash
createdb orcazap
alembic upgrade head
```

4. **Start services:**
```bash
# Terminal 1: Start API
uvicorn app.main:app --reload

# Terminal 2: Start worker
rq worker --url redis://localhost:6379/0 default
```

5. **Run tests:**
```bash
pytest
```

## How It Works

1. **Webhook receives message**: WhatsApp Cloud API sends webhook → FastAPI stores message → enqueues job
2. **Worker processes**: RQ worker picks up job → creates/updates contact & conversation → state machine transition
3. **Data capture**: Customer provides CEP, payment method, delivery day, items → worker parses message
4. **Quote generation**: Pricing engine calculates quote → checks approval rules → auto-approve or require human approval
5. **Approval (if needed)**: Admin reviews in HTMX dashboard → approves/rejects → quote sent via WhatsApp
6. **Quote sent**: Formatted quote message sent → conversation state updated → customer can accept/decline

See [docs/flows.md](docs/flows.md) for detailed flow diagrams.

## Documentation

- **[Documentation Index](docs/index.md)** - Complete documentation navigation
- **[Architecture](docs/architecture.md)** - System design and boundaries
- **[Flows](docs/flows.md)** - End-to-end application flows
- **[Security](docs/security.md)** - Security model and tenant isolation
- **[Deployment](docs/deployment.md)** - Production deployment guide

## Tech Stack

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2.0, Alembic
- **Queue**: Redis, RQ (Redis Queue)
- **Frontend**: HTMX, Jinja2 templates
- **Database**: PostgreSQL 15+
- **Testing**: pytest
- **Code Quality**: ruff, mypy

## Development

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type check
mypy app

# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

## Sensitive Information Policy

**No sensitive production data in public documentation:**
- No real IP addresses or domains
- No tokens, keys, or passwords
- All secrets documented as required environment variables with placeholders
- Private infrastructure details kept in private runbooks

If you find sensitive information in public docs, please report it.

## License

[To be determined]
