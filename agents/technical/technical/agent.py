"""Technical specialist: consume ticket.triaged.technical, produce ticket.resolved."""
from shared.topics import TOPIC_TRIAGED_TECHNICAL
from shared.specialist_base import run_specialist

from .llm import generate_response
from .telemetry import get_trace_id, TECHNICAL_RESOLVED
from .config import KAFKA_BOOTSTRAP_SERVERS


def on_processed(ticket_id: str, response: str) -> None:
    TECHNICAL_RESOLVED.inc()


def run() -> None:
    run_specialist(
        agent_name="technical",
        input_topic=TOPIC_TRIAGED_TECHNICAL,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        generate_response=generate_response,
        get_trace_id=get_trace_id,
        on_processed=on_processed,
    )
