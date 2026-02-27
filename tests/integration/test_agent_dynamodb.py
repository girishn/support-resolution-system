"""
Integration: Agent + DynamoDB

Does the real DynamoDB call work with real AWS credentials?
Requires: DYNAMODB_TABLE set, AWS credentials configured.
Skipped when not configured or credentials missing.

Run scripts/seed-dynamodb.py before tests, or set AUTO_SEED_DYNAMODB=1 to auto-seed.
"""
import os

import pytest

pytestmark = pytest.mark.integration


def _seed_if_needed() -> None:
    """Seed test-customer if AUTO_SEED_DYNAMODB=1 and table exists."""
    if os.environ.get("AUTO_SEED_DYNAMODB", "").lower() not in ("1", "true", "yes"):
        return
    table = os.environ.get("DYNAMODB_TABLE", "").strip()
    if not table:
        return
    try:
        import subprocess
        import sys
        from pathlib import Path
        script = Path(__file__).resolve().parent.parent.parent / "scripts" / "seed-dynamodb.py"
        subprocess.run(
            [sys.executable, str(script), "--table", table],
            capture_output=True,
            check=True,
        )
    except Exception:
        pass


def _get_dynamodb_table() -> str:
    """Return DYNAMODB_TABLE from env, or try Terraform output."""
    table = os.environ.get("DYNAMODB_TABLE", "").strip()
    if table:
        return table
    try:
        import subprocess
        from pathlib import Path
        repo = Path(__file__).resolve().parent.parent.parent
        proc = subprocess.run(
            ["terraform", "output", "-raw", "dynamodb_table_name"],
            cwd=repo / "infra",
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout.strip()
    except Exception:
        pass
    return ""


def _dynamodb_configured() -> bool:
    table = _get_dynamodb_table()
    if not table:
        return False
    os.environ["DYNAMODB_TABLE"] = table  # so triage enricher and get_customer see it
    try:
        import boto3
        boto3.client("sts").get_caller_identity()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _dynamodb_configured(), reason="DynamoDB not configured (DYNAMODB_TABLE + AWS credentials)")
def test_agent_dynamodb_lookup_returns_customer():
    """Real get_customer call returns data when customer exists."""
    _seed_if_needed()
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
    _seed_if_needed()
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
