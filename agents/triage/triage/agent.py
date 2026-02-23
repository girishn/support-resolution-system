"""Kafka consumer/producer loop: consume ticket.created, produce ticket.triaged."""
import json
import logging
from datetime import datetime, timezone
from confluent_kafka import Consumer, Producer
from confluent_kafka import KafkaError

from .config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC
from .llm import classify_ticket

logger = logging.getLogger(__name__)


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
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            logger.error("Consumer error: %s", msg.error())
            continue

        try:
            value = json.loads(msg.value().decode("utf-8"))
        except (json.JSONDecodeError, AttributeError) as e:
            logger.warning("Invalid message value: %s", e)
            continue

        event_type = value.get("event_type")
        logger.info("Received message event_type=%s ticket_id=%s", event_type, value.get("ticket_id"))
        if event_type != "ticket.created":
            continue

        ticket_id = value.get("ticket_id")
        customer_id = value.get("customer_id")
        subject = value.get("subject", "")
        body = value.get("body", "")
        channel = value.get("channel", "portal")

        if not ticket_id or not customer_id:
            logger.warning("Skipping message missing ticket_id or customer_id")
            continue

        logger.info("Triage ticket_id=%s", ticket_id)
        try:
            result = classify_ticket(subject=subject, body=body, channel=channel)
        except Exception as e:
            logger.exception("LLM classification failed for ticket_id=%s: %s", ticket_id, e)
            continue

        triaged = {
            "event_type": "ticket.triaged",
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "type": result["type"],
            "priority": result["priority"],
            "triaged_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "reasoning": result["reasoning"],
            "original_subject": subject,
        }
        out_value = json.dumps(triaged).encode("utf-8")
        producer.produce(
            KAFKA_TOPIC,
            key=ticket_id.encode("utf-8"),
            value=out_value,
            callback=lambda err, _: logger.error("Produce error: %s", err) if err else None,
        )
        producer.flush(timeout=10)
        logger.info("Produced ticket.triaged ticket_id=%s type=%s priority=%s", ticket_id, result["type"], result["priority"])
