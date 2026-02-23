"""LLM classification for triage: type, priority, reasoning."""
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

SYSTEM_PROMPT = f"""You are a support ticket triage agent. For each ticket, output exactly:
1. type: one of {list(TRIAGE_TYPES)} — category for routing to specialized agents.
2. priority: one of {list(TRIAGE_PRIORITIES)} — how urgent the ticket is.
3. reasoning: one short sentence explaining your classification.

Respond with valid JSON only, no markdown: {{"type": "<type>", "priority": "<priority>", "reasoning": "<reasoning>"}}"""


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
    # Strip markdown code block if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    out = json.loads(text)
    if out.get("type") not in TRIAGE_TYPES or out.get("priority") not in TRIAGE_PRIORITIES:
        raise ValueError(f"LLM returned invalid type/priority: {out}")
    return out


def _call_ollama(subject: str, body: str, channel: str) -> dict:
    from openai import OpenAI
    # Ollama exposes an OpenAI-compatible API; no API key required.
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
    if out.get("type") not in TRIAGE_TYPES or out.get("priority") not in TRIAGE_PRIORITIES:
        raise ValueError(f"LLM returned invalid type/priority: {out}")
    return out


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
    if out.get("type") not in TRIAGE_TYPES or out.get("priority") not in TRIAGE_PRIORITIES:
        raise ValueError(f"LLM returned invalid type/priority: {out}")
    return out


def classify_ticket(subject: str, body: str, channel: str = "portal") -> dict:
    """Return dict with type, priority, reasoning."""
    if MOCK_LLM:
        logger.info("MOCK_LLM enabled: returning fixed triage (no API call)")
        return {"type": "billing", "priority": "high", "reasoning": "Mock classification for e2e/CI."}
    if LLM_PROVIDER == "anthropic":
        return _call_anthropic(subject, body, channel)
    if LLM_PROVIDER == "ollama":
        return _call_ollama(subject, body, channel)
    return _call_openai(subject, body, channel)
