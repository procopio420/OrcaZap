# ADR 0001: Why RQ for Background Job Processing

**Status:** Accepted  
**Date:** 2024-12  
**Deciders:** Platform Engineering Team

## Context

OrcaZap needs background job processing for:
- Processing inbound WhatsApp messages (async, <200ms webhook response target)
- Generating quotes (pricing calculations, freight, discounts)
- Sending WhatsApp messages (API calls with retries)
- State machine transitions (conversation state updates)

We need a job queue that:
- Handles thousands of jobs per hour (early-stage SaaS scale)
- Runs reliably on small VPS instances (1GB RAM, 2 vCPU)
- Integrates well with Python/FastAPI
- Is simple to operate and debug
- Supports job retries and failure handling

## Decision

We will use **RQ (Redis Queue)** for background job processing.

## Decision Drivers

- **Simplicity**: Minimal setup, Redis-based, no separate message broker
- **Resource efficiency**: Runs well on small VPS instances
- **Python-native**: Pure Python implementation, easy to debug
- **Sufficient scale**: Handles early-stage SaaS workloads (thousands of jobs/hour)
- **Low overhead**: Direct Redis connection, no complex broker

## Considered Options

### Option 1: RQ (Redis Queue) ✅

**Pros:**
- Simple setup (just Redis, no separate broker)
- Python-native, easy to debug
- Lightweight, low memory footprint
- Good documentation and community
- Built-in job retries and failure handling
- Works well on small VPS instances

**Cons:**
- No built-in task scheduling (use cron + RQ for scheduled jobs)
- Single queue by default (can use multiple queues if needed)
- Redis as single point of failure (acceptable for MVP, can add Sentinel later)

**Implementation:**
- Redis as queue backend
- RQ workers as systemd services
- Job definitions in `app/worker/jobs.py`
- Job handlers in `app/worker/handlers.py`

### Option 2: Celery

**Pros:**
- More features (task scheduling, distributed routing, result backend)
- Mature and widely used
- Good documentation

**Cons:**
- Heavier setup (requires message broker: RabbitMQ or Redis)
- More complex configuration
- Higher memory footprint
- Overkill for early-stage SaaS needs

**Why not chosen:** Too complex for MVP needs, unnecessary overhead.

### Option 3: Sidekiq (Ruby)

**Not applicable:** OrcaZap is Python-based.

### Option 4: Kafka

**Pros:**
- High throughput, distributed, scalable
- Event streaming capabilities

**Cons:**
- Complex setup and operation
- Requires Zookeeper (or KRaft mode)
- High resource requirements
- Overkill for early-stage SaaS

**Why not chosen:** Massive overkill for current needs, complex to operate.

## Consequences

### Positive

- **Simple deployment**: Just Redis + RQ workers, no complex broker setup
- **Easy debugging**: Python stack traces, direct Redis inspection
- **Low resource usage**: Runs efficiently on small VPS instances
- **Fast development**: Quick to set up and iterate on job processing
- **Good enough scale**: Handles thousands of jobs/hour (sufficient for MVP)

### Negative

- **No built-in scheduling**: Need cron jobs to enqueue scheduled tasks (acceptable)
- **Single queue**: Can't easily route jobs to different worker pools (acceptable for MVP)
- **Redis dependency**: Redis becomes critical infrastructure (can add Sentinel for HA later)

### Neutral

- **Job persistence**: Jobs stored in Redis (acceptable, can add persistence layer if needed)
- **Monitoring**: Basic RQ monitoring available, can add RQ dashboard if needed

## Implementation Notes

- RQ workers run as systemd services (`orcazap-worker.service`)
- Can run multiple worker processes for parallel processing
- Jobs are idempotent (safe to retry)
- Failed jobs moved to failed queue (manual review/retry)

## Future Considerations

- **Horizontal scaling**: Add more worker instances as load increases
- **High availability**: Add Redis Sentinel for Redis HA
- **Monitoring**: Add RQ dashboard or Prometheus metrics
- **Scheduled jobs**: Use cron + RQ for periodic tasks
- **Multiple queues**: Use separate queues for different job types if needed

## References

- [RQ Documentation](https://python-rq.org/)
- [RQ GitHub](https://github.com/rq/rq)

