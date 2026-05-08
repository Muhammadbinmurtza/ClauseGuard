"""Agent 3: Risk Scorer — evaluates severity of each clause."""

import json
import logging
from typing import List

from clauseguard.config.prompts import RISK_SCORER_SYSTEM_PROMPT
from clauseguard.models.clause import Clause, ClauseType
from clauseguard.models.findings import RiskFinding, ScoredClause, Severity
from clauseguard.services.model_service import call_model, clean_json_response

logger = logging.getLogger(__name__)
MAX_RETRIES = 1


async def run_risk_scorer(clause_list) -> List[ScoredClause]:
    """Evaluate each clause and assign severity with evidence-based risk reasons.

    Args:
        clause_list: A ClauseList with classified clauses.

    Returns:
        A list of ScoredClause objects with risk findings.
    """
    input_json = clause_list.model_dump_json(indent=2)

    content = await call_model(
        system_prompt=RISK_SCORER_SYSTEM_PROMPT,
        user_prompt=f"Score the risk for each of these clauses:\n{input_json}",
        agent_name="Risk Scorer",
        max_retries=MAX_RETRIES,
    )

    if content is None:
        logger.warning("Risk Scorer produced no valid output after retries")
        return []

    return _parse_response(content)


def _parse_response(content: str) -> List[ScoredClause]:
    """Parse the risk scorer JSON response into ScoredClause objects."""
    cleaned = clean_json_response(content)
    data = json.loads(cleaned)

    scored_clauses: List[ScoredClause] = []
    items = data if isinstance(data, list) else data.get("scored_clauses", [data])

    for item in items:
        clause_data = item.get("clause", {})
        finding_data = item.get("finding", {})

        clause_type_raw = clause_data.get("clause_type", "OTHER")
        try:
            clause_type = ClauseType(clause_type_raw)
        except ValueError:
            clause_type = ClauseType.OTHER

        severity_raw = finding_data.get("severity", "INFO")
        try:
            severity = Severity(severity_raw)
        except ValueError:
            severity = Severity.INFO

        clause = Clause(
            id=clause_data.get("id", 0),
            raw_text=clause_data.get("raw_text", ""),
            plain_english=clause_data.get("plain_english"),
            clause_type=clause_type,
            section_heading=clause_data.get("section_heading"),
            position=clause_data.get("position", 0),
            confidence_score=clause_data.get("confidence_score"),
        )

        finding = RiskFinding(
            clause_id=finding_data.get("clause_id", clause.id),
            severity=severity,
            risk_title=finding_data.get("risk_title", "Risk Identified"),
            risk_reason=finding_data.get("risk_reason", ""),
            recommended_action=finding_data.get("recommended_action", ""),
            negotiation_tip=finding_data.get("negotiation_tip", ""),
        )

        scored_clauses.append(ScoredClause(clause=clause, finding=finding))

    return scored_clauses
