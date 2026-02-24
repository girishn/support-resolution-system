"""Observability: structured logging, trace IDs, Prometheus metrics."""
import logging
import threading
import uuid

import structlog
from prometheus_client import Counter, Histogram, start_http_server

from .config import LOG_FORMAT, METRICS_PORT

# -----------------------------------------------------------------------------
# Prometheus metrics
# -----------------------------------------------------------------------------

TICKETS_PROCESSED = Counter(
    "triage_tickets_processed_total",
    "Tickets successfully triaged and produced",
    ["type", "priority"],
)
TICKETS_FAILED = Counter(
    "triage_tickets_failed_total",
    "Tickets that failed processing",
    ["reason"],
)
PROCESSING_SECONDS = Histogram(
    "triage_processing_seconds",
    "End-to-end processing time per ticket",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
LLM_LATENCY_SECONDS = Histogram(
    "triage_llm_latency_seconds",
    "LLM classification latency",
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0),
)
TICKETS_ENRICHED = Counter(
    "triage_tickets_enriched_total",
    "Tickets enriched with customer data from DynamoDB",
)


def get_or_create_trace_id(payload: dict) -> str:
    """Extract trace_id from payload or Kafka headers, or generate one."""
    trace_id = payload.get("trace_id")
    if trace_id:
        return trace_id
    return uuid.uuid4().hex


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog for JSON (prod) or console (dev) output."""
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    if LOG_FORMAT == "json":
        processors = shared_processors + [
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(),
        ]
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def start_metrics_server() -> None:
    """Start Prometheus HTTP server in a daemon thread."""
    def _serve():
        start_http_server(METRICS_PORT, addr="0.0.0.0")

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
