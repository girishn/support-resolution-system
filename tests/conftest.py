"""Pytest configuration: set PYTHONPATH for agent imports."""
import sys
from pathlib import Path

# Add repo root and agents/triage so triage.llm, triage.enricher, triage.agent can be imported
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))
sys.path.insert(0, str(repo_root / "agents" / "triage"))
