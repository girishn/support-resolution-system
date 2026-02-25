"""Generate draft response for feature request tickets."""
import logging
from .config import (
    LLM_PROVIDER,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    MOCK_LLM,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a product feedback specialist. Given a feature request ticket, write a brief, empathetic draft response (2-4 sentences). Thank the customer for the suggestion, acknowledge its value, and mention that the product team will review it. Do not promise timelines. Output the response text only, no JSON."""


def _call_openai(ticket_id: str, subject: str, body: str, reasoning: str) -> str:
    from openai import OpenAI
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Ticket: {ticket_id}\nSubject: {subject}\nTriage reasoning: {reasoning}\nBody:\n{body}"},
        ],
        temperature=0.3,
    )
    return (resp.choices[0].message.content or "").strip()


def _call_ollama(ticket_id: str, subject: str, body: str, reasoning: str) -> str:
    from openai import OpenAI
    client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
    resp = client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Ticket: {ticket_id}\nSubject: {subject}\nTriage reasoning: {reasoning}\nBody:\n{body}"},
        ],
        temperature=0.3,
    )
    return (resp.choices[0].message.content or "").strip()


def _call_anthropic(ticket_id: str, subject: str, body: str, reasoning: str) -> str:
    from anthropic import Anthropic
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
    client = Anthropic()
    msg = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Ticket: {ticket_id}\nSubject: {subject}\nTriage reasoning: {reasoning}\nBody:\n{body}"}],
    )
    return msg.content[0].text.strip()


def generate_response(ticket_id: str, subject: str, body: str, reasoning: str) -> str:
    """Return a draft feature-request response."""
    if MOCK_LLM:
        logger.info("MOCK_LLM enabled: returning fixed feature response")
        return "Thank you for your feature request. We appreciate you taking the time to share this with us. Our product team will review your suggestion and consider it for future releases. We'll keep you updated via this ticket."
    if LLM_PROVIDER == "anthropic":
        return _call_anthropic(ticket_id, subject, body, reasoning)
    if LLM_PROVIDER == "ollama":
        return _call_ollama(ticket_id, subject, body, reasoning)
    return _call_openai(ticket_id, subject, body, reasoning)
