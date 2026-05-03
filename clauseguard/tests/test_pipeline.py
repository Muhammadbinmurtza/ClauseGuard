"""Integration tests for the full 5-agent pipeline."""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from clauseguard.agents.orchestrator import run_pipeline
from clauseguard.models.findings import Severity
from clauseguard.models.report import FinalReport

SAMPLE_NDA_PATH = Path(__file__).parent.parent / "sample_contracts" / "sample_nda.txt"


def load_sample_nda() -> str:
    """Load the sample NDA text."""
    with open(SAMPLE_NDA_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _mock_extract_response() -> str:
    """Return a mock extractor JSON response."""
    return json.dumps({
        "clauses": [
            {"id": 1, "raw_text": "Confidential Information shall mean any and all information disclosed.", "plain_english": None, "clause_type": "OTHER", "section_heading": "DEFINITION", "position": 1},
            {"id": 2, "raw_text": "Recipient agrees to hold all Confidential Information in strict confidence.", "plain_english": None, "clause_type": "OTHER", "section_heading": "CONFIDENTIALITY", "position": 2},
            {"id": 3, "raw_text": "For 18 months, Recipient shall not compete anywhere in the world.", "plain_english": None, "clause_type": "OTHER", "section_heading": "NON-COMPETE", "position": 3},
            {"id": 4, "raw_text": "Recipient assigns all inventions including those on personal time and equipment for 1 year after.", "plain_english": None, "clause_type": "OTHER", "section_heading": "IP ASSIGNMENT", "position": 4},
            {"id": 5, "raw_text": "All disputes resolved by binding arbitration, waives jury trial.", "plain_english": None, "clause_type": "OTHER", "section_heading": "ARBITRATION", "position": 5},
            {"id": 6, "raw_text": "This Agreement governed by New York law.", "plain_english": None, "clause_type": "OTHER", "section_heading": "GOVERNING LAW", "position": 6},
            {"id": 7, "raw_text": "Auto-renews for 1-year terms unless 90 days notice.", "plain_english": None, "clause_type": "OTHER", "section_heading": "AUTO-RENEWAL", "position": 7},
            {"id": 8, "raw_text": "If any provision is invalid, the rest remains in effect.", "plain_english": None, "clause_type": "OTHER", "section_heading": "SEVERABILITY", "position": 8},
        ],
        "contract_type": "Other",
        "total_clauses": 8,
    })


def _mock_classify_response() -> str:
    """Return a mock classifier JSON response."""
    return json.dumps({
        "clauses": [
            {"id": 1, "raw_text": "Confidential Information shall mean any and all information disclosed.", "plain_english": None, "clause_type": "NDA", "section_heading": "DEFINITION", "position": 1},
            {"id": 2, "raw_text": "Recipient agrees to hold all Confidential Information in strict confidence.", "plain_english": None, "clause_type": "NDA", "section_heading": "CONFIDENTIALITY", "position": 2},
            {"id": 3, "raw_text": "For 18 months, Recipient shall not compete anywhere in the world.", "plain_english": None, "clause_type": "NON_COMPETE", "section_heading": "NON-COMPETE", "position": 3},
            {"id": 4, "raw_text": "Recipient assigns all inventions including those on personal time and equipment for 1 year after.", "plain_english": None, "clause_type": "IP_ASSIGNMENT", "section_heading": "IP ASSIGNMENT", "position": 4},
            {"id": 5, "raw_text": "All disputes resolved by binding arbitration, waives jury trial.", "plain_english": None, "clause_type": "ARBITRATION", "section_heading": "ARBITRATION", "position": 5},
            {"id": 6, "raw_text": "This Agreement governed by New York law.", "plain_english": None, "clause_type": "GOVERNING_LAW", "section_heading": "GOVERNING LAW", "position": 6},
            {"id": 7, "raw_text": "Auto-renews for 1-year terms unless 90 days notice.", "plain_english": None, "clause_type": "AUTO_RENEWAL", "section_heading": "AUTO-RENEWAL", "position": 7},
            {"id": 8, "raw_text": "If any provision is invalid, the rest remains in effect.", "plain_english": None, "clause_type": "OTHER", "section_heading": "SEVERABILITY", "position": 8},
        ],
        "contract_type": "NDA",
        "total_clauses": 8,
    })


def _mock_score_response() -> str:
    """Return a mock risk scorer JSON response."""
    return json.dumps([
        {"clause": {"id": 1, "raw_text": "Confidential Information shall mean any and all information disclosed.", "plain_english": None, "clause_type": "NDA", "section_heading": "DEFINITION", "position": 1}, "finding": {"clause_id": 1, "severity": "INFO", "risk_title": "Broad Definition", "risk_reason": "Definition of confidential information is broad but standard for NDA.", "recommended_action": ""}},
        {"clause": {"id": 2, "raw_text": "Recipient agrees to hold all Confidential Information in strict confidence.", "plain_english": None, "clause_type": "NDA", "section_heading": "CONFIDENTIALITY", "position": 2}, "finding": {"clause_id": 2, "severity": "LOW", "risk_title": "Standard Confidentiality", "risk_reason": "Standard confidentiality obligation with no unusual scope.", "recommended_action": ""}},
        {"clause": {"id": 3, "raw_text": "For 18 months, Recipient shall not compete anywhere in the world.", "plain_english": None, "clause_type": "NON_COMPETE", "section_heading": "NON-COMPETE", "position": 3}, "finding": {"clause_id": 3, "severity": "HIGH", "risk_title": "Global Non-Compete", "risk_reason": "Non-compete covers the entire world with no geographic boundary tied to Company operations.", "recommended_action": ""}},
        {"clause": {"id": 4, "raw_text": "Recipient assigns all inventions including those on personal time and equipment for 1 year after.", "plain_english": None, "clause_type": "IP_ASSIGNMENT", "section_heading": "IP ASSIGNMENT", "position": 4}, "finding": {"clause_id": 4, "severity": "CRITICAL", "risk_title": "IP Assignment of Personal Work", "risk_reason": "Clause assigns all IP including work on personal time and equipment, extending 1 year after termination.", "recommended_action": ""}},
        {"clause": {"id": 5, "raw_text": "All disputes resolved by binding arbitration, waives jury trial.", "plain_english": None, "clause_type": "ARBITRATION", "section_heading": "ARBITRATION", "position": 5}, "finding": {"clause_id": 5, "severity": "HIGH", "risk_title": "Mandatory Arbitration with Jury Waiver", "risk_reason": "Clause mandates binding arbitration and explicitly waives right to jury trial with no opt-out.", "recommended_action": ""}},
        {"clause": {"id": 6, "raw_text": "This Agreement governed by New York law.", "plain_english": None, "clause_type": "GOVERNING_LAW", "section_heading": "GOVERNING LAW", "position": 6}, "finding": {"clause_id": 6, "severity": "LOW", "risk_title": "Standard Governing Law", "risk_reason": "Standard choice of New York law, commonly used in contracts.", "recommended_action": ""}},
        {"clause": {"id": 7, "raw_text": "Auto-renews for 1-year terms unless 90 days notice.", "plain_english": None, "clause_type": "AUTO_RENEWAL", "section_heading": "AUTO-RENEWAL", "position": 7}, "finding": {"clause_id": 7, "severity": "MEDIUM", "risk_title": "Auto-Renewal with 90-Day Notice", "risk_reason": "Auto-renewal with 90-day notice requirement, which is reasonable but requires calendar tracking.", "recommended_action": ""}},
        {"clause": {"id": 8, "raw_text": "If any provision is invalid, the rest remains in effect.", "plain_english": None, "clause_type": "OTHER", "section_heading": "SEVERABILITY", "position": 8}, "finding": {"clause_id": 8, "severity": "INFO", "risk_title": "Standard Severability", "risk_reason": "Standard severability clause with no unusual terms.", "recommended_action": ""}},
    ])


def _mock_translate_response() -> str:
    """Return a mock translator JSON response."""
    return json.dumps([
        {"clause": {"id": 1, "raw_text": "Confidential Information shall mean any and all information disclosed.", "clause_type": "NDA", "section_heading": "DEFINITION", "position": 1, "plain_english": "This clause defines confidential information broadly to include everything disclosed to you."}, "finding": {"clause_id": 1, "severity": "INFO", "risk_title": "Broad Definition", "risk_reason": "Definition of confidential information is broad but standard for NDA.", "recommended_action": "Confirm the scope of confidential information is limited to information marked as confidential."}},
        {"clause": {"id": 2, "raw_text": "Recipient agrees to hold all Confidential Information in strict confidence.", "clause_type": "NDA", "section_heading": "CONFIDENTIALITY", "position": 2, "plain_english": "You must keep all confidential information secret and cannot share it without written permission."}, "finding": {"clause_id": 2, "severity": "LOW", "risk_title": "Standard Confidentiality", "risk_reason": "Standard confidentiality obligation with no unusual scope.", "recommended_action": "No action needed — this is standard."}},
        {"clause": {"id": 3, "raw_text": "For 18 months, Recipient shall not compete anywhere in the world.", "clause_type": "NON_COMPETE", "section_heading": "NON-COMPETE", "position": 3, "plain_english": "You cannot work for any competitor anywhere in the world for 18 months after this agreement ends."}, "finding": {"clause_id": 3, "severity": "HIGH", "risk_title": "Global Non-Compete", "risk_reason": "Non-compete covers the entire world with no geographic boundary tied to Company operations.", "recommended_action": "Negotiate to limit the non-compete to the specific geographic regions where the Company actually operates."}},
        {"clause": {"id": 4, "raw_text": "Recipient assigns all inventions including those on personal time and equipment for 1 year after.", "clause_type": "IP_ASSIGNMENT", "section_heading": "IP ASSIGNMENT", "position": 4, "plain_english": "You give the company all rights to anything you create, even on your own time and equipment, and for a year after the agreement ends."}, "finding": {"clause_id": 4, "severity": "CRITICAL", "risk_title": "IP Assignment of Personal Work", "risk_reason": "Clause assigns all IP including work on personal time and equipment, extending 1 year after termination.", "recommended_action": "Demand a carve-out for inventions created on your own time using your own equipment that are unrelated to the Company's business."}},
        {"clause": {"id": 5, "raw_text": "All disputes resolved by binding arbitration, waives jury trial.", "clause_type": "ARBITRATION", "section_heading": "ARBITRATION", "position": 5, "plain_english": "You must resolve all disputes through private arbitration and give up your right to sue in court or have a jury trial."}, "finding": {"clause_id": 5, "severity": "HIGH", "risk_title": "Mandatory Arbitration with Jury Waiver", "risk_reason": "Clause mandates binding arbitration and explicitly waives right to jury trial with no opt-out.", "recommended_action": "Negotiate to add an opt-out clause for arbitration or remove the jury trial waiver."}},
        {"clause": {"id": 6, "raw_text": "This Agreement governed by New York law.", "clause_type": "GOVERNING_LAW", "section_heading": "GOVERNING LAW", "position": 6, "plain_english": "This clause says New York state law will apply to any disputes about this agreement."}, "finding": {"clause_id": 6, "severity": "LOW", "risk_title": "Standard Governing Law", "risk_reason": "Standard choice of New York law, commonly used in contracts.", "recommended_action": "No action needed unless you prefer a different jurisdiction."}},
        {"clause": {"id": 7, "raw_text": "Auto-renews for 1-year terms unless 90 days notice.", "clause_type": "AUTO_RENEWAL", "section_heading": "AUTO-RENEWAL", "position": 7, "plain_english": "This agreement automatically renews each year unless you give 90 days notice to cancel."}, "finding": {"clause_id": 7, "severity": "MEDIUM", "risk_title": "Auto-Renewal with 90-Day Notice", "risk_reason": "Auto-renewal with 90-day notice requirement, which is reasonable but requires calendar tracking.", "recommended_action": "Set a calendar reminder 120 days before the end of each term to decide whether to renew."}},
        {"clause": {"id": 8, "raw_text": "If any provision is invalid, the rest remains in effect.", "clause_type": "OTHER", "section_heading": "SEVERABILITY", "position": 8, "plain_english": "This clause means that if one part of the agreement is found to be invalid, the rest still applies."}, "finding": {"clause_id": 8, "severity": "INFO", "risk_title": "Standard Severability", "risk_reason": "Standard severability clause with no unusual terms.", "recommended_action": "No action needed — this is standard boilerplate."}},
    ])


def _mock_reporter_response() -> str:
    """Return a mock reporter JSON response."""
    return json.dumps({
        "contract_name": "sample_nda.txt",
        "summary": {
            "total_clauses": 8,
            "critical_count": 1,
            "high_count": 2,
            "medium_count": 1,
            "low_count": 2,
            "overall_score": 5.0,
            "contract_type": "NDA",
        },
        "top_3_actions": [
            "Demand a carve-out for inventions created on own time",
            "Negotiate geographic limit on non-compete",
            "Add opt-out for arbitration clause",
        ],
        "scored_clauses": [],
        "markdown_report": "# ClauseGuard Risk Report\n\nTest markdown content",
    })


@pytest.mark.asyncio
async def test_pipeline_returns_final_report() -> None:
    """Test that the full pipeline returns a FinalReport."""
    text = load_sample_nda()

    results = [
        _mock_extract_response(),
        _mock_classify_response(),
        _mock_score_response(),
        _mock_translate_response(),
        _mock_reporter_response(),
    ]
    results_iter = iter(results)

    class MockResponse:
        def __init__(self, content):
            self.message = type("msg", (), {"content": content})()
            self.choices = [type("choice", (), {"message": self.message})()]

    class MockCompletions:
        async def create(self, **kwargs):
            content = next(results_iter)
            return MockResponse(content)

    class MockClient:
        def __init__(self):
            self.chat = type("chat", (), {"completions": MockCompletions()})()

    with patch("clauseguard.agents.extractor._build_client", return_value=MockClient()), \
         patch("clauseguard.agents.classifier._build_client", return_value=MockClient()), \
         patch("clauseguard.agents.risk_scorer._build_client", return_value=MockClient()), \
         patch("clauseguard.agents.translator._build_client", return_value=MockClient()), \
         patch("clauseguard.agents.reporter._build_client", return_value=MockClient()):
        report = await run_pipeline(text, "sample_nda.txt")

    assert isinstance(report, FinalReport)
    assert report.contract_name == "sample_nda.txt"


@pytest.mark.asyncio
async def test_pipeline_finds_critical_or_high() -> None:
    """Test that the pipeline identifies at least 1 CRITICAL or HIGH finding."""
    text = load_sample_nda()

    results = [
        _mock_extract_response(),
        _mock_classify_response(),
        _mock_score_response(),
        _mock_translate_response(),
        _mock_reporter_response(),
    ]
    results_iter = iter(results)

    class MockResponse:
        def __init__(self, content):
            self.message = type("msg", (), {"content": content})()
            self.choices = [type("choice", (), {"message": self.message})()]

    class MockCompletions:
        async def create(self, **kwargs):
            content = next(results_iter)
            return MockResponse(content)

    class MockClient:
        def __init__(self):
            self.chat = type("chat", (), {"completions": MockCompletions()})()

    with patch("clauseguard.agents.extractor._build_client", return_value=MockClient()), \
         patch("clauseguard.agents.classifier._build_client", return_value=MockClient()), \
         patch("clauseguard.agents.risk_scorer._build_client", return_value=MockClient()), \
         patch("clauseguard.agents.translator._build_client", return_value=MockClient()), \
         patch("clauseguard.agents.reporter._build_client", return_value=MockClient()):
        report = await run_pipeline(text, "sample_nda.txt")

    assert isinstance(report, FinalReport)
    assert report.summary.critical_count >= 1 or report.summary.high_count >= 1, (
        f"Expected at least 1 CRITICAL or HIGH finding, got critical={report.summary.critical_count} high={report.summary.high_count}"
    )


@pytest.mark.asyncio
async def test_markdown_report_is_non_empty() -> None:
    """Test that the markdown_report field is a non-empty string."""
    text = load_sample_nda()

    results = [
        _mock_extract_response(),
        _mock_classify_response(),
        _mock_score_response(),
        _mock_translate_response(),
        _mock_reporter_response(),
    ]
    results_iter = iter(results)

    class MockResponse:
        def __init__(self, content):
            self.message = type("msg", (), {"content": content})()
            self.choices = [type("choice", (), {"message": self.message})()]

    class MockCompletions:
        async def create(self, **kwargs):
            content = next(results_iter)
            return MockResponse(content)

    class MockClient:
        def __init__(self):
            self.chat = type("chat", (), {"completions": MockCompletions()})()

    with patch("clauseguard.agents.extractor._build_client", return_value=MockClient()), \
         patch("clauseguard.agents.classifier._build_client", return_value=MockClient()), \
         patch("clauseguard.agents.risk_scorer._build_client", return_value=MockClient()), \
         patch("clauseguard.agents.translator._build_client", return_value=MockClient()), \
         patch("clauseguard.agents.reporter._build_client", return_value=MockClient()):
        report = await run_pipeline(text, "sample_nda.txt")

    assert isinstance(report.markdown_report, str)
    assert len(report.markdown_report) > 0


@pytest.mark.asyncio
async def test_pipeline_handles_extractor_failure_gracefully() -> None:
    """Test that pipeline returns a FinalReport even when Extractor fails."""
    text = "too short"

    class MockClient:
        def __init__(self):
            self.chat = type("chat", (), {})()

    with patch("clauseguard.agents.extractor._build_client", return_value=MockClient()), \
         patch("clauseguard.agents.extractor.run_extractor", side_effect=ValueError("Test failure")):
        report = await run_pipeline(text, "test.txt")

    assert isinstance(report, FinalReport)
