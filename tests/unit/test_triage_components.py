"""
Unit tests for triage agent components per the test matrix:

1. AI prompt logic – Given ticket text → does it produce correct category?
2. Event parsing – Can we read a ticket.created JSON correctly?
3. DynamoDB lookup – Given customer_id → returns correct customer data
4. Triage decision logic – Given AI output → does agent route correctly?
5. Event producer – Does it build the ticket.triaged message correctly?
"""
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

# -----------------------------------------------------------------------------
# 1. AI prompt logic – Given ticket text → does it produce correct category?
# -----------------------------------------------------------------------------


@patch("triage.llm.MOCK_LLM", True)
def test_classify_ticket_mock_returns_billing():
    """Given ticket text, MOCK_LLM produces correct category (billing)."""
    from triage.llm import classify_ticket

    result = classify_ticket(
        subject="My bill is wrong",
        body="I was charged twice this month. Please help.",
        channel="portal",
    )
    assert result["type"] == "billing"
    assert result["priority"] == "high"
    assert "reasoning" in result


@patch("triage.llm.MOCK_LLM", True)
def test_classify_ticket_mock_returns_valid_type_and_priority():
    """MOCK_LLM always returns valid type and priority from allowed enums."""
    from triage.llm import classify_ticket
    from triage.config import TRIAGE_TYPES, TRIAGE_PRIORITIES

    result = classify_ticket(subject="Test", body="Body", channel="portal")
    assert result["type"] in TRIAGE_TYPES
    assert result["priority"] in TRIAGE_PRIORITIES


# -----------------------------------------------------------------------------
# 2. Event parsing – Can we read a ticket.created JSON correctly?
# -----------------------------------------------------------------------------


def test_parse_valid_ticket_created_json():
    """Valid ticket.created JSON is parsed correctly and yields expected fields."""
    payload = {
        "event_type": "ticket.created",
        "ticket_id": "TKT-001",
        "customer_id": "cust-123",
        "subject": "Billing issue",
        "body": "My bill is wrong",
        "created_at": "2024-01-15T10:00:00Z",
        "channel": "portal",
    }
    raw = json.dumps(payload).encode("utf-8")
    value = json.loads(raw.decode("utf-8"))

    assert value["event_type"] == "ticket.created"
    assert value["ticket_id"] == "TKT-001"
    assert value["customer_id"] == "cust-123"
    assert value["subject"] == "Billing issue"
    assert value["body"] == "My bill is wrong"
    assert value["channel"] == "portal"


def test_malformed_json_raises_clear_error():
    """Malformed JSON raises JSONDecodeError with clear message."""
    malformed = b"{ invalid json }"
    with pytest.raises(json.JSONDecodeError) as exc_info:
        json.loads(malformed.decode("utf-8"))
    assert "JSON" in str(exc_info.value) or "Expecting" in str(exc_info.value)


def test_empty_or_non_json_raises_error():
    """Empty string or non-JSON raises appropriate error."""
    with pytest.raises(json.JSONDecodeError):
        json.loads("")
    with pytest.raises(json.JSONDecodeError):
        json.loads("not json at all")


# -----------------------------------------------------------------------------
# 3. DynamoDB lookup – Given customer_id → returns correct customer data
# -----------------------------------------------------------------------------


@patch("triage.enricher.DYNAMODB_TABLE", "support-customers")
@patch("shared.aws.dynamodb.get_customer")
def test_enrich_payload_adds_customer_when_found(mock_get_customer):
    """Given customer_id, enricher merges customer data into payload."""
    from triage.enricher import enrich_payload

    mock_get_customer.return_value = {"email": "jane@example.com", "plan": "pro"}
    payload = {
        "event_type": "ticket.created",
        "ticket_id": "TKT-001",
        "customer_id": "cust-123",
        "subject": "Help",
        "body": "Body",
    }

    enriched = enrich_payload(payload, "cust-123")

    mock_get_customer.assert_called_once_with("cust-123", "support-customers")
    assert "customer" in enriched
    assert enriched["customer"]["email"] == "jane@example.com"
    assert enriched["customer"]["plan"] == "pro"


@patch("triage.enricher.DYNAMODB_TABLE", "support-customers")
@patch("shared.aws.dynamodb.get_customer")
def test_enrich_payload_unchanged_when_customer_not_found(mock_get_customer):
    """When customer not found, payload is returned unchanged."""
    from triage.enricher import enrich_payload

    mock_get_customer.return_value = None
    payload = {"ticket_id": "TKT-001", "customer_id": "unknown"}

    enriched = enrich_payload(payload, "unknown")

    assert "customer" not in enriched
    assert enriched == payload


@patch("triage.enricher.DYNAMODB_TABLE", None)
def test_enrich_payload_unchanged_when_dynamodb_not_configured():
    """When DYNAMODB_TABLE not set, payload is returned unchanged."""
    from triage.enricher import enrich_payload

    payload = {"ticket_id": "TKT-001", "customer_id": "cust-123"}
    enriched = enrich_payload(payload, "cust-123")

    assert enriched == payload
    assert "customer" not in enriched


# -----------------------------------------------------------------------------
# 4. Triage decision logic – Given AI output → does agent route correctly?
# -----------------------------------------------------------------------------


