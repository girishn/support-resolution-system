"""
Integration: Agent + Ollama

Does the AI return a usable response in expected format?
Requires: Ollama running, MOCK_LLM unset.
Skipped when Ollama unreachable or MOCK_LLM is set.
"""
import os
import urllib.error
import urllib.request
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.integration


def _ollama_reachable() -> bool:
    if os.environ.get("MOCK_LLM", "").lower() in ("1", "true", "yes"):
        return False
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    url = base.replace("/v1", "") + "/api/tags"
    try:
        req = urllib.request.Request(url)
        urllib.request.urlopen(req, timeout=3)
        return True
    except (urllib.error.URLError, OSError):
        return False


@pytest.mark.skipif(not _ollama_reachable(), reason="Ollama unreachable (run ollama serve) or MOCK_LLM=1")
@patch("triage.llm.LLM_PROVIDER", "ollama")
def test_agent_ollama_returns_usable_response():
    """Real classify_ticket call returns valid type, priority, reasoning."""
    from triage.config import TRIAGE_PRIORITIES, TRIAGE_TYPES
    from triage.llm import classify_ticket

    result = classify_ticket(
        subject="My bill is wrong",
        body="I was charged twice this month. Please help.",
        channel="portal",
    )
    assert result["type"] in TRIAGE_TYPES, f"Invalid type: {result.get('type')}"
    assert result["priority"] in TRIAGE_PRIORITIES, f"Invalid priority: {result.get('priority')}"
    assert isinstance(result.get("reasoning"), str) and len(result["reasoning"]) > 0


@pytest.mark.skipif(not _ollama_reachable(), reason="Ollama unreachable (run ollama serve) or MOCK_LLM=1")
@patch("triage.llm.LLM_PROVIDER", "ollama")
def test_agent_ollama_output_format():
    """AI response has exactly the keys expected by triage pipeline."""
    from triage.llm import classify_ticket

    result = classify_ticket(
        subject="Login fails",
        body="I get error 500 when I try to sign in.",
        channel="email",
    )
    required = {"type", "priority", "reasoning"}
    assert required.issubset(result.keys()), f"Missing keys: {required - result.keys()}"
