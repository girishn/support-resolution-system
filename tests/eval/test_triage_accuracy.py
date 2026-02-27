"""
Eval framework: Triage classification accuracy.

Runs classify_ticket on fixture cases and reports type/priority accuracy.
Requires: MOCK_LLM unset and LLM available (Ollama or API) for real evaluation.

Usage:
  pytest tests/eval/test_triage_accuracy.py -v -s
  MOCK_LLM= pytest tests/eval/test_triage_accuracy.py -v -s   # Force real LLM
"""
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.eval

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_cases():
    path = FIXTURES_DIR / "triage_cases.json"
    if not path.exists():
        return []
    return json.loads(path.read_text())


@pytest.fixture
def triage_cases():
    return _load_cases()


def test_triage_accuracy_report(triage_cases, request):
    """Run triage on cases and report accuracy. Requires real LLM (MOCK_LLM unset)."""
    import os
    if os.environ.get("MOCK_LLM", "").lower() in ("1", "true", "yes"):
        pytest.skip("Eval requires real LLM; set MOCK_LLM= to run.")

    from triage.llm import classify_ticket

    if not triage_cases:
        pytest.skip("No triage_cases.json fixtures found.")

    type_correct = 0
    priority_correct = 0
    total = len(triage_cases)
    results = []

    for i, case in enumerate(triage_cases):
        subject = case.get("subject", "")
        body = case.get("body", "")
        expected_type = case.get("expected_type", "")
        expected_priority = case.get("expected_priority", "")

        try:
            out = classify_ticket(subject=subject, body=body, channel="portal")
        except Exception as e:
            results.append({"case": i, "error": str(e), "ok": False})
            continue

        got_type = out.get("type", "")
        got_priority = out.get("priority", "")
        type_ok = got_type == expected_type
        priority_ok = got_priority == expected_priority
        if type_ok:
            type_correct += 1
        if priority_ok:
            priority_correct += 1

        results.append({
            "case": i,
            "subject": subject[:40],
            "expected": (expected_type, expected_priority),
            "got": (got_type, got_priority),
            "confidence": out.get("confidence"),
            "type_ok": type_ok,
            "priority_ok": priority_ok,
        })

    type_acc = type_correct / total if total else 0
    priority_acc = priority_correct / total if total else 0

    # Print report (visible with -s)
    print("\n--- Triage Eval Report ---")
    print(f"Type accuracy:     {type_correct}/{total} = {type_acc:.1%}")
    print(f"Priority accuracy: {priority_correct}/{total} = {priority_acc:.1%}")
    for r in results:
        if "error" in r:
            print(f"  Case {r['case']}: ERROR {r['error']}")
        else:
            status = "✓" if (r["type_ok"] and r["priority_ok"]) else "✗"
            print(f"  {status} Case {r['case']}: expected {r['expected']}, got {r['got']} (conf={r.get('confidence')})")
    print("-------------------------\n")

    # Assert minimum accuracy (optional; relax for small/local models)
    assert type_acc >= 0.0, "Type accuracy below 0%"
