"""Kafka topic names for the support resolution system."""

# Triage input (ticket.created)
TOPIC_TICKET_EVENTS = "ticket.events"

# Type-specific topics: triage produces here based on classification
TOPIC_TRIAGED_BILLING = "ticket.triaged.billing"
TOPIC_TRIAGED_TECHNICAL = "ticket.triaged.technical"
TOPIC_TRIAGED_FEATURE_REQUEST = "ticket.triaged.feature_request"
TOPIC_TRIAGED_ACCOUNT = "ticket.triaged.account"
TOPIC_TRIAGED_OTHER = "ticket.triaged.other"
# Fallback/human queue: unknown types, low-confidence classifications
TOPIC_TRIAGED_HUMAN = "ticket.triaged.human"

# Resolved output: specialist agents produce here
TOPIC_RESOLVED = "ticket.resolved"


def topic_for_triage_type(triage_type: str, route_to_human: bool = False) -> str:
    """Return the Kafka topic for a triage type. Used by triage agent.

    When route_to_human is True (low confidence or needs review), always use human queue.
    Unknown types (not in known set) map to human queue instead of being dropped.
    """
    if route_to_human:
        return TOPIC_TRIAGED_HUMAN
    return {
        "billing": TOPIC_TRIAGED_BILLING,
        "technical": TOPIC_TRIAGED_TECHNICAL,
        "feature_request": TOPIC_TRIAGED_FEATURE_REQUEST,
        "account": TOPIC_TRIAGED_ACCOUNT,
        "other": TOPIC_TRIAGED_OTHER,
        "unknown": TOPIC_TRIAGED_HUMAN,
    }.get(triage_type, TOPIC_TRIAGED_HUMAN)
