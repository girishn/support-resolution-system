"""Observability for feature agent."""
import logging
import sys
import threading
import uuid

import structlog  # type: ignore[import-untyped]
from prometheus_client import Counter, Histogram, start_http_server  # type: ignore[import-untyped]

from .config import LOG_FORMAT, METRICS_PORT

FEATURE_RESOLVED = Counter(
    "feature_tickets_resolved_total",
    "Feature request tickets successfully resolved",
)
FEATURE_FAILED = Counter(
    "feature_tickets_failed_total",
    "Feature request tickets that failed",
    ["reason"],
)
FEATURE_PROCESSING_SECONDS = Histogram(
    "feature_processing_seconds",
    "End-to-end processing time per feature ticket",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)


def get_trace_id(payload: dict) -> str:
    return payload.get("trace_id") or uuid.uuid4().hex


def configure_logging(log_level: str = "INFO") -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    foreign_pre_chain = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    renderer = structlog.processors.JSONRenderer() if LOG_FORMAT == "json" else structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=foreign_pre_chain,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(level)


def start_metrics_server() -> None:
    def _serve():
        start_http_server(METRICS_PORT, addr="0.0.0.0")
    t = threading.Thread(target=_serve, daemon=True)
    t.start()
