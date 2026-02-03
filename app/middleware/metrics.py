"""Prometheus metrics middleware."""

import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

# HTTP metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

# Business metrics
quotes_generated_total = Counter(
    "quotes_generated_total",
    "Total quotes generated",
    ["tenant_id", "status"],
)

messages_processed_total = Counter(
    "messages_processed_total",
    "Total messages processed",
    ["tenant_id", "direction"],
)

ai_calls_total = Counter(
    "ai_calls_total",
    "Total AI/LLM calls",
    ["provider", "tenant_id"],
)

ai_call_cost = Counter(
    "ai_call_cost_total",
    "Total AI/LLM call cost in USD",
    ["provider", "tenant_id"],
)

approvals_created_total = Counter(
    "approvals_created_total",
    "Total approvals created",
    ["tenant_id", "reason_type"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect Prometheus metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and collect metrics."""
        start_time = time.time()
        
        # Get endpoint path (simplified)
        endpoint = request.url.path
        method = request.method
        
        # Skip metrics endpoint itself
        if endpoint == "/metrics":
            return await call_next(request)
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Record metrics
        status_code = response.status_code
        http_requests_total.labels(method=method, endpoint=endpoint, status=status_code).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
        
        return response


def record_quote_generated(tenant_id: str, status: str):
    """Record a quote generation metric."""
    quotes_generated_total.labels(tenant_id=tenant_id, status=status).inc()


def record_message_processed(tenant_id: str, direction: str):
    """Record a message processing metric."""
    messages_processed_total.labels(tenant_id=tenant_id, direction=direction).inc()


def record_ai_call(provider: str, tenant_id: str, cost: float = 0.0):
    """Record an AI/LLM call metric."""
    ai_calls_total.labels(provider=provider, tenant_id=tenant_id).inc()
    if cost > 0:
        ai_call_cost.labels(provider=provider, tenant_id=tenant_id).inc(cost)


def record_approval_created(tenant_id: str, reason_type: str):
    """Record an approval creation metric."""
    approvals_created_total.labels(tenant_id=tenant_id, reason_type=reason_type).inc()


