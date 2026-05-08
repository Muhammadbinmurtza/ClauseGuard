"""Integration tests for the full 5-agent pipeline."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from clauseguard.agents.orchestrator import run_pipeline
from clauseguard.models.findings import Severity
from clauseguard.models.report import FinalReport

SAMPLE_NDA_PATH = Path(__file__).parent.parent / "sample_contracts" / "sample_nda.txt"


def load_sample_nda() -> str:
    with open(SAMPLE_NDA_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _mock_extract_response() -> str:
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
    return json.dumps([
        {"clause": {"id": 1, "raw_text": "Confidential Information shall mean any and all information disclosed.", "plain_english": None, "clause_type": "NDA", "section_heading": "DEFINITION", "position": 1}, "finding": {"clause_id": 1, "severity": "INFO", "risk_title": "Broad Definition", "risk_reason": "Standard.", "recommended_action": ""}},
        {"clause": {"id": 2, "raw_text": "Recipient agrees to hold all Confidential Information in strict confidence.", "plain_english": None, "clause_type": "NDA", "section_heading": "CONFIDENTIALITY", "position": 2}, "finding": {"clause_id": 2, "severity": "LOW", "risk_title": "Standard Confidentiality", "risk_reason": "Standard.", "recommended_action": ""}},
        {"clause": {"id": 3, "raw_text": "For 18 months, Recipient shall not compete anywhere in the world.", "plain_english": None, "clause_type": "NON_COMPETE", "section_heading": "NON-COMPETE", "position": 3}, "finding": {"clause_id": 3, "severity": "HIGH", "risk_title": "Global Non-Compete", "risk_reason": "Worldwide scope.", "recommended_action": ""}},
        {"clause": {"id": 4, "raw_text": "Recipient assigns all inventions including those on personal time and equipment for 1 year after.", "plain_english": None, "clause_type": "IP_ASSIGNMENT", "section_heading": "IP ASSIGNMENT", "position": 4}, "finding": {"clause_id": 4, "severity": "CRITICAL", "risk_title": "IP Assignment of Personal Work", "risk_reason": "Assigns all IP.", "recommended_action": ""}},
        {"clause": {"id": 5, "raw_text": "All disputes resolved by binding arbitration, waives jury trial.", "plain_english": None, "clause_type": "ARBITRATION", "section_heading": "ARBITRATION", "position": 5}, "finding": {"clause_id": 5, "severity": "HIGH", "risk_title": "Mandatory Arbitration", "risk_reason": "Mandatory arbitration.", "recommended_action": ""}},
        {"clause": {"id": 6, "raw_text": "This Agreement governed by New York law.", "plain_english": None, "clause_type": "GOVERNING_LAW", "section_heading": "GOVERNING LAW", "position": 6}, "finding": {"clause_id": 6, "severity": "LOW", "risk_title": "Standard Governing Law", "risk_reason": "Standard NY law.", "recommended_action": ""}},
        {"clause": {"id": 7, "raw_text": "Auto-renews for 1-year terms unless 90 days notice.", "plain_english": None, "clause_type": "AUTO_RENEWAL", "section_heading": "AUTO-RENEWAL", "position": 7}, "finding": {"clause_id": 7, "severity": "MEDIUM", "risk_title": "Auto-Renewal", "risk_reason": "90-day notice.", "recommended_action": ""}},
        {"clause": {"id": 8, "raw_text": "If any provision is invalid, the rest remains in effect.", "plain_english": None, "clause_type": "OTHER", "section_heading": "SEVERABILITY", "position": 8}, "finding": {"clause_id": 8, "severity": "INFO", "risk_title": "Standard Severability", "risk_reason": "Standard.", "recommended_action": ""}},
    ])


def _mock_translate_response() -> str:
    return json.dumps([
        {"clause": {"id": 1, "raw_text": "Confidential Information shall mean any and all information disclosed.", "clause_type": "NDA", "section_heading": "DEFINITION", "position": 1, "plain_english": "Defines confidential info."}, "finding": {"clause_id": 1, "severity": "INFO", "risk_title": "Broad Definition", "risk_reason": "Standard.", "recommended_action": "No action."}},
        {"clause": {"id": 2, "raw_text": "Recipient agrees to hold all Confidential Information in strict confidence.", "clause_type": "NDA", "section_heading": "CONFIDENTIALITY", "position": 2, "plain_english": "Keep info secret."}, "finding": {"clause_id": 2, "severity": "LOW", "risk_title": "Standard Confidentiality", "risk_reason": "Standard.", "recommended_action": "No action."}},
        {"clause": {"id": 3, "raw_text": "For 18 months, Recipient shall not compete anywhere in the world.", "clause_type": "NON_COMPETE", "section_heading": "NON-COMPETE", "position": 3, "plain_english": "No competing worldwide for 18 months."}, "finding": {"clause_id": 3, "severity": "HIGH", "risk_title": "Global Non-Compete", "risk_reason": "Worldwide.", "recommended_action": "Reduce scope."}},
        {"clause": {"id": 4, "raw_text": "Recipient assigns all inventions including those on personal time and equipment for 1 year after.", "clause_type": "IP_ASSIGNMENT", "section_heading": "IP ASSIGNMENT", "position": 4, "plain_english": "You give all inventions to company."}, "finding": {"clause_id": 4, "severity": "CRITICAL", "risk_title": "IP Assignment of Personal Work", "risk_reason": "Assigns all IP.", "recommended_action": "Add carve-out."}},
        {"clause": {"id": 5, "raw_text": "All disputes resolved by binding arbitration, waives jury trial.", "clause_type": "ARBITRATION", "section_heading": "ARBITRATION", "position": 5, "plain_english": "Must use arbitration."}, "finding": {"clause_id": 5, "severity": "HIGH", "risk_title": "Mandatory Arbitration", "risk_reason": "Mandatory.", "recommended_action": "Add opt-out."}},
        {"clause": {"id": 6, "raw_text": "This Agreement governed by New York law.", "clause_type": "GOVERNING_LAW", "section_heading": "GOVERNING LAW", "position": 6, "plain_english": "NY law applies."}, "finding": {"clause_id": 6, "severity": "LOW", "risk_title": "Standard Governing Law", "risk_reason": "Standard.", "recommended_action": "No action."}},
        {"clause": {"id": 7, "raw_text": "Auto-renews for 1-year terms unless 90 days notice.", "clause_type": "AUTO_RENEWAL", "section_heading": "AUTO-RENEWAL", "position": 7, "plain_english": "Auto-renews yearly."}, "finding": {"clause_id": 7, "severity": "MEDIUM", "risk_title": "Auto-Renewal", "risk_reason": "Auto.", "recommended_action": "Track."}},
        {"clause": {"id": 8, "raw_text": "If any provision is invalid, the rest remains in effect.", "clause_type": "OTHER", "section_heading": "SEVERABILITY", "position": 8, "plain_english": "Invalid parts don't invalidate rest."}, "finding": {"clause_id": 8, "severity": "INFO", "risk_title": "Standard Severability", "risk_reason": "Standard.", "recommended_action": "No action."}},
    ])


_MOCK_RESPONSES = [
    _mock_extract_response(),
    _mock_classify_response(),
    _mock_score_response(),
    _mock_translate_response(),
]

_AGENT_CALL_MODEL_PATHS = [
    "clauseguard.agents.extractor.call_model",
    "clauseguard.agents.classifier.call_model",
    "clauseguard.agents.risk_scorer.call_model",
    "clauseguard.agents.translator.call_model",
]


@pytest.mark.asyncio
async def test_pipeline_returns_final_report() -> None:
    text = load_sample_nda()
    results_iter = iter(_MOCK_RESPONSES)

    async def mock_call_model(**kwargs):
        try:
            return next(results_iter)
        except StopIteration:
            return None

    patches = [patch(path, side_effect=mock_call_model) for path in _AGENT_CALL_MODEL_PATHS]
    for p in patches:
        p.start()
    try:
        report = await run_pipeline(text, "sample_nda.txt")
    finally:
        for p in patches:
            p.stop()

    assert isinstance(report, FinalReport)
    assert report.contract_name == "sample_nda.txt"


@pytest.mark.asyncio
async def test_pipeline_finds_critical_or_high() -> None:
    text = load_sample_nda()
    results_iter = iter(_MOCK_RESPONSES)

    async def mock_call_model(**kwargs):
        try:
            return next(results_iter)
        except StopIteration:
            return None

    patches = [patch(path, side_effect=mock_call_model) for path in _AGENT_CALL_MODEL_PATHS]
    for p in patches:
        p.start()
    try:
        report = await run_pipeline(text, "sample_nda.txt")
    finally:
        for p in patches:
            p.stop()

    assert isinstance(report, FinalReport)
    assert report.summary.critical_count >= 1 or report.summary.high_count >= 1, (
        f"Expected at least 1 CRITICAL or HIGH finding"
    )


@pytest.mark.asyncio
async def test_markdown_report_is_non_empty() -> None:
    text = load_sample_nda()
    results_iter = iter(_MOCK_RESPONSES)

    async def mock_call_model(**kwargs):
        try:
            return next(results_iter)
        except StopIteration:
            return None

    patches = [patch(path, side_effect=mock_call_model) for path in _AGENT_CALL_MODEL_PATHS]
    for p in patches:
        p.start()
    try:
        report = await run_pipeline(text, "sample_nda.txt")
    finally:
        for p in patches:
            p.stop()

    assert isinstance(report.markdown_report, str)
    assert len(report.markdown_report) > 0


@pytest.mark.asyncio
async def test_pipeline_handles_extractor_failure_gracefully() -> None:
    text = "too short"

    async def mock_call_model(**kwargs):
        return None

    patches = [patch(path, side_effect=mock_call_model) for path in _AGENT_CALL_MODEL_PATHS]
    for p in patches:
        p.start()
    try:
        report = await run_pipeline(text, "test.txt")
    finally:
        for p in patches:
            p.stop()

    assert isinstance(report, FinalReport)
