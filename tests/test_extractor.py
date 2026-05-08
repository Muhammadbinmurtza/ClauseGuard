"""Tests for the Extractor agent."""

import json
import os
from pathlib import Path

import pytest

from clauseguard.agents.extractor import _parse_response, _validate_clause_list
from clauseguard.models.clause import Clause, ClauseList

SAMPLE_NDA_PATH = Path(__file__).parent.parent / "sample_contracts" / "sample_nda.txt"


def load_sample_nda() -> str:
    """Load the sample NDA text file."""
    with open(SAMPLE_NDA_PATH, "r", encoding="utf-8") as f:
        return f.read()


def test_sample_nda_produces_at_least_6_clauses() -> None:
    """Verify sample_nda.txt has enough content to produce 6+ clauses."""
    text = load_sample_nda()
    # The document has 10 numbered sections
    assert len(text.split("\n")) > 20
    # Each paragraph cluster represents a clause
    from clauseguard.tools.clause_tools import split_into_clauses
    clauses = split_into_clauses(text)
    assert len(clauses) >= 6, f"Expected at least 6 clauses, got {len(clauses)}"


def test_short_text_raises_value_error() -> None:
    """Test that a very short document (2 sentences) raises ValueError."""
    mock_json = json.dumps({
        "clauses": [
            {
                "id": 1,
                "raw_text": "This is a short agreement.",
                "plain_english": None,
                "clause_type": "OTHER",
                "section_heading": None,
                "position": 1,
            },
            {
                "id": 2,
                "raw_text": "Parties agree to the above.",
                "plain_english": None,
                "clause_type": "OTHER",
                "section_heading": None,
                "position": 2,
            },
        ],
        "contract_type": "Other",
        "total_clauses": 2,
    })

    clause_list = _parse_response(mock_json)
    with pytest.raises(ValueError, match="minimum 3 clauses required"):
        _validate_clause_list(clause_list)


def test_output_matches_clause_list_schema() -> None:
    """Test that parsed output matches the ClauseList Pydantic schema."""
    mock_json = json.dumps({
        "clauses": [
            {
                "id": 1,
                "raw_text": "Employee shall maintain confidentiality of all trade secrets.",
                "plain_english": None,
                "clause_type": "OTHER",
                "section_heading": "CONFIDENTIALITY",
                "position": 1,
            },
            {
                "id": 2,
                "raw_text": "This Agreement is governed by Delaware law.",
                "plain_english": None,
                "clause_type": "OTHER",
                "section_heading": "GOVERNING LAW",
                "position": 2,
            },
            {
                "id": 3,
                "raw_text": "Either party may terminate for convenience.",
                "plain_english": None,
                "clause_type": "OTHER",
                "section_heading": "TERMINATION",
                "position": 3,
            },
        ],
        "contract_type": "NDA",
        "total_clauses": 3,
    })

    clause_list = _parse_response(mock_json)
    assert isinstance(clause_list, ClauseList)
    assert clause_list.total_clauses == 3
    assert clause_list.contract_type == "NDA"
    assert len(clause_list.clauses) == 3
    assert all(isinstance(c, Clause) for c in clause_list.clauses)
    assert all(c.id > 0 for c in clause_list.clauses)
    assert all(c.raw_text for c in clause_list.clauses)


def test_parse_response_handles_list_input() -> None:
    """Test that _parse_response handles both list and dict input formats."""
    list_json = json.dumps([
        {
            "id": 1,
            "raw_text": "Test clause one.",
            "plain_english": None,
            "clause_type": "OTHER",
            "section_heading": None,
            "position": 1,
        },
        {
            "id": 2,
            "raw_text": "Test clause two.",
            "plain_english": None,
            "clause_type": "OTHER",
            "section_heading": None,
            "position": 2,
        },
        {
            "id": 3,
            "raw_text": "Test clause three.",
            "plain_english": None,
            "clause_type": "OTHER",
            "section_heading": None,
            "position": 3,
        },
    ])

    clause_list = _parse_response(list_json)
    assert clause_list.total_clauses == 3


def test_parse_response_handles_markdown_fences() -> None:
    """Test that markdown code fences are stripped from responses."""
    wrapped_json = '```json\n{\n  "clauses": [\n    {"id": 1, "raw_text": "Test one.", "plain_english": null, "clause_type": "OTHER", "section_heading": null, "position": 1},\n    {"id": 2, "raw_text": "Test two.", "plain_english": null, "clause_type": "OTHER", "section_heading": null, "position": 2},\n    {"id": 3, "raw_text": "Test three.", "plain_english": null, "clause_type": "OTHER", "section_heading": null, "position": 3}\n  ],\n  "contract_type": "Other",\n  "total_clauses": 3\n}\n```'

    clause_list = _parse_response(wrapped_json)
    assert clause_list.total_clauses == 3
    assert clause_list.clauses[0].raw_text == "Test one."
