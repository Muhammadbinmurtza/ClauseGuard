"""Agent 4: Translator — writes plain English explanations and negotiation support."""

import json
import logging
from typing import List

from clauseguard.config.prompts import TRANSLATOR_SYSTEM_PROMPT
from clauseguard.models.clause import Clause, ClauseType
from clauseguard.models.findings import RiskFinding, ScoredClause, Severity
from clauseguard.services.model_service import call_model, clean_json_response

logger = logging.getLogger(__name__)
MAX_RETRIES = 1


async def run_translator(scored_clauses: List[ScoredClause]) -> List[ScoredClause]:
    """Translate legal clauses into plain English and write actionable recommendations.

    Args:
        scored_clauses: A list of ScoredClause objects from the Risk Scorer.

    Returns:
        Updated ScoredClause list with plain_english and recommended_action filled in.
    """
    scored_json = [
        {
            "clause": sc.clause.model_dump(),
            "finding": sc.finding.model_dump(),
        }
        for sc in scored_clauses
    ]
    input_json = json.dumps(scored_json, indent=2)

    content = await call_model(
        system_prompt=TRANSLATOR_SYSTEM_PROMPT,
        user_prompt=f"Translate these clauses into plain English:\n{input_json}",
        agent_name="Translator",
        max_retries=MAX_RETRIES,
    )

    if content is None:
        logger.warning("Translator produced no valid output, returning original clauses")
        return scored_clauses

    return _parse_response(content, scored_clauses)


def _parse_response(content: str, original: List[ScoredClause]) -> List[ScoredClause]:
    """Parse translator response and merge plain_english + actions into originals."""
    cleaned = clean_json_response(content)
    data = json.loads(cleaned)

    items = data if isinstance(data, list) else [data]
    result: List[ScoredClause] = []

    for i, item in enumerate(items):
        clause_data = item.get("clause", {})
        finding_data = item.get("finding", {})

        plain_english = clause_data.get("plain_english")
        recommended_action = finding_data.get("recommended_action", "")
        negotiation_tip = finding_data.get("negotiation_tip", "")
        safer_clause_version = finding_data.get("safer_clause_version", "")
        negotiation_message = finding_data.get("negotiation_message", "")
        impact_scenarios = finding_data.get("impact_scenarios", [])

        if i < len(original):
            orig = original[i]
            clause = orig.clause.model_copy(update={"plain_english": plain_english})
            finding_updates = {"recommended_action": recommended_action}
            if negotiation_tip:
                finding_updates["negotiation_tip"] = negotiation_tip
            if safer_clause_version:
                finding_updates["safer_clause_version"] = safer_clause_version
            if negotiation_message:
                finding_updates["negotiation_message"] = negotiation_message
            if impact_scenarios:
                finding_updates["impact_scenarios"] = impact_scenarios
            finding = orig.finding.model_copy(update=finding_updates)
            result.append(ScoredClause(clause=clause, finding=finding))
        else:
            result.append(_build_scored_clause_from_data(clause_data, finding_data))

    return result


def _build_scored_clause_from_data(clause_data: dict, finding_data: dict) -> ScoredClause:
    """Build a ScoredClause from raw LLM response data."""
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
        safer_clause_version=finding_data.get("safer_clause_version", ""),
        negotiation_message=finding_data.get("negotiation_message", ""),
        impact_scenarios=finding_data.get("impact_scenarios", []),
    )

    return ScoredClause(clause=clause, finding=finding)
