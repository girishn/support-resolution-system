"""Kafka consumer/producer loop: consume ticket.created, produce ticket.triaged."""
import json
import time
from datetime import datetime, timezone

import structlog  # type: ignore[import-untyped]
from confluent_kafka import Consumer, Producer
from confluent_kafka import KafkaError

from .config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC
from .enricher import enrich_payload
from .llm import classify_ticket
from .telemetry import (
    PROCESSING_SECONDS,
    TICKETS_ENRICHED,
    TICKETS_FAILED,
    TICKETS_PROCESSED,
    LLM_LATENCY_SECONDS,
    get_or_create_trace_id,
)

logger = structlog.get_logger(__name__)


def run():
    logger.debug("Starting triage agent Kafka consumer/producer loop")
    # Reduce rdkafka stderr noise (e.g. "connection closed by peer") so app logs are visible; 4 = warning.
    kafka_common = {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "log_level": 4,
    }
    consumer = Consumer({
        **kafka_common,
        "group.id": "triage-agent",
        "auto.offset.reset": "earliest",
    })
    producer = Producer(kafka_common)
    consumer.subscribe([KAFKA_TOPIC])

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
            TICKETS_FAILED.labels(reason="consumer_error").inc()
            continue
        try:
            value = json.loads(msg.value().decode("utf-8"))
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning("Invalid message value", error=str(e))
            TICKETS_FAILED.labels(reason="invalid_json").inc()
            continue

        event_type = value.get("event_type")
        ticket_id = value.get("ticket_id")
        trace_id = get_or_create_trace_id(value)
        structlog.contextvars.bind_contextvars(trace_id=trace_id, ticket_id=ticket_id)

        logger.info("Received message", event_type=event_type)
        if event_type != "ticket.created":
            continue

        customer_id = value.get("customer_id")
        subject = value.get("subject", "")
        body = value.get("body", "")
        channel = value.get("channel", "portal")

        if not ticket_id or not customer_id:
            logger.warning("Skipping message missing ticket_id or customer_id")
            TICKETS_FAILED.labels(reason="missing_ids").inc()
            continue

        start_time = time.perf_counter()
        enriched = enrich_payload(value, customer_id)
        if "customer" in enriched:
            TICKETS_ENRICHED.inc()

        logger.info("Triage starting")
        try:
            t0 = time.perf_counter()
            result = classify_ticket(subject=subject, body=body, channel=channel)
            LLM_LATENCY_SECONDS.observe(time.perf_counter() - t0)
        except Exception as e:
            logger.exception("LLM classification failed", error=str(e))
            TICKETS_FAILED.labels(reason="llm_error").inc()
            continue

        triaged = {
            "event_type": "ticket.triaged",
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "trace_id": trace_id,
            "type": result["type"],
            "priority": result["priority"],
            "triaged_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "reasoning": result["reasoning"],
            "original_subject": subject,
        }
        if "customer" in enriched:
            triaged["customer"] = enriched["customer"]
        out_value = json.dumps(triaged).encode("utf-8")
        headers = [("trace_id", trace_id.encode("utf-8"))]
        producer.produce(
            KAFKA_TOPIC,
            key=ticket_id.encode("utf-8"),
            value=out_value,
            headers=headers,
            callback=lambda err, _: logger.error("Produce error", error=str(err)) if err else None,
        )
        producer.flush(timeout=10)
        PROCESSING_SECONDS.observe(time.perf_counter() - start_time)
        TICKETS_PROCESSED.labels(type=result["type"], priority=result["priority"]).inc()
        logger.info("Produced ticket.triaged", type=result["type"], priority=result["priority"])
