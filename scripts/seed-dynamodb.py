#!/usr/bin/env python3
"""
Bootstrap DynamoDB with test customer data for integration tests and E2E.

Seeds the customers table with known test records. Idempotent (put_item overwrites).

Usage:
  DYNAMODB_TABLE=support-customers python scripts/seed-dynamodb.py
  python scripts/seed-dynamodb.py --table support-customers

After infra Terraform: terraform -chdir=infra output -raw dynamodb_table_name
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add repo root for shared imports if needed
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))


DEFAULT_TEST_CUSTOMERS = [
    {
        "customer_id": "test-customer",
        "plan": "pro",
        "region": "us-east-1",
        "email": "test@example.com",
        "tier": "premium",
    },
    {
        "customer_id": "e2e-cust",
        "plan": "starter",
        "region": "us-west-2",
        "email": "e2e@example.com",
    },
    {
        "customer_id": "int-cust",
        "plan": "enterprise",
        "region": "us-east-1",
    },
]


def _serialize(val) -> dict:
    """Convert Python value to DynamoDB AttributeValue format."""
    if isinstance(val, str):
        return {"S": val}
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return {"N": str(val)}
    if isinstance(val, bool):
        return {"BOOL": val}
    if isinstance(val, list):
        return {"L": [_serialize(v) for v in val]}
    if isinstance(val, dict):
        return {"M": {k: _serialize(v) for k, v in val.items()}}
    if val is None:
        return {"NULL": True}
    raise TypeError(f"Cannot serialize {type(val)}")


def seed_table(table_name: str, customers: list[dict], region: str | None = None) -> int:
    """Put customer items into DynamoDB. Returns count of items written."""
    import boto3
    client = boto3.client("dynamodb", region_name=region)
    for item in customers:
        dynamo_item = {k: _serialize(v) for k, v in item.items()}
        client.put_item(TableName=table_name, Item=dynamo_item)
    return len(customers)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed DynamoDB with test customers for integration tests",
        epilog="Requires AWS credentials. Table must exist (run infra Terraform first).",
    )
    parser.add_argument(
        "--table",
        default=os.environ.get("DYNAMODB_TABLE", ""),
        help="DynamoDB table name (or set DYNAMODB_TABLE)",
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="JSON file with list of customer objects (optional; uses built-in defaults if omitted)",
    )
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    args = parser.parse_args()

    table = args.table.strip()
    if not table:
        print("Error: --table or DYNAMODB_TABLE required", file=sys.stderr)
        return 1

    if args.file:
        customers = json.loads(args.file.read_text())
        if not isinstance(customers, list):
            customers = [customers]
    else:
        customers = DEFAULT_TEST_CUSTOMERS

    try:
        n = seed_table(table, customers, args.region)
        print(f"Seeded {n} customer(s) into {table}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
