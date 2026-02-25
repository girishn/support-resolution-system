"""Feature specialist: consume ticket.triaged.feature_request, produce ticket.resolved."""
from shared.topics import TOPIC_TRIAGED_FEATURE_REQUEST
from shared.specialist_base import run_specialist

from .llm import generate_response
from .telemetry import get_trace_id, FEATURE_RESOLVED
from .config import KAFKA_BOOTSTRAP_SERVERS


def on_processed(ticket_id: str, response: str) -> None:
    FEATURE_RESOLVED.inc()


def run() -> None:
    run_specialist(
        agent_name="feature",
        input_topic=TOPIC_TRIAGED_FEATURE_REQUEST,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        generate_response=generate_response,
        get_trace_id=get_trace_id,
        on_processed=on_processed,
    )
