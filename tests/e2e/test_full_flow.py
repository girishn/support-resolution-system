"""E2E test: produce ticket.created, consume ticket.resolved.

Requires: KAFKA_BOOTSTRAP_SERVERS, and triage + billing agents running with MOCK_LLM=true.
With MOCK_LLM, triage always classifies as "billing", so the billing agent handles the ticket.

Run from repo root:
  KAFKA_BOOTSTRAP_SERVERS=localhost:9092 pytest tests/e2e/test_full_flow.py -v -s
"""
import json
import os
import time

import pytest
from confluent_kafka import Consumer, Producer


KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "")
SKIP_E2E = not KAFKA_BOOTSTRAP or os.environ.get("SKIP_E2E_KAFKA", "").lower() in ("1", "true", "yes")


@pytest.fixture
def bootstrap_servers():
    return KAFKA_BOOTSTRAP


@pytest.fixture
def ticket_id():
    return f"e2e-pytest-{int(time.time())}"


@pytest.fixture
def trace_id():
    return f"e2e-trace-{int(time.time())}"


@pytest.mark.skipif(SKIP_E2E, reason="KAFKA_BOOTSTRAP_SERVERS not set; run with Kafka + agents")
def test_ticket_created_to_resolved(bootstrap_servers: str, ticket_id: str, trace_id: str):
    """Produce ticket.created, wait, consume ticket.resolved. Asserts flow completes."""
    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "event_type": "ticket.created",
        "ticket_id": ticket_id,
        "customer_id": "e2e-pytest-cust",
        "trace_id": trace_id,
        "subject": "Billing question",
        "body": "Why was I charged twice? Please help.",
        "created_at": created_at,
        "channel": "portal",
    }

    producer = Producer({"bootstrap.servers": bootstrap_servers})
    producer.produce(
        "ticket.events",
        key=ticket_id.encode("utf-8"),
        value=json.dumps(payload).encode("utf-8"),
        headers=[("trace_id", trace_id.encode("utf-8"))],
    )
    producer.flush(timeout=10)

    consumer = Consumer({
        "bootstrap.servers": bootstrap_servers,
        "group.id": f"e2e-test-{int(time.time())}",
        "auto.offset.reset": "latest",
    })
    consumer.subscribe(["ticket.resolved"])

    deadline = time.time() + 60
    resolved_event = None
    while time.time() < deadline:
        msg = consumer.poll(timeout=2.0)
        if msg and not msg.error():
            value = json.loads(msg.value().decode("utf-8"))
            if value.get("ticket_id") == ticket_id and value.get("event_type") == "ticket.resolved":
                resolved_event = value
                break
        time.sleep(0.5)

    consumer.close()
    assert resolved_event is not None, (
        f"No ticket.resolved for ticket_id={ticket_id} within 60s. "
        "Ensure triage and billing agents are running with MOCK_LLM=true."
    )
    assert resolved_event.get("resolved_by") == "billing"
    assert "response" in resolved_event
    assert len(resolved_event["response"]) > 0
