"""Entrypoint: python -m triage"""
import logging
import sys

from .config import LOG_LEVEL, KAFKA_BOOTSTRAP_SERVERS, LLM_PROVIDER, OPENAI_API_KEY, ANTHROPIC_API_KEY
from .agent import run

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)

def main():
    if not KAFKA_BOOTSTRAP_SERVERS:
        logging.error("KAFKA_BOOTSTRAP_SERVERS is required (e.g. kafka.confluent.local:9092; run agent in-cluster or from a host in the VPC so b0/b1/b2 resolve)")
        sys.exit(1)
    if LLM_PROVIDER == "openai" and not OPENAI_API_KEY:
        logging.error("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        sys.exit(1)
    if LLM_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
        logging.error("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        sys.exit(1)
    run()

if __name__ == "__main__":
    main()
