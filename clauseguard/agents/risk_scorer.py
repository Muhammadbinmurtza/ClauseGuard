"""Agent 3: Risk Scorer — evaluates severity of each clause."""

import asyncio
import json
import logging
from typing import List

from openai import AsyncOpenAI

from clauseguard.config.prompts import RISK_SCORER_SYSTEM_PROMPT
from clauseguard.config.settings import BASE_URL, DEEPSEEK_API_KEY, MAX_TOKENS, MODEL_NAME, TEMPERATURE, TIMEOUT_SECONDS
from clauseguard.models.clause import Clause, ClauseType
from clauseguard.models.findings import RiskFinding, ScoredClause, Severity

logger = logging.getLogger(__name__)
MAX_RETRIES = 1


async def run_risk_scorer(clause_list) -> List[ScoredClause]:
    """Evaluate each clause and assign severity with evidence-based risk reasons.

    Args:
        clause_list: A ClauseList with classified clauses.

    Returns:
        A list of ScoredClause objects with risk findings.
    """
    client = _build_client()
    input_json = clause_list.model_dump_json(indent=2)

    content = await _call_with_retry(
        client,
        system_prompt=RISK_SCORER_SYSTEM_PROMPT,
        user_prompt=f"Score the risk for each of these clauses:\n{input_json}",
        agent_name="Risk Scorer",
    )
    if content is None:
        logger.warning("Risk Scorer produced no valid output after retries")
        return []

    return _parse_response(content)


async def _call_with_retry(
    client: AsyncOpenAI,
    system_prompt: str,
    user_prompt: str,
    agent_name: str,
) -> str | None:
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=TEMPERATURE,
                    max_tokens=MAX_TOKENS,
                ),
                timeout=TIMEOUT_SECONDS,
            )
            content = response.choices[0].message.content or ""
            json.loads(_clean_json_response(content))
            return content
        except json.JSONDecodeError as e:
            last_error = str(e)
            if attempt < MAX_RETRIES:
                logger.warning("%s returned malformed JSON, retrying...", agent_name)
                user_prompt += "\n\nIMPORTANT: Output ONLY raw JSON array."
        except asyncio.TimeoutError:
            logger.error("%s agent timed out after %ds", agent_name, TIMEOUT_SECONDS)
            return None
        except Exception as e:
            logger.error("%s agent failed: %s", agent_name, e)
            return None
    logger.error("%s failed to produce valid JSON after %d attempts: %s", agent_name, MAX_RETRIES + 1, last_error)
    return None


def _build_client() -> AsyncOpenAI:
    """Build an AsyncOpenAI client configured for DeepSeek."""
    return AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=BASE_URL)


def _parse_response(content: str) -> List[ScoredClause]:
    """Parse the risk scorer JSON response into ScoredClause objects."""
    cleaned = _clean_json_response(content)
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


def _clean_json_response(content: str) -> str:
    """Strip markdown fences from LLM JSON output."""
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    return content.strip()
