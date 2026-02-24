"""Enrich ticket payload with customer info from DynamoDB."""
import logging
from typing import Any

from .config import DYNAMODB_TABLE

logger = logging.getLogger(__name__)


def enrich_payload(payload: dict[str, Any], customer_id: str) -> dict[str, Any]:
    """
    Fetch customer from DynamoDB and merge into payload under "customer".
    Returns payload unchanged if DYNAMODB_TABLE not set or customer not found.
    """
    if not DYNAMODB_TABLE:
        return payload

    try:
        from shared.aws.dynamodb import get_customer

        customer = get_customer(customer_id, DYNAMODB_TABLE)
        if customer:
            enriched = dict(payload)
            enriched["customer"] = customer
            logger.debug("Enriched payload for customer_id=%s", customer_id)
            return enriched
    except ImportError as e:
        logger.warning("shared.aws.dynamodb not available: %s", e)

    return payload
