"""Observability: structured logging, trace IDs, Prometheus metrics."""
import logging
import sys
import threading
import uuid

import structlog  # type: ignore[import-untyped]
from prometheus_client import Counter, Histogram, start_http_server  # type: ignore[import-untyped]

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
    """Configure structlog and standard logging for consistent JSON/console output.

    Both structlog (agent.py) and standard logging (enricher, llm, shared.aws.dynamodb)
    are routed through ProcessorFormatter so all logs share the same format.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    # Processors for stdlib-originated logs (enricher, llm, dynamodb) - merge contextvars
    # (trace_id, ticket_id) so they appear in output, then add logger name, format %s args.
    foreign_pre_chain: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    if LOG_FORMAT == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=foreign_pre_chain,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(level)


def start_metrics_server() -> None:
    """Start Prometheus HTTP server in a daemon thread."""
    def _serve():
        start_http_server(METRICS_PORT, addr="0.0.0.0")

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
