"""Entrypoint: python -m triage"""
import sys

import structlog

from .config import (
    LOG_LEVEL,
    LOG_FORMAT,
    KAFKA_BOOTSTRAP_SERVERS,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
)
from .agent import run
from .telemetry import configure_logging, start_metrics_server

def main():
    configure_logging(log_level=LOG_LEVEL)
    start_metrics_server()

    log = structlog.get_logger()
    if not KAFKA_BOOTSTRAP_SERVERS:
        log.error("KAFKA_BOOTSTRAP_SERVERS is required", hint="e.g. kafka.confluent.local:9092")
        sys.exit(1)
    if LLM_PROVIDER == "openai" and not OPENAI_API_KEY:
        log.error("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        sys.exit(1)
    if LLM_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
        log.error("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        sys.exit(1)
    run()

if __name__ == "__main__":
    main()
