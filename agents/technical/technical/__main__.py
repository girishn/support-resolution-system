"""Entrypoint: python -m technical"""
import sys

import structlog

from .config import KAFKA_BOOTSTRAP_SERVERS, LOG_LEVEL
from .agent import run
from .telemetry import configure_logging, start_metrics_server


def main():
    configure_logging(log_level=LOG_LEVEL)
    start_metrics_server()
    log = structlog.get_logger()
    if not KAFKA_BOOTSTRAP_SERVERS:
        log.error("KAFKA_BOOTSTRAP_SERVERS is required")
        sys.exit(1)
    run()


if __name__ == "__main__":
    main()
