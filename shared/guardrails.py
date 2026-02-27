"""Policy rule checks for response guardrails.

Runs before specialist agents emit ticket.resolved. Catches policy violations
(e.g. PII leakage, excessive length, forbidden content) and raises for retry or human review.
"""
import re
from typing import Sequence

# Max response length (chars). Excess gets truncated with a disclaimer.
MAX_RESPONSE_LENGTH = 4000

# Patterns that suggest PII leakage (basic heuristics; not comprehensive)
PII_PATTERNS = (
    re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),  # Credit card
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
)

# Forbidden phrases that should not appear in support responses
FORBIDDEN_PHRASES = (
    "I am not a lawyer",
    "I am not a doctor",
    "this is legal advice",
    "guaranteed approval",
    "100% refund",
)


def check_response(text: str, policies: Sequence[str] | None = None) -> str:
    """Apply policy rule checks. Returns (possibly modified) response or raises.

    Policies: "pii", "length", "forbidden". Default: all.
    Raises ValueError if policy is violated in a way that cannot be auto-fixed.
    Forbidden and PII checks run on the original text before any truncation.
    """
    policies = policies or ("pii", "length", "forbidden")
    result = str(text).strip()

    # Check rejection policies on original text before truncation
    if "forbidden" in policies:
        lower = result.lower()
        for phrase in FORBIDDEN_PHRASES:
            if phrase.lower() in lower:
                raise ValueError(f"Response contains forbidden phrase: {phrase!r}")

    if "pii" in policies:
        for pat in PII_PATTERNS:
            if pat.search(result):
                raise ValueError("Response appears to contain PII (e.g. card number, SSN, email)")

    if "length" in policies and len(result) > MAX_RESPONSE_LENGTH:
        result = result[: MAX_RESPONSE_LENGTH - 50] + "\n\n[Response truncated for length.]"

    return result
