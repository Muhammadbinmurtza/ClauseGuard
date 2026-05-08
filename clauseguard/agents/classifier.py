"""Agent 2: Classifier — assigns clause types and detects contract type."""

import json
import logging
from typing import Any

from clauseguard.config.prompts import CLASSIFIER_SYSTEM_PROMPT
from clauseguard.models.clause import Clause, ClauseList, ClauseType
from clauseguard.services.model_service import call_model, clean_json_response

logger = logging.getLogger(__name__)
MAX_RETRIES = 1


async def run_classifier(clause_list: ClauseList) -> ClauseList:
    """Classify each clause and detect the overall contract type.

    Args:
        clause_list: The ClauseList from the Extractor agent.

    Returns:
        An updated ClauseList with clause_type and contract_type filled in.
    """
    input_json = clause_list.model_dump_json(indent=2)

    content = await call_model(
        system_prompt=CLASSIFIER_SYSTEM_PROMPT,
        user_prompt=f"Classify these clauses:\n{input_json}",
        agent_name="Classifier",
        max_retries=MAX_RETRIES,
    )

    if content is None:
        logger.warning("Classifier produced no valid output, returning original clauses")
        return clause_list

    return _parse_response(content, clause_list)


def _parse_response(content: str, original: ClauseList) -> ClauseList:
    """Parse the classifier JSON response and merge with original data."""
    cleaned = clean_json_response(content)
    data = json.loads(cleaned)

    clauses_data = data.get("clauses", data if isinstance(data, list) else [])
    contract_type = data.get("contract_type", "Other")

    classified_clauses: list[Clause] = []
    for c in clauses_data:
        clause_type_raw = c.get("clause_type", "OTHER")
        try:
            clause_type = ClauseType(clause_type_raw)
        except ValueError:
            clause_type = ClauseType.OTHER

        classified_clauses.append(
            Clause(
                id=c.get("id", 0),
                raw_text=c.get("raw_text", ""),
                plain_english=c.get("plain_english"),
                clause_type=clause_type,
                section_heading=c.get("section_heading"),
                position=c.get("position", 0),
                confidence_score=c.get("confidence_score"),
            )
        )

    return ClauseList(
        clauses=classified_clauses,
        contract_type=contract_type,
        total_clauses=len(classified_clauses),
    )
