"""Unit tests for response guardrails."""
import pytest

from shared.guardrails import check_response


def test_check_response_passes_clean():
    assert check_response("Thank you for your inquiry. We have processed your refund.") == "Thank you for your inquiry. We have processed your refund."


def test_check_response_truncates_excess_length():
    long_text = "x" * 5000
    result = check_response(long_text)
    assert len(result) <= 4000
    assert "[Response truncated for length.]" in result


def test_check_response_forbidden_phrase_raises():
    with pytest.raises(ValueError, match="forbidden phrase"):
        check_response("Thank you. I am not a lawyer, but here is my view.")


def test_check_response_pii_credit_card_raises():
    with pytest.raises(ValueError, match="PII"):
        check_response("Your refund will be sent to card 4111-1111-1111-1111.")


def test_check_response_pii_ssn_raises():
    with pytest.raises(ValueError, match="PII"):
        check_response("The SSN on file is 123-45-6789.")


def test_check_response_policies_subset():
    # With only "length" policy, forbidden phrases are not checked
    result = check_response("I am not a doctor.", policies=("length",))
    assert "I am not a doctor" in result


def test_check_response_forbidden_phrase_after_truncation_point_rejects():
    """Forbidden content at end of long response is caught before truncation would remove it."""
    long_with_forbidden = "x" * 4500 + " I am not a lawyer."
    with pytest.raises(ValueError, match="forbidden phrase"):
        check_response(long_with_forbidden)
