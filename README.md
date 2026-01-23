# OrcaZap

WhatsApp-first quoting assistant for Brazilian construction material stores.

## Product Overview

OrcaZap automates the quoting process for construction material stores via WhatsApp:
- Receives inbound WhatsApp messages (WhatsApp Cloud API)
- Collects minimal data in a single question block
- Generates deterministic quotes (pricing rules, freight, margins)
- Sends formatted quotes via WhatsApp
- Requires human approval for edge cases (unknown SKU, low margin, etc.)

## Tech Stack

- Python 3.12+
- FastAPI
- HTMX (server-rendered admin panel)
- PostgreSQL
- Redis
- RQ (Redis Queue) for workers
- Alembic for migrations
- pytest for testing
- ruff for linting
- black/ruff-format for formatting

## Development Setup

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Redis 7+
- Poetry (recommended) or pip

### Installation

1. Clone the repository:
```bash
git clone <repo-url>
cd orcazap
```

2. Install dependencies:
```bash
# Using Poetry
poetry install

# Or using pip
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Set up database:
```bash
# Create database
createdb orcazap

# Run migrations
alembic upgrade head
```

5. Run tests:
```bash
pytest
```

6. Start development server:
```bash
uvicorn app.main:app --reload
```

## Project Structure

```
orcazap/
├── app/
│   ├── main.py              # FastAPI application
│   ├── settings.py           # Configuration
│   ├── db/                   # Database session, models
│   ├── domain/              # Business logic (pricing, freight, state machine)
│   ├── adapters/            # External adapters (WhatsApp, etc.)
│   ├── admin/               # Admin panel routes and templates
│   └── worker/              # RQ worker and jobs
├── tests/
│   ├── unit/                # Unit tests
│   └── integration/         # Integration tests
├── docs/                    # Documentation
├── alembic/                 # Database migrations
└── scripts/                 # Utility scripts
```

## Documentation

- [Data Model](docs/data_model.md)
- [State Machine](docs/state_machine.md)
- [Message Templates](docs/message_templates.md)
- [WhatsApp Integration](docs/whatsapp.md)
- [Worker & Queue](docs/worker.md)
- [Admin UI](docs/admin_ui.md)
- [Infrastructure](docs/infra.md)

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_pricing.py

# Run with verbose output
pytest -v
```

## Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type check (if mypy configured)
mypy app
```

## CI/CD

GitHub Actions runs on every push:
- Linting (ruff)
- Formatting check (ruff format --check)
- Type checking (mypy, if configured)
- Tests (pytest)

## License

[To be determined]


