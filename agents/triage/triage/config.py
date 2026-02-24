"""Load configuration from environment."""
import os
from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "ticket.events")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic").lower()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# Ollama (local or in-cluster): base URL for the API (OpenAI-compatible), no API key needed.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
# When set (e.g. "1" or "true"), skip real LLM calls and return a fixed triage (for e2e/CI without API credits).
MOCK_LLM = os.environ.get("MOCK_LLM", "").lower() in ("1", "true", "yes")
# DynamoDB table for customer lookups (optional). When set, triage enriches payload with customer info.
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE", "").strip() or None
# Observability: "json" for structured logs (prod), "console" for human-readable (dev).
LOG_FORMAT = os.environ.get("LOG_FORMAT", "json").lower()
# Prometheus metrics HTTP port.
METRICS_PORT = int(os.environ.get("METRICS_PORT", "9090"))

# Allowed values for ticket.triaged
TRIAGE_TYPES = ("billing", "technical", "feature_request", "account", "other")
TRIAGE_PRIORITIES = ("low", "medium", "high", "critical")
