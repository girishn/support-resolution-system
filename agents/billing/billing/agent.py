"""Billing specialist: consume ticket.triaged.billing, produce ticket.resolved."""
from shared.topics import TOPIC_TRIAGED_BILLING
from shared.specialist_base import run_specialist

from .llm import generate_response
from .telemetry import get_trace_id, BILLING_RESOLVED, BILLING_PROCESSING_SECONDS
from .config import KAFKA_BOOTSTRAP_SERVERS


def on_processed(ticket_id: str, response: str) -> None:
    BILLING_RESOLVED.inc()


def run() -> None:
    run_specialist(
        agent_name="billing",
        input_topic=TOPIC_TRIAGED_BILLING,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        generate_response=generate_response,
        get_trace_id=get_trace_id,
        on_processed=on_processed,
    )
