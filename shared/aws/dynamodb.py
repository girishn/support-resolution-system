"""DynamoDB client for customer/user lookups. Used by agents to enrich ticket payloads."""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_customer(customer_id: str, table_name: str | None = None) -> dict[str, Any] | None:
    """
    Fetch customer record from DynamoDB by customer_id.
    Returns None if table not configured, customer not found, or on error.
    """
    if not table_name:
        return None

    try:
        import boto3
        from boto3.dynamodb.types import TypeDeserializer
        from botocore.exceptions import ClientError

        client = boto3.client("dynamodb")
        resp = client.get_item(
            TableName=table_name,
            Key={"customer_id": {"S": customer_id}},
        )
        item = resp.get("Item")
        if not item:
            return None

        deserializer = TypeDeserializer()
        return {k: deserializer.deserialize(v) for k, v in item.items()}
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.warning("DynamoDB table %s not found", table_name)
        else:
            logger.exception("DynamoDB get_item failed for customer_id=%s: %s", customer_id, e)
        return None
    except Exception as e:
        logger.exception("DynamoDB get_customer failed for customer_id=%s: %s", customer_id, e)
        return None
