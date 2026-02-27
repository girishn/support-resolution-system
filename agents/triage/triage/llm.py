"""LLM classification for triage: type, priority, reasoning, confidence."""
import json
import logging
from .config import (
    LLM_PROVIDER,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    TRIAGE_TYPES,
    TRIAGE_PRIORITIES,
    MOCK_LLM,
)

logger = logging.getLogger(__name__)

# "unknown" is for fallback when LLM returns a type not in the known set
_KNOWN_TYPES = tuple(t for t in TRIAGE_TYPES if t != "unknown")

SYSTEM_PROMPT = f"""You are a support ticket triage agent. For each ticket, output:
1. type: one of {list(_KNOWN_TYPES)} — category for routing to specialized agents.
2. priority: one of {list(TRIAGE_PRIORITIES)} — how urgent the ticket is.
3. reasoning: one short sentence explaining your classification.
4. confidence: a number from 0.0 to 1.0 — how confident you are in this classification (1.0 = very sure, 0.5 = uncertain).

Respond with valid JSON only, no markdown: {{"type": "<type>", "priority": "<priority>", "reasoning": "<reasoning>", "confidence": <number>}}"""


def _normalize_result(out: dict) -> dict:
    """Validate and normalize LLM output. Unknown types route to fallback instead of raising."""
    type_val = out.get("type", "").strip().lower()
    priority = out.get("priority", "").strip().lower()
    if type_val not in _KNOWN_TYPES:
        logger.warning("LLM returned unknown type, routing to human queue", type=type_val, raw=out)
        type_val = "unknown"
    if priority not in TRIAGE_PRIORITIES:
        priority = "medium"
    confidence = out.get("confidence")
    if confidence is None:
        confidence = 0.5
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))
    return {
        "type": type_val,
        "priority": priority,
        "reasoning": str(out.get("reasoning", "")).strip() or "No reasoning provided.",
        "confidence": confidence,
    }


def _call_openai(subject: str, body: str, channel: str) -> dict:
    from openai import OpenAI
    if not OPENAI_API_KEY:
        raise ValueError(
            "OPENAI_API_KEY is required when LLM_PROVIDER=openai. "
            "For in-cluster Ollama set LLM_PROVIDER=ollama and OLLAMA_BASE_URL in the ConfigMap."
        )
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Subject: {subject}\nChannel: {channel}\nBody:\n{body}"},
        ],
        temperature=0.2,
    )
    text = resp.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    out = json.loads(text)
    return _normalize_result(out)


def _call_ollama(subject: str, body: str, channel: str) -> dict:
    from openai import OpenAI
    client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
    resp = client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Subject: {subject}\nChannel: {channel}\nBody:\n{body}"},
        ],
        temperature=0.2,
    )
    text = (resp.choices[0].message.content or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    out = json.loads(text)
    return _normalize_result(out)


def _call_anthropic(subject: str, body: str, channel: str) -> dict:
    from anthropic import Anthropic
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
    client = Anthropic()
    msg = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Subject: {subject}\nChannel: {channel}\nBody:\n{body}"}],
    )
    text = msg.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    out = json.loads(text)
    return _normalize_result(out)


def classify_ticket(subject: str, body: str, channel: str = "portal") -> dict:
    """Return dict with type, priority, reasoning, confidence."""
    if MOCK_LLM:
        logger.info("MOCK_LLM enabled: returning fixed triage (no API call)")
        return {"type": "billing", "priority": "high", "reasoning": "Mock classification for e2e/CI.", "confidence": 1.0}
    if LLM_PROVIDER == "anthropic":
        return _call_anthropic(subject, body, channel)
    if LLM_PROVIDER == "ollama":
        return _call_ollama(subject, body, channel)
    return _call_openai(subject, body, channel)
