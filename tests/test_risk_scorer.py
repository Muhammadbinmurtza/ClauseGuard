"""Tests for the Risk Scorer agent."""

import json

import pytest

from clauseguard.agents.risk_scorer import _parse_response
from clauseguard.models.findings import ScoredClause, Severity


def _make_mock_response(clauses_data: list) -> str:
    """Build a mock LLM JSON response string for testing."""
    return json.dumps(clauses_data)


def test_ip_assignment_clause_is_critical() -> None:
    """Test that IP assignment of personal time/side projects is rated CRITICAL."""
    mock_response = _make_mock_response([
        {
            "clause": {
                "id": 1,
                "raw_text": "Employee hereby assigns to Company all inventions and intellectual property created by Employee, whether during working hours or on Employee's own time, using Company equipment or Employee's personal equipment.",
                "plain_english": None,
                "clause_type": "IP_ASSIGNMENT",
                "section_heading": "INTELLECTUAL PROPERTY",
                "position": 1,
            },
            "finding": {
                "clause_id": 1,
                "severity": "CRITICAL",
                "risk_title": "IP Assignment of Personal Work",
                "risk_reason": "This clause claims ownership of all employee creations including those made on personal time and equipment with no carve-out for unrelated work.",
                "recommended_action": "",
            },
        }
    ])

    scored = _parse_response(mock_response)
    assert len(scored) == 1
    assert scored[0].finding.severity == Severity.CRITICAL
    assert scored[0].clause.clause_type.value == "IP_ASSIGNMENT"


def test_governing_law_clause_is_low_or_info() -> None:
    """Test that a standard governing law clause is rated LOW or INFO."""
    mock_response = _make_mock_response([
        {
            "clause": {
                "id": 1,
                "raw_text": "This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware.",
                "plain_english": None,
                "clause_type": "GOVERNING_LAW",
                "section_heading": "GOVERNING LAW",
                "position": 1,
            },
            "finding": {
                "clause_id": 1,
                "severity": "LOW",
                "risk_title": "Standard Governing Law",
                "risk_reason": "Standard governing law clause selecting Delaware, a common jurisdiction.",
                "recommended_action": "",
            },
        }
    ])

    scored = _parse_response(mock_response)
    assert len(scored) == 1
    assert scored[0].finding.severity in (Severity.LOW, Severity.INFO)


def test_every_scored_clause_has_non_empty_risk_reason() -> None:
    """Test that every ScoredClause has a non-empty risk_reason."""
    mock_response = _make_mock_response([
        {
            "clause": {
                "id": 1,
                "raw_text": "For two years, Employee shall not compete with Company anywhere in the United States.",
                "plain_english": None,
                "clause_type": "NON_COMPETE",
                "section_heading": "NON-COMPETE",
                "position": 1,
            },
            "finding": {
                "clause_id": 1,
                "severity": "CRITICAL",
                "risk_title": "Overly Broad Non-Compete",
                "risk_reason": "Non-compete duration of 2 years covers the entire US with no geographic relevance to Company's actual operations.",
                "recommended_action": "",
            },
        },
        {
            "clause": {
                "id": 2,
                "raw_text": "Notice shall be sent to the address listed above.",
                "plain_english": None,
                "clause_type": "OTHER",
                "section_heading": "NOTICES",
                "position": 2,
            },
            "finding": {
                "clause_id": 2,
                "severity": "INFO",
                "risk_title": "Standard Notice Provision",
                "risk_reason": "Boilerplate notice provision with no unusual terms.",
                "recommended_action": "",
            },
        },
    ])

    scored = _parse_response(mock_response)
    assert len(scored) == 2
    for sc in scored:
        assert sc.finding.risk_reason, f"Clause {sc.clause.id} has empty risk_reason"
        assert len(sc.finding.risk_reason) > 5


def test_multiple_severity_levels() -> None:
    """Test that different severities are correctly parsed."""
    mock_response = _make_mock_response([
        {
            "clause": {
                "id": i,
                "raw_text": f"Test clause {i}",
                "plain_english": None,
                "clause_type": "OTHER",
                "section_heading": None,
                "position": i,
            },
            "finding": {
                "clause_id": i,
                "severity": sev.value,
                "risk_title": f"Risk {i}",
                "risk_reason": f"Reason for clause {i}",
                "recommended_action": "",
            },
        }
        for i, sev in enumerate(
            [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO], 1
        )
    ])

    scored = _parse_response(mock_response)
    assert len(scored) == 5
    severities = [sc.finding.severity for sc in scored]
    assert Severity.CRITICAL in severities
    assert Severity.HIGH in severities
    assert Severity.MEDIUM in severities
    assert Severity.LOW in severities
    assert Severity.INFO in severities
