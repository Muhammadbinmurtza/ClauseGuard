"""Agent 1: Extractor — segments document into individual clauses."""

import json
import logging
from typing import Optional

from clauseguard.config.prompts import EXTRACTOR_SYSTEM_PROMPT
from clauseguard.models.clause import Clause, ClauseList
from clauseguard.services.model_service import call_model, clean_json_response

logger = logging.getLogger(__name__)

MIN_CLAUSES = 3
MAX_RETRIES = 1


async def run_extractor(raw_text: str, filename: str = "document") -> ClauseList:
    """Extract clauses from raw contract text using the Extractor agent.

    Args:
        raw_text: The raw text content of the contract.
        filename: Name of the source file (for context).

    Returns:
        A ClauseList containing the extracted clauses.

    Raises:
        ValueError: If fewer than MIN_CLAUSES clauses are found.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Document is empty or unreadable")

    prompt = _build_user_prompt(raw_text, filename)

    content = await call_model(
        system_prompt=EXTRACTOR_SYSTEM_PROMPT,
        user_prompt=prompt,
        agent_name="Extractor",
        max_retries=MAX_RETRIES,
    )

    if content is None:
        raise ValueError("Extractor agent failed to produce a valid response")

    clause_list = _parse_response(content)
    _validate_clause_list(clause_list)
    return clause_list


def _build_user_prompt(raw_text: str, filename: str) -> str:
    """Build the user prompt with the contract text."""
    return f"""Extract all clauses from the following contract document.

Filename: {filename}

Document text:
{raw_text}
"""


def _parse_response(content: str) -> ClauseList:
    """Parse the LLM JSON response into a ClauseList."""
    cleaned = clean_json_response(content)
    data = json.loads(cleaned)

    if isinstance(data, list):
        clauses_data = data
    elif isinstance(data, dict):
        clauses_data = data.get("clauses", [])
    else:
        clauses_data = []

    clauses: list[Clause] = []
    for c in clauses_data:
        clauses.append(
            Clause(
                id=c.get("id", 0),
                raw_text=c.get("raw_text", ""),
                plain_english=c.get("plain_english"),
                clause_type=c.get("clause_type", "OTHER"),
                section_heading=c.get("section_heading"),
                position=c.get("position", 0),
            )
        )

    contract_type_raw = data.get("contract_type", "Other") if isinstance(data, dict) else "Other"

    return ClauseList(
        clauses=clauses,
        contract_type=contract_type_raw,
        total_clauses=len(clauses),
    )


def _validate_clause_list(clause_list: ClauseList) -> None:
    """Validate the extracted clause list meets minimum requirements.

    Raises:
        ValueError: If fewer than MIN_CLAUSES clauses are found.
    """
    if clause_list.total_clauses < MIN_CLAUSES:
        raise ValueError(
            f"Document too short or unreadable — minimum {MIN_CLAUSES} clauses required"
        )
