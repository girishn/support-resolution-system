"""Shared logic for specialist agents: consume ticket.triaged, produce ticket.resolved."""
import json
import time
from datetime import datetime, timezone
from typing import Callable

import structlog  # type: ignore[import-untyped]
from confluent_kafka import Consumer, Producer, KafkaError

from .topics import TOPIC_RESOLVED


logger = structlog.get_logger(__name__)


def run_specialist(
    agent_name: str,
    input_topic: str,
    bootstrap_servers: str,
    generate_response: Callable[[str, str, str, str], str],
    get_trace_id: Callable[[dict], str],
    on_processed: Callable[[str, str], None] | None = None,
) -> None:
    """
    Main loop: consume from input_topic (ticket.triaged.*), produce ticket.resolved.

    generate_response(ticket_id, subject, body, reasoning) -> response_text
    get_trace_id(payload) -> trace_id
    on_processed(ticket_id, response) -> optional callback for metrics
    """
    kafka_common = {"bootstrap.servers": bootstrap_servers, "log_level": 4}
    consumer = Consumer({
        **kafka_common,
        "group.id": f"{agent_name}-agent",
        "auto.offset.reset": "earliest",
    })
    producer = Producer(kafka_common)
    consumer.subscribe([input_topic])

    while True:
        msg = consumer.poll(timeout=1.0)
        if msg is None:
            continue
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            partition=msg.partition(),
            offset=msg.offset(),
        )
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            logger.error("Consumer error", error=str(msg.error()))
            continue
        try:
            value = json.loads(msg.value().decode("utf-8"))
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning("Invalid message value", error=str(e))
            continue

        event_type = value.get("event_type")
        ticket_id = value.get("ticket_id")
        trace_id = get_trace_id(value)
        structlog.contextvars.bind_contextvars(trace_id=trace_id, ticket_id=ticket_id)

        logger.info("Received message", event_type=event_type)
        if event_type != "ticket.triaged":
            continue

        subject = value.get("original_subject", value.get("subject", ""))
        body = value.get("body", "")
        reasoning = value.get("reasoning", "")
        triage_type = value.get("type", "")

        if not ticket_id:
            logger.warning("Skipping message missing ticket_id")
            continue

        start_time = time.perf_counter()
        try:
            response_text = generate_response(ticket_id, subject, body, reasoning)
        except Exception as e:
            logger.exception("Response generation failed", error=str(e))
            continue

        resolved = {
            "event_type": "ticket.resolved",
            "ticket_id": ticket_id,
            "customer_id": value.get("customer_id", ""),
            "trace_id": trace_id,
            "triage_type": triage_type,
            "resolved_by": agent_name,
            "resolved_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "response": response_text,
        }
        if "customer" in value:
            resolved["customer"] = value["customer"]

        out_value = json.dumps(resolved).encode("utf-8")
        headers = [("trace_id", trace_id.encode("utf-8"))]
        producer.produce(
            TOPIC_RESOLVED,
            key=ticket_id.encode("utf-8"),
            value=out_value,
            headers=headers,
            callback=lambda err, _: logger.error("Produce error", error=str(err)) if err else None,
        )
        producer.flush(timeout=10)
        elapsed = time.perf_counter() - start_time
        logger.info("Produced ticket.resolved", ticket_id=ticket_id, elapsed_sec=round(elapsed, 2))
        if on_processed:
            on_processed(ticket_id, response_text)
