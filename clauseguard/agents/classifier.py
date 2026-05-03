"""Agent 2: Classifier — assigns clause types and detects contract type."""

import asyncio
import json
import logging
from typing import Any

from openai import AsyncOpenAI

from clauseguard.config.prompts import CLASSIFIER_SYSTEM_PROMPT
from clauseguard.config.settings import BASE_URL, DEEPSEEK_API_KEY, MAX_TOKENS, MODEL_NAME, TEMPERATURE, TIMEOUT_SECONDS
from clauseguard.models.clause import Clause, ClauseList, ClauseType

logger = logging.getLogger(__name__)
MAX_RETRIES = 1


async def run_classifier(clause_list: ClauseList) -> ClauseList:
    """Classify each clause and detect the overall contract type.

    Args:
        clause_list: The ClauseList from the Extractor agent.

    Returns:
        An updated ClauseList with clause_type, contract_type, and confidence_scores filled in.
    """
    client = _build_client()
    input_json = clause_list.model_dump_json(indent=2)

    content = await _call_with_retry(
        client,
        system_prompt=CLASSIFIER_SYSTEM_PROMPT,
        user_prompt=f"Classify these clauses:\n{input_json}",
        agent_name="Classifier",
    )

    return _parse_response(content, clause_list)


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
                user_prompt += "\n\nIMPORTANT: Output ONLY raw JSON."
        except asyncio.TimeoutError:
            logger.error("%s agent timed out", agent_name)
            return None
        except Exception as e:
            logger.error("%s agent failed: %s", agent_name, e)
            return None
    logger.error("%s failed: %s", agent_name, last_error)
    return None


def _build_client() -> AsyncOpenAI:
    """Build an AsyncOpenAI client configured for DeepSeek."""
    return AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url=BASE_URL)


def _parse_response(content: str, original: ClauseList) -> ClauseList:
    """Parse the classifier JSON response and merge with original data."""
    cleaned = _clean_json_response(content)
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
