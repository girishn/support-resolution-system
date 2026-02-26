"""
Integration: Event schema

Does ticket.triaged match the JSON schema in events/?
Validates that build_triaged_event output conforms to events/ticket.triaged.schema.json.
"""
import json
from pathlib import Path

import pytest

from triage.agent import build_triaged_event

pytestmark = pytest.mark.integration


def _load_schema() -> dict:
    schema_path = Path(__file__).resolve().parent.parent.parent / "events" / "ticket.triaged.schema.json"
    with open(schema_path) as f:
        return json.load(f)


def test_ticket_triaged_output_matches_schema():
    """build_triaged_event output validates against ticket.triaged.schema.json."""
    try:
        import jsonschema
    except ImportError:
        pytest.skip("jsonschema not installed (pip install jsonschema)")

    schema = _load_schema()
    event = build_triaged_event(
        ticket_id="TKT-001",
        customer_id="cust-123",
        trace_id="trace-abc",
        result={"type": "billing", "priority": "high", "reasoning": "Billing-related complaint."},
        subject="My bill is wrong",
        body="I was charged twice.",
        customer=None,
    )

    # Schema allows extra fields (event_type, body, customer); we only validate structure
    jsonschema.validate(event, schema)


def test_ticket_triaged_with_customer_matches_schema():
    """build_triaged_event with customer dict still conforms (customer is extra, allowed)."""
    try:
        import jsonschema
    except ImportError:
        pytest.skip("jsonschema not installed (pip install jsonschema)")

    schema = _load_schema()
    event = build_triaged_event(
        ticket_id="TKT-002",
        customer_id="cust-456",
        trace_id="trace-xyz",
        result={"type": "technical", "priority": "medium", "reasoning": "Technical issue."},
        subject="Login fails",
        body="I cannot log in.",
        customer={"customer_id": "cust-456", "plan": "pro", "region": "us-east-1"},
    )

    jsonschema.validate(event, schema)
