"""
Integration: Agent + DynamoDB

Does the real DynamoDB call work with real AWS credentials?
Requires: DYNAMODB_TABLE set, AWS credentials configured.
Skipped when not configured or credentials missing.
"""
import os

import pytest

pytestmark = pytest.mark.integration


def _dynamodb_configured() -> bool:
    table = os.environ.get("DYNAMODB_TABLE", "").strip()
    if not table:
        return False
    try:
        import boto3
        sts = boto3.client("sts")
        sts.get_caller_identity()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _dynamodb_configured(), reason="DynamoDB not configured (DYNAMODB_TABLE + AWS credentials)")
def test_agent_dynamodb_lookup_returns_customer():
    """Real get_customer call returns data when customer exists."""
    from shared.aws.dynamodb import get_customer

    table = os.environ.get("DYNAMODB_TABLE", "").strip()
    customer_id = os.environ.get("DYNAMODB_TEST_CUSTOMER_ID", "test-customer")
    result = get_customer(customer_id, table)

    if result is None:
        pytest.skip(
            f"Customer '{customer_id}' not found in table. "
            "Create a test item with customer_id='test-customer' or set DYNAMODB_TEST_CUSTOMER_ID."
        )

    assert isinstance(result, dict)
    assert "customer_id" in result or any(k for k in result if "customer" in k.lower() or "id" in k.lower())


@pytest.mark.skipif(not _dynamodb_configured(), reason="DynamoDB not configured (DYNAMODB_TABLE + AWS credentials)")
def test_agent_dynamodb_enrich_integration():
    """Enricher merges real DynamoDB customer data into payload."""
    from triage.enricher import enrich_payload

    customer_id = os.environ.get("DYNAMODB_TEST_CUSTOMER_ID", "test-customer")
    payload = {
        "event_type": "ticket.created",
        "ticket_id": "int-dynamo-1",
        "customer_id": customer_id,
        "subject": "Test",
        "body": "Body",
    }

    enriched = enrich_payload(payload, customer_id)

    if "customer" not in enriched:
        pytest.skip(
            f"Customer '{customer_id}' not found. "
            "Create a test item or set DYNAMODB_TEST_CUSTOMER_ID to an existing customer_id."
        )

    assert enriched["customer_id"] == customer_id
    assert "customer" in enriched
    assert isinstance(enriched["customer"], dict)
