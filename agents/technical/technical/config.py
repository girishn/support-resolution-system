"""Load configuration from environment."""
import os
from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic").lower()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
MOCK_LLM = os.environ.get("MOCK_LLM", "").lower() in ("1", "true", "yes")
LOG_FORMAT = os.environ.get("LOG_FORMAT", "json").lower()
METRICS_PORT = int(os.environ.get("METRICS_PORT", "9092"))