def test_topic_for_triage_type_billing():
    """billing → ticket.triaged.billing."""
    from shared.topics import topic_for_triage_type

    assert topic_for_triage_type("billing") == "ticket.triaged.billing"


def test_topic_for_triage_type_technical():
    """technical → ticket.triaged.technical."""
    from shared.topics import topic_for_triage_type

    assert topic_for_triage_type("technical") == "ticket.triaged.technical"


def test_topic_for_triage_type_feature_request():
    """feature_request → ticket.triaged.feature_request."""
    from shared.topics import topic_for_triage_type

    assert topic_for_triage_type("feature_request") == "ticket.triaged.feature_request"


def test_topic_for_triage_type_unknown_routes_to_human():
    """Unknown type routes to ticket.triaged.human (fallback queue, no silent drop)."""
    from shared.topics import topic_for_triage_type

    assert topic_for_triage_type("unknown") == "ticket.triaged.human"
    assert topic_for_triage_type("") == "ticket.triaged.human"


def test_topic_for_triage_type_route_to_human_overrides():
    """route_to_human=True overrides type and sends to human queue."""
    from shared.topics import topic_for_triage_type

    assert topic_for_triage_type("billing", route_to_human=True) == "ticket.triaged.human"
    assert topic_for_triage_type("technical", route_to_human=False) == "ticket.triaged.technical"


def test_topic_for_triage_type_account():
    """account → ticket.triaged.account."""
    from shared.topics import topic_for_triage_type

    assert topic_for_triage_type("account") == "ticket.triaged.account"


# -----------------------------------------------------------------------------
# 5. Event producer – Does it build the ticket.triaged message correctly?
# -----------------------------------------------------------------------------


def test_build_triaged_event_has_all_required_fields():
    """Ticket.triaged message includes all required schema fields."""
    from triage.agent import build_triaged_event

    result = {
        "type": "billing",
        "priority": "high",
        "reasoning": "Billing-related inquiry.",
    }
    triaged = build_triaged_event(
        ticket_id="TKT-001",
        customer_id="cust-123",
        trace_id="trace-abc",
        result=result,
        subject="Bill question",
        body="Why was I charged?",
        customer=None,
    )

    required = ["ticket_id", "customer_id", "type", "priority", "triaged_at", "reasoning"]
    for field in required:
        assert field in triaged, f"Missing required field: {field}"

    assert triaged["event_type"] == "ticket.triaged"
    assert triaged["ticket_id"] == "TKT-001"
    assert triaged["customer_id"] == "cust-123"
    assert triaged["type"] == "billing"
    assert triaged["priority"] == "high"
    assert triaged["original_subject"] == "Bill question"
    assert triaged["body"] == "Why was I charged?"
    # triaged_at is ISO 8601
    datetime.fromisoformat(triaged["triaged_at"].replace("Z", "+00:00"))


def test_build_triaged_event_includes_customer_when_provided():
    """When customer data is provided, it is merged into the event."""
    from triage.agent import build_triaged_event

    result = {"type": "technical", "priority": "medium", "reasoning": "Tech issue."}
    customer = {"email": "user@example.com", "plan": "free"}

    triaged = build_triaged_event(
        ticket_id="TKT-002",
        customer_id="cust-456",
        trace_id="trace-xyz",
        result=result,
        subject="Login failed",
        body="Cannot log in",
        customer=customer,
    )

    assert "customer" in triaged
    assert triaged["customer"]["email"] == "user@example.com"
    assert triaged["customer"]["plan"] == "free"


def test_build_triaged_event_excludes_customer_when_none():
    """When customer is None, customer field is not present."""
    from triage.agent import build_triaged_event

    result = {"type": "other", "priority": "low", "reasoning": "General question."}
    triaged = build_triaged_event(
        ticket_id="TKT-003",
        customer_id="cust-789",
        trace_id="trace-123",
        result=result,
        subject="Hi",
        body="Just saying hi",
        customer=None,
    )

    assert "customer" not in triaged


def test_build_triaged_event_adds_confidence_and_needs_review_when_low(monkeypatch):
    """When confidence < threshold, needs_review is True."""
    import triage.agent
    monkeypatch.setattr(triage.agent, "CONFIDENCE_THRESHOLD", 0.8)

    from triage.agent import build_triaged_event

    result = {"type": "billing", "priority": "high", "reasoning": "Maybe billing.", "confidence": 0.5}
    triaged = build_triaged_event(
        ticket_id="TKT-004",
        customer_id="cust-1",
        trace_id="trace-1",
        result=result,
        subject="Charge",
        body="Question",
        customer=None,
    )
    assert triaged["confidence"] == 0.5
    assert triaged["needs_review"] is True


def test_build_triaged_event_needs_review_when_unknown_type_without_confidence():
    """When type is unknown, needs_review is True even when confidence is absent."""
    from triage.agent import build_triaged_event

    result = {"type": "unknown", "priority": "medium", "reasoning": "Unclear category."}
    triaged = build_triaged_event(
        ticket_id="TKT-005",
        customer_id="cust-2",
        trace_id="trace-2",
        result=result,
        subject="???",
        body="Weird ticket",
        customer=None,
    )
    assert triaged["needs_review"] is True
    assert "confidence" not in triaged
